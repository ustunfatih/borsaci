"""Custom PydanticAI model for Google Gemini with OAuth Bearer token support.

Uses Google's Cloud Code Assist API (cloudcode-pa.googleapis.com) which accepts
OAuth tokens with cloud-platform scope. This is the same approach used by:
- Gemini CLI
- OpenClaw/OpenCode
- VS Code Gemini extension

This bypasses the public Generative Language API which requires the
'generative-language' scope (not available on Gemini CLI OAuth client).
"""

from typing import Optional, Union
from dataclasses import dataclass

from pydantic_ai.models import Model, KnownModelName
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    ModelRequest,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    RetryPromptPart,
    SystemPromptPart,
    UserPromptPart,
)

from .cloudcode_provider import get_cloudcode_client, CloudCodeClient


def _convert_tools_to_gemini_format(tools: list) -> list[dict]:
    """
    Convert PydanticAI ToolDefinition to Gemini function declaration format.

    Gemini expects:
    {
        "functionDeclarations": [
            {
                "name": "tool_name",
                "description": "Tool description",
                "parameters": {  // JSON Schema
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        ]
    }
    """
    if not tools:
        return []

    function_declarations = []
    for tool in tools:
        func_decl = {
            "name": tool.name,
            "description": tool.description or "",
        }

        # Get parameters schema
        if hasattr(tool, 'parameters_json_schema') and tool.parameters_json_schema:
            # Flatten the schema to remove $defs/$ref
            schema = _flatten_json_schema(tool.parameters_json_schema.copy())
            func_decl["parameters"] = schema
        else:
            # No parameters
            func_decl["parameters"] = {
                "type": "object",
                "properties": {},
            }

        function_declarations.append(func_decl)

    return [{"functionDeclarations": function_declarations}]


def _flatten_json_schema(schema: dict) -> dict:
    """
    Flatten JSON schema by resolving $defs and $ref.

    Cloud Code API doesn't support $defs, $ref, examples, const, and other
    JSON Schema features, so we need to clean them up.
    """
    if not schema:
        return schema

    # Fields that Cloud Code API doesn't support
    UNSUPPORTED_FIELDS = {
        "$defs", "$ref", "examples", "const", "default",
        "title", "additionalProperties", "minItems", "maxItems",
        "minimum", "maximum", "pattern", "format",
    }

    defs = schema.pop("$defs", {})

    def resolve_refs(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_path = obj["$ref"]
                # Handle "#/$defs/TypeName" format
                if ref_path.startswith("#/$defs/"):
                    type_name = ref_path.split("/")[-1]
                    if type_name in defs:
                        # Return a copy of the definition, resolved recursively
                        resolved = resolve_refs(defs[type_name].copy())
                        return resolved
                return obj
            else:
                return {k: resolve_refs(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_refs(item) for item in obj]
        else:
            return obj

    flattened = resolve_refs(schema)

    # Remove unsupported fields recursively
    def remove_unsupported(obj):
        if isinstance(obj, dict):
            cleaned = {}
            for k, v in obj.items():
                if k in UNSUPPORTED_FIELDS:
                    continue
                cleaned[k] = remove_unsupported(v)
            return cleaned
        elif isinstance(obj, list):
            return [remove_unsupported(item) for item in obj]
        else:
            return obj

    cleaned = remove_unsupported(flattened)

    # Clean up anyOf with null type - Cloud Code doesn't like these
    def clean_any_of(obj):
        if isinstance(obj, dict):
            if "anyOf" in obj:
                # Check if it's a nullable pattern: [{"type": "X"}, {"type": "null"}]
                any_of = obj["anyOf"]
                non_null = [item for item in any_of if item.get("type") != "null"]
                if len(non_null) == 1:
                    # Replace anyOf with the non-null type
                    result = {k: v for k, v in obj.items() if k != "anyOf"}
                    result.update(non_null[0])
                    return {k: clean_any_of(v) for k, v in result.items()}
            return {k: clean_any_of(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_any_of(item) for item in obj]
        else:
            return obj

    return clean_any_of(cleaned)


def _convert_messages_to_contents(messages: list[ModelMessage]) -> tuple[list[dict], Optional[dict]]:
    """
    Convert PydanticAI messages to Cloud Code API contents format.

    Returns:
        Tuple of (contents list, system_instruction dict or None)
    """
    contents = []
    system_instruction = None

    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    # System prompt goes to system_instruction
                    system_instruction = {
                        "parts": [{"text": part.content}]
                    }
                elif isinstance(part, UserPromptPart):
                    contents.append({
                        "role": "user",
                        "parts": [{"text": part.content}]
                    })
                elif isinstance(part, ToolReturnPart):
                    # Tool return becomes user message with function response
                    contents.append({
                        "role": "user",
                        "parts": [{
                            "functionResponse": {
                                "name": part.tool_name,
                                "response": {"result": part.content}
                            }
                        }]
                    })
                elif isinstance(part, RetryPromptPart):
                    # Retry prompt becomes user message
                    content = part.content if isinstance(part.content, str) else str(part.content)
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"[Retry] {content}"}]
                    })
        elif isinstance(message, ModelResponse):
            # Model response becomes assistant message
            parts = []
            for part in message.parts:
                if isinstance(part, TextPart):
                    parts.append({"text": part.content})
                elif isinstance(part, ToolCallPart):
                    parts.append({
                        "functionCall": {
                            "name": part.tool_name,
                            "args": part.args if isinstance(part.args, dict) else {}
                        }
                    })
            if parts:
                contents.append({
                    "role": "model",
                    "parts": parts
                })

    return contents, system_instruction


