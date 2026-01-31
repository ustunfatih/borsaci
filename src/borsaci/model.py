"""PydanticAI agent factory with Multi-Model and Multi-Provider support"""

from pydantic_ai import Agent
from typing import Any, Optional, Union
import os

from .config import get_config_manager, GoogleOAuthCredential


# Model mappings for different providers
# OpenRouter uses prefixed strings, Google uses raw model names (for custom provider)
MODEL_MAPPINGS = {
    "openrouter": {
        "planning": "openrouter:google/gemini-3-pro-preview",
        "action": "openrouter:google/gemini-3-flash-preview",
        "validation": "openrouter:google/gemini-3-flash-preview",
        "answer": "openrouter:google/gemini-3-flash-preview",
        "buffett": "openrouter:google/gemini-3-flash-preview",
    },
    "google": {
        # Model names for Cloud Code Assist API (uses OAuth with cloud-platform scope)
        # Available via cloudcode-pa.googleapis.com with -preview suffix
        # Gemini 3 models now available: gemini-3-pro-preview, gemini-3-flash-preview
        "planning": "gemini-3-pro-preview",    # Best reasoning for task decomposition
        "action": "gemini-3-flash-preview",    # Fast tool calling
        "validation": "gemini-3-flash-preview",
        "answer": "gemini-3-flash-preview",
        "buffett": "gemini-3-flash-preview",
    },
}


def _get_model(role: str) -> str:
    """
    Get model string for a role based on active provider.

    Args:
        role: Agent role (planning, action, validation, answer, buffett)

    Returns:
        Model string for PydanticAI (prefixed for OpenRouter, raw for Google OAuth)
    """
    provider = get_config_manager().get_active_provider()
    return MODEL_MAPPINGS[provider][role]


def is_google_provider() -> bool:
    """Check if using Google OAuth provider."""
    return get_config_manager().get_active_provider() == "google"


async def get_model_for_agent(role: str) -> Union[str, Any]:
    """
    Get model for agent creation, handling OAuth for Google provider.

    For OpenRouter: Returns model string (e.g., "openrouter:google/gemini-3-flash")
    For Google OAuth: Returns CloudCodeModel instance using Cloud Code Assist API

    Args:
        role: Agent role (planning, action, validation, answer, buffett)

    Returns:
        Model string or CloudCodeModel instance
    """
    if is_google_provider():
        from .google_oauth_provider import create_cloudcode_model, ensure_google_oauth_ready

        # Ensure Cloud Code client is initialized
        await ensure_google_oauth_ready()

        model_name = MODEL_MAPPINGS["google"][role]
        return create_cloudcode_model(model_name)
    else:
        return MODEL_MAPPINGS["openrouter"][role]


async def ensure_google_token_fresh():
    """
    Refresh Google OAuth token if expired.

    This should be called before making API requests when using Google provider.
    Automatically refreshes expired access tokens using refresh token.
    """
    cm = get_config_manager()

    # Only applies to Google provider
    if cm.get_active_provider() != "google":
        return

    # Check if token is expired
    if not cm.is_google_token_expired():
        return

    # Get current credentials
    cred = cm.get_google_oauth()
    if not cred or not cred.refresh_token:
        raise Exception("Google OAuth credentials missing. Run 'login google' to authenticate.")

    # Get credential source for refresh
    source = cm.get_google_credential_source() or "antigravity"

    # Import OAuth functions
    from .oauth import refresh_access_token, resolve_oauth_credentials

    # Get client credentials for refresh
    cred_source, client_id, client_secret = resolve_oauth_credentials()

    # Refresh the token
    try:
        new_cred = await refresh_access_token(
            refresh_token=cred.refresh_token,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Save refreshed credentials
        cm.save_google_oauth(
            GoogleOAuthCredential(
                access_token=new_cred.access_token,
                refresh_token=new_cred.refresh_token,
                expires_at=new_cred.expires_at,
                email=cred.email,  # Preserve original email
            ),
            source=source,
        )
    except Exception as e:
        raise Exception(f"Token refresh failed: {e}. Run 'login google' to re-authenticate.")


def get_planning_model() -> str:
    """
    Get model for Planning Agent.

    Returns:
        Gemini 3 Pro - Strong reasoning for task decomposition
    """
    return _get_model("planning")


def get_action_model() -> str:
    """
    Get model for Action Agent.

    Returns:
        Gemini 3 Flash - Optimized for tool calling
    """
    return _get_model("action")


def get_validation_model() -> str:
    """
    Get model for Validation Agent.

    Returns:
        Gemini 3 Flash - Simple validation tasks
    """
    return _get_model("validation")


def get_answer_model() -> str:
    """
    Get model for Answer Agent.

    Returns:
        Gemini 3 Flash - Fast, high-quality responses
    """
    return _get_model("answer")


def get_buffett_model() -> str:
    """
    Get model for Warren Buffett Agent.

    Returns:
        Gemini 3 Flash (default) - Fast analysis with good quality
        Can be overridden via BUFFETT_MODEL env variable for Pro model (OpenRouter only)
    """
    # Check for env override (backwards compatibility for OpenRouter)
    env_model = os.getenv("BUFFETT_MODEL")
    if env_model:
        return env_model
    return _get_model("buffett")


def create_agent(
    model: str,
    system_prompt: str,
    output_type: Optional[type] = None,
    tools: Optional[list] = None,
    deps_type: Optional[type] = None,
    retries: int = 3,
) -> Agent:
    """
    Create a PydanticAI agent with specified OpenRouter model.

    Args:
        model: OpenRouter model string (e.g., from get_planning_model())
        system_prompt: System prompt for the agent
        output_type: Optional Pydantic model for structured output
        tools: Optional list of tools/functions the agent can use
        deps_type: Optional type for dependency injection context
        retries: Number of retries for tool calls and model requests (default: 3)

    Returns:
        Configured PydanticAI Agent

    Example:
        >>> from borsaci.schemas import Answer
        >>> agent = create_agent(
        ...     get_answer_model(),
        ...     "You are a financial analyst",
        ...     output_type=Answer
        ... )
        >>> result = await agent.run("Analyze ASELS stock")
    """
    return Agent(
        model=model,
        system_prompt=system_prompt,
        output_type=output_type,
        tools=tools or [],
        deps_type=deps_type,
        retries=retries,
    )


def create_planning_agent(output_type: type, system_prompt: str) -> Agent:
    """
    Create planning agent for task decomposition.

    Uses Gemini 3 Pro for strong reasoning capabilities.

    Args:
        output_type: Pydantic model for task list output
        system_prompt: System prompt with planning instructions

    Returns:
        Planning agent with 3 retries
    """
    return create_agent(
        model=get_planning_model(),
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


def create_action_agent(
    system_prompt: str,
    mcp_client: Any,
    deps_type: Optional[type] = None,
) -> Agent:
    """
    Create action agent with MCP tool access.

    Uses Gemini 3 Flash optimized for tool calling.

    Args:
        system_prompt: System prompt for tool selection
        mcp_client: BorsaMCP client instance (MCPServerStreamableHTTP)
        deps_type: Type for dependency injection

    Returns:
        Action agent with tool calling capabilities via MCP toolset (3 retries)
    """
    # Register MCP client as toolset
    # The agent will automatically discover and use MCP tools
    return Agent(
        model=get_action_model(),
        system_prompt=system_prompt,
        toolsets=[mcp_client],  # MCP server registered as toolset
        deps_type=deps_type,
        retries=3,  # MCP tools can fail temporarily, allow retries
    )


def create_validation_agent(output_type: type, system_prompt: str) -> Agent:
    """
    Create validation agent for task completion checking.

    Uses Gemini 3 Flash for simple validation tasks.

    Args:
        output_type: Pydantic model for validation result (IsDone)
        system_prompt: System prompt with validation criteria

    Returns:
        Validation agent with 3 retries
    """
    return create_agent(
        model=get_validation_model(),
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


def create_answer_agent(output_type: type, system_prompt: str) -> Agent:
    """
    Create answer generation agent.

    Uses Gemini 3 Flash for fast, high-quality final responses.

    Args:
        output_type: Pydantic model for answer output (Answer)
        system_prompt: System prompt for answer generation

    Returns:
        Answer agent with 3 retries
    """
    return create_agent(
        model=get_answer_model(),
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


def create_base_agent(output_type: type, system_prompt: str) -> Agent:
    """
    Create base routing agent for query triage.

    Uses Gemini 3 Flash for fast routing decisions (simple vs complex queries).
    This agent determines if a query can be answered directly or needs
    multi-agent workflow with MCP tools.

    Args:
        output_type: Pydantic model for routing decision (BaseResponse)
        system_prompt: System prompt for routing logic

    Returns:
        Base routing agent with 3 retries
    """
    return create_agent(
        model=get_action_model(),  # Flash - fast and cheap for routing
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


# =============================================================================
# Async Agent Creation (for Google OAuth support)
# =============================================================================

async def create_planning_agent_async(output_type: type, system_prompt: str) -> Agent:
    """
    Create planning agent for task decomposition (async version).

    Supports both OpenRouter and Google OAuth providers.

    Args:
        output_type: Pydantic model for task list output
        system_prompt: System prompt with planning instructions

    Returns:
        Planning agent with 3 retries
    """
    model = await get_model_for_agent("planning")
    return Agent(
        model=model,
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


async def create_action_agent_async(
    system_prompt: str,
    mcp_client: Any,
    deps_type: Optional[type] = None,
) -> Agent:
    """
    Create action agent with MCP tool access (async version).

    Supports both OpenRouter and Google OAuth providers.

    Args:
        system_prompt: System prompt for tool selection
        mcp_client: BorsaMCP client instance (MCPServerStreamableHTTP)
        deps_type: Type for dependency injection

    Returns:
        Action agent with tool calling capabilities via MCP toolset (3 retries)
    """
    model = await get_model_for_agent("action")
    return Agent(
        model=model,
        system_prompt=system_prompt,
        toolsets=[mcp_client],
        deps_type=deps_type,
        retries=3,
    )


async def create_validation_agent_async(output_type: type, system_prompt: str) -> Agent:
    """
    Create validation agent for task completion checking (async version).

    Supports both OpenRouter and Google OAuth providers.

    Args:
        output_type: Pydantic model for validation result (IsDone)
        system_prompt: System prompt with validation criteria

    Returns:
        Validation agent with 3 retries
    """
    model = await get_model_for_agent("validation")
    return Agent(
        model=model,
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


async def create_answer_agent_async(output_type: Optional[type], system_prompt: str) -> Agent:
    """
    Create answer generation agent (async version).

    Supports both OpenRouter and Google OAuth providers.

    Args:
        output_type: Optional Pydantic model for answer output (Answer)
        system_prompt: System prompt for answer generation

    Returns:
        Answer agent with 3 retries
    """
    model = await get_model_for_agent("answer")
    return Agent(
        model=model,
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )


async def create_base_agent_async(output_type: type, system_prompt: str) -> Agent:
    """
    Create base routing agent for query triage (async version).

    Supports both OpenRouter and Google OAuth providers.

    Args:
        output_type: Pydantic model for routing decision (BaseResponse)
        system_prompt: System prompt for routing logic

    Returns:
        Base routing agent with 3 retries
    """
    model = await get_model_for_agent("action")  # Flash for routing
    return Agent(
        model=model,
        system_prompt=system_prompt,
        output_type=output_type,
        retries=3,
    )