def _convert_response_to_model_response(
    response: dict,
    output_tool_name: Optional[str] = None,
    is_json_response: bool = False,
) -> ModelResponse:
    """Convert Cloud Code API response to PydanticAI ModelResponse.

    Args:
        response: Raw API response
        output_tool_name: If set, convert JSON text to tool call for structured output
        is_json_response: Whether the response is JSON mode
    """
    parts = []

    # Cloud Code API wraps response in "response" field
    inner_response = response.get("response", response)
    candidates = inner_response.get("candidates", [])

    if candidates:
        content = candidates[0].get("content", {})
        for part in content.get("parts", []):
            if "text" in part:
                text = part["text"]
                # If we have an output tool name and JSON response,
                # convert to tool call (PydanticAI structured output pattern)
                if output_tool_name and is_json_response:
                    try:
                        import json
                        args = json.loads(text)
                        parts.append(ToolCallPart(
                            tool_name=output_tool_name,
                            args=args,
                            tool_call_id=output_tool_name,
                        ))
                    except json.JSONDecodeError:
                        # Fallback to text if JSON parsing fails
                        parts.append(TextPart(content=text))
                else:
                    parts.append(TextPart(content=text))
            elif "functionCall" in part:
                fc = part["functionCall"]
                parts.append(ToolCallPart(
                    tool_name=fc.get("name", ""),
                    args=fc.get("args", {}),
                    tool_call_id=fc.get("name", ""),  # Use name as ID
                ))

    # If no parts found, add empty text
    if not parts:
        parts.append(TextPart(content=""))

    return ModelResponse(parts=parts)


async def cloudcode_model_function(
    messages: list[ModelMessage],
    info: AgentInfo,
) -> ModelResponse:
    """
    PydanticAI FunctionModel implementation using Cloud Code API.

    This function is called by PydanticAI to generate responses.
    It converts messages to Cloud Code format and back.
    """
    client = get_cloudcode_client()

    # Convert PydanticAI messages to Cloud Code format
    contents, system_instruction = _convert_messages_to_contents(messages)

    # Get model name from info or use default
    model_name = getattr(info, 'model_name', None) or "gemini-2.0-flash"

    # Generate content using Cloud Code API
    response = await client.generate_content(
        model=model_name,
        contents=contents,
        system_instruction=system_instruction,
        generation_config={
            "temperature": 0.7,
            "maxOutputTokens": 8192,
        },
    )

    # Convert response back to PydanticAI format
    return _convert_response_to_model_response(response)


@dataclass
class CloudCodeModelInfo:
    """Model info for Cloud Code model."""
    model_name: str = "gemini-2.0-flash"


class CloudCodeModel(FunctionModel):
    """
    PydanticAI model that uses Google's Cloud Code Assist API.

    This model uses OAuth tokens with cloud-platform scope to authenticate
    to Google's internal API, bypassing the need for API keys or
    generative-language scope.

    Usage:
        model = CloudCodeModel("gemini-2.0-flash")
        agent = Agent(model=model, ...)
    """

    def __init__(self, gemini_model: str = "gemini-2.0-flash"):
        self._gemini_model = gemini_model
        # Store model name in a way the function can access
        self._info = CloudCodeModelInfo(model_name=gemini_model)

        # Create a closure that captures the model name
        async def model_func(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            client = get_cloudcode_client()
            contents, system_instruction = _convert_messages_to_contents(messages)

            # Check if structured output is expected (agent has output_tools)
            # If so, enable JSON mode for proper parsing
            generation_config = {
                "temperature": 0.7,
                "maxOutputTokens": 8192,
            }

            # Track if we're doing JSON structured output
            output_tool_name = None
            is_json_response = False

            # Check if structured output is expected via output_tools
            # PydanticAI creates a final_result tool even with output_type=None,
            # but with schema {'type': 'null'}. We need to detect and skip this case.
            should_use_json_mode = False
            if info.output_tools and not info.allow_text_output:
                tool_def = info.output_tools[0]
                if hasattr(tool_def, 'parameters_json_schema'):
                    schema = tool_def.parameters_json_schema
                    props = schema.get('properties', {})
                    # Check if this is a "None" output type (schema has only null type)
                    # This happens when Agent is created with output_type=None
                    if props.get('response', {}).get('type') == 'null':
                        # This is output_type=None, don't use JSON mode
                        should_use_json_mode = False
                    else:
                        should_use_json_mode = True
                        output_tool_name = tool_def.name

            if should_use_json_mode:
                # Enable JSON mode for structured output
                generation_config["responseMimeType"] = "application/json"
                is_json_response = True

                # Add schema to generation config if available
                if info.output_tools:
                    tool_def = info.output_tools[0]
                    if hasattr(tool_def, 'parameters_json_schema'):
                        # Flatten schema - Cloud Code doesn't support $defs/$ref
                        schema = tool_def.parameters_json_schema.copy()
                        generation_config["responseSchema"] = _flatten_json_schema(schema)

            # Convert function_tools to Gemini format for tool calling
            gemini_tools = None
            if info.function_tools:
                gemini_tools = _convert_tools_to_gemini_format(info.function_tools)

            response = await client.generate_content(
                model=self._gemini_model,
                contents=contents,
                system_instruction=system_instruction,
                generation_config=generation_config,
                tools=gemini_tools,
            )

            return _convert_response_to_model_response(
                response,
                output_tool_name=output_tool_name,
                is_json_response=is_json_response,
            )

        super().__init__(model_func)

    def name(self) -> str:
        return f"cloudcode:{self._gemini_model}"


# Singleton client for connection management
_cloudcode_client: Optional[CloudCodeClient] = None


async def ensure_google_oauth_ready():
    """
    Ensure Google OAuth is ready for use.

    This should be called before creating agents when using Google provider.
    It ensures the Cloud Code client can connect and load the project.
    """
    from .config import get_config_manager

    cm = get_config_manager()

    if cm.get_active_provider() != "google":
        return

    # Initialize Cloud Code client and load project
    client = get_cloudcode_client()
    await client.load_code_assist()


def create_cloudcode_model(model_name: str) -> CloudCodeModel:
    """
    Create a CloudCodeModel for use with PydanticAI agents.

    Args:
        model_name: Model name (e.g., "gemini-2.0-flash", "gemini-2.5-pro")

    Returns:
        CloudCodeModel instance configured for the specified model
    """
    return CloudCodeModel(model_name)


async def close_cloudcode_client():
    """Close the Cloud Code client connection."""
    client = get_cloudcode_client()
    await client.close()
