"""CLI entry point for BorsaCI - Interactive REPL for Turkish financial markets"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from .agent import BorsaAgent
from .utils.ui import print_banner, print_goodbye, print_help, print_error_banner
from .utils.logger import Logger
from .utils.loading import run_with_loading_and_cancel
from .updater import check_and_auto_update
from .config import get_config_manager, GoogleOAuthCredential, ProviderType


# Custom prompt style
prompt_style = Style.from_dict({
    'prompt': '#00aa00 bold',
})


def write_openrouter_key_to_env(api_key: str):
    """
    Write OpenRouter API key to .env file, creating from template if needed.

    Args:
        api_key: OpenRouter API key to save
    """
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if env_path.exists():
        # .env exists, update the key
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open(env_path, "w", encoding="utf-8") as f:
            found = False
            for line in lines:
                if line.startswith("OPENROUTER_API_KEY="):
                    f.write(f"OPENROUTER_API_KEY={api_key}\n")
                    found = True
                else:
                    f.write(line)

            # If key wasn't in file, add it
            if not found:
                f.write(f"\nOPENROUTER_API_KEY={api_key}\n")

    else:
        # .env doesn't exist, create from template
        if env_example_path.exists():
            with open(env_example_path, "r", encoding="utf-8") as f:
                template = f.read()

            # Replace placeholder with actual key
            content = template.replace(
                "OPENROUTER_API_KEY=sk-or-v1-your_key_here",
                f"OPENROUTER_API_KEY={api_key}"
            )

            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            # No template, create minimal .env
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("# BorsaCI Environment Variables\n")
                f.write(f"OPENROUTER_API_KEY={api_key}\n")
                f.write("\n# Optional: OpenRouter app info\n")
                f.write("# HTTP_REFERER=https://borsaci.app\n")
                f.write("# X_TITLE=BorsaCI\n")


async def check_and_setup_openrouter_key(logger: Logger) -> bool:
    """
    Check if OPENROUTER_API_KEY exists, if not prompt user and save to .env.

    Args:
        logger: Logger instance for output

    Returns:
        True if key is valid, False otherwise
    """
    # Check if key exists in environment
    api_key = os.getenv("OPENROUTER_API_KEY")

    # Debug logging
    if "--debug" in sys.argv:
        print(f"[DEBUG] OpenRouter key from env: {api_key[:10] + '...' if api_key else 'None'}")
        print(f"[DEBUG] Key is truthy: {bool(api_key)}")
        if api_key:
            print(f"[DEBUG] Key is not placeholder: {api_key != 'sk-or-v1-your_key_here'}")

    if api_key and api_key != "sk-or-v1-your_key_here":
        # Key exists and is not placeholder
        return True

    # Key missing or is placeholder
    logger.log_warning("OPENROUTER_API_KEY bulunamadı!")
    logger.log_info("OpenRouter API key'inizi alın: https://openrouter.ai/keys")
    print()

    # Create async prompt session
    from prompt_toolkit.shortcuts import PromptSession as AsyncPromptSession

    session = AsyncPromptSession()

    # Prompt user for OpenRouter key
    while True:
        try:
            # Use async prompt
            api_key = await session.prompt_async(
                "OpenRouter API Key: ",
                is_password=True,  # Mask input like password
            )

            # Strip whitespace
            api_key = api_key.strip()

            if not api_key:
                logger.log_error("API key boş olamaz!")
                continue

            # Validate format (OpenRouter keys start with sk-or-v1-)
            if not api_key.startswith("sk-or-v1-"):
                logger.log_error("Geçersiz format! Key 'sk-or-v1-' ile başlamalı.")
                logger.log_info("Örnek: sk-or-v1-xxxxxxxxxxxxxxxxxxxx")
                continue

            # Key looks valid
            break

        except KeyboardInterrupt:
            logger.log_warning("\nKurulum iptal edildi. Program sonlandırılıyor.")
            return False

    # Save to .env file
    try:
        write_openrouter_key_to_env(api_key)
        logger.log_success("OpenRouter API key .env dosyasına kaydedildi!")

        # Load into current environment
        os.environ["OPENROUTER_API_KEY"] = api_key

        return True

    except Exception as e:
        logger.log_error(f".env dosyasına yazılırken hata: {str(e)}")
        logger.log_info("API key'i manuel olarak .env dosyasına ekleyin")
        return False


async def setup_google_oauth(logger: Logger, force_login: bool = False) -> bool:
    """
    Google OAuth login flow with OpenClaw pattern.

    First checks for existing Gemini CLI tokens (~/.gemini/oauth_creds.json).
    If found, reuses them without browser login.
    Otherwise, uses Gemini CLI credentials for new OAuth flow.

    Args:
        logger: Logger instance for output
        force_login: If True, skip token reuse and force new browser login

    Returns:
        True if OAuth successful, False otherwise
    """
    from .oauth import login_google_oauth, resolve_oauth_credentials, extract_tokens_from_gemini_cli

    logger.log_info("🔐 Google Gemini OAuth Kurulumu")
    print()

    # First, try to reuse existing Gemini CLI tokens (no browser needed)
    if not force_login:
        existing_creds = extract_tokens_from_gemini_cli()
        if existing_creds:
            logger.log_info("Gemini CLI'dan mevcut token'lar bulundu")

            cm = get_config_manager()
            cm.save_google_oauth(
                GoogleOAuthCredential(
                    access_token=existing_creds.access_token,
                    refresh_token=existing_creds.refresh_token,
                    expires_at=existing_creds.expires_at,
                    email=existing_creds.email,
                ),
                source="gemini-cli",
            )
            cm.set_active_provider("google")

            email_info = f" ({existing_creds.email})" if existing_creds.email else ""
            logger.log_success(f"Gemini CLI token'ları kullanılıyor!{email_info}")
            return True

    # No existing tokens, need browser login
    try:
        # Resolve credentials (Gemini CLI > Antigravity)
        source, client_id, client_secret = resolve_oauth_credentials()
        logger.log_info(f"OAuth credentials bulundu ({source})")
    except Exception as e:
        logger.log_error(f"OAuth credential hatası: {str(e)}")
        return False

    try:
        logger.log_info("Browser ile giriş yapılıyor...")
        cred = await login_google_oauth(
            client_id=client_id,
            client_secret=client_secret,
        )

        cm = get_config_manager()
        cm.save_google_oauth(
            GoogleOAuthCredential(
                access_token=cred.access_token,
                refresh_token=cred.refresh_token,
                expires_at=cred.expires_at,
                email=cred.email,
            ),
            source=source,
        )
        cm.set_active_provider("google")

        email_info = f" ({cred.email})" if cred.email else ""
        logger.log_success(f"Google OAuth başarılı!{email_info}")
        return True

    except KeyboardInterrupt:
        logger.log_warning("\nOAuth iptal edildi.")
        return False

    except Exception as e:
        logger.log_error(f"OAuth hatası: {str(e)}")
        return False


async def select_provider(logger: Logger) -> ProviderType:
    """
    Interactive provider selection.

    Args:
        logger: Logger instance for output

    Returns:
        Selected provider ("openrouter" or "google")
    """
    session = PromptSession()

    logger.log_info("🔧 BorsaCI Provider Seçimi")
    print()
    print("  [1] OpenRouter (API Key)")
    print("      https://openrouter.ai/keys adresinden key alın")
    print()
    print("  [2] Google Gemini (OAuth)")
    print("      Browser ile Google hesabınıza giriş yapın")
    print()

    while True:
        try:
            choice = await session.prompt_async("Seçiminiz [1/2]: ")
            choice = choice.strip()
            if choice == "1":
                return "openrouter"
            elif choice == "2":
                return "google"
            else:
                print("Geçersiz seçim. 1 veya 2 girin.")
        except KeyboardInterrupt:
            print("\nVarsayılan provider kullanılıyor: openrouter")
            return "openrouter"


async def check_and_setup_credentials(logger: Logger) -> bool:
    """
    Main credential check and setup flow.

    Checks existing credentials and prompts for setup if needed.

    Args:
        logger: Logger instance for output

    Returns:
        True if valid credentials exist, False otherwise
    """
    cm = get_config_manager()

    # Check existing credentials for active provider first
    active = cm.get_active_provider()

    if cm.has_valid_credentials(active):
        if active == "openrouter":
            logger.log_info("Provider: OpenRouter")
        else:
            email = cm.get_google_oauth().email if cm.get_google_oauth() else None
            email_info = f" ({email})" if email else ""
            logger.log_info(f"Provider: Google Gemini{email_info}")
        return True

    # Check if other provider has credentials
    other = "google" if active == "openrouter" else "openrouter"
    if cm.has_valid_credentials(other):
        cm.set_active_provider(other)
        if other == "openrouter":
            logger.log_info("Provider: OpenRouter")
        else:
            email = cm.get_google_oauth().email if cm.get_google_oauth() else None
            email_info = f" ({email})" if email else ""
            logger.log_info(f"Provider: Google Gemini{email_info}")
        return True

    # No credentials - setup flow
    provider = await select_provider(logger)

    if provider == "openrouter":
        success = await check_and_setup_openrouter_key(logger)
        if success:
            cm.set_active_provider("openrouter")
            # Also save to config manager for consistency
            key = os.getenv("OPENROUTER_API_KEY")
            if key:
                cm.save_openrouter_key(key)
        return success
    else:
        return await setup_google_oauth(logger)


async def async_main():
    """Async main function for CLI"""
    # Check for updates and auto-update if available
    # (will restart program if update found)
    skip_update = "--skip-update" in sys.argv
    debug = "--debug" in sys.argv
    check_and_auto_update(skip_update=skip_update, debug=debug)

    # Print welcome banner
    print_banner()

    # Load environment variables
    load_dotenv()

    # Initialize logger
    logger = Logger()

    # Check and setup credentials if needed
    if not await check_and_setup_credentials(logger):
        logger.log_error("API credentials gereklidir. Program sonlandırılıyor.")
        sys.exit(1)

    print()  # Empty line for spacing

    # Create agent
    try:
        agent = BorsaAgent()
        logger.log_info("BorsaCI başlatılıyor...")
        logger.log_info(f"MCP Server: {agent.mcp.server_url}")

    except Exception as e:
        print_error_banner(f"Başlatma hatası: {str(e)}")
        logger.log_error("OPENROUTER_API_KEY veya model ayarlarını kontrol edin")

        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()

        sys.exit(1)

    # Create prompt session with history
    session = PromptSession(
        history=InMemoryHistory(),
        style=prompt_style,
    )

    # Main REPL loop with persistent MCP connection
    async with agent:
        logger.log_success("BorsaCI hazır! (MCP bağlantısı kuruldu)")

        # Conversation history stored across queries
        conversation_history = []

        while True:
            try:
                # Prompt for user input
                query = await session.prompt_async([('class:prompt', '>> ')])

                # Handle empty input
                if not query.strip():
                    continue

                # Handle special commands
                query_lower = query.lower().strip()

                if query_lower in ["exit", "quit", "çık", "q"]:
                    print_goodbye()
                    break

                if query_lower in ["help", "yardım", "h", "?"]:
                    print_help()
                    continue

                if query_lower in ["tools", "araçlar"]:
                    logger.log_info(agent.mcp.get_tools_summary())
                    continue

                if query_lower in ["clear", "temizle"]:
                    # Clear screen and conversation history
                    import os
                    os.system('clear' if os.name != 'nt' else 'cls')
                    print_banner()
                    conversation_history = []  # Reset conversation
                    logger.log_info("Sohbet geçmişi temizlendi")
                    continue

                if query_lower == "login google":
                    # Re-authenticate with Google OAuth (force fresh login to get correct scopes)
                    success = await setup_google_oauth(logger, force_login=True)
                    if success:
                        logger.log_info("Provider Google'a değiştirildi. Lütfen programı yeniden başlatın.")
                    continue

                if query_lower == "login openrouter":
                    # Re-setup OpenRouter API key
                    success = await check_and_setup_openrouter_key(logger)
                    if success:
                        cm = get_config_manager()
                        cm.set_active_provider("openrouter")
                        key = os.getenv("OPENROUTER_API_KEY")
                        if key:
                            cm.save_openrouter_key(key)
                        logger.log_info("Provider OpenRouter'a değiştirildi. Lütfen programı yeniden başlatın.")
                    continue

                if query_lower.startswith("provider"):
                    # Show or switch provider
                    cm = get_config_manager()
                    parts = query_lower.split()

                    if len(parts) == 1:
                        # Show current provider info
                        info = cm.get_provider_info()
                        print()
                        print(f"  Aktif Provider: {info['active']}")
                        print()
                        print("  OpenRouter:")
                        print(f"    Durumu: {'Yapılandırılmış' if info['openrouter']['configured'] else 'Yapılandırılmamış'}")
                        if info['openrouter']['key_preview']:
                            print(f"    Key: {info['openrouter']['key_preview']}")
                        print()
                        print("  Google Gemini:")
                        print(f"    Durumu: {'Yapılandırılmış' if info['google']['configured'] else 'Yapılandırılmamış'}")
                        if info['google']['email']:
                            print(f"    Email: {info['google']['email']}")
                        if info['google']['source']:
                            print(f"    Kaynak: {info['google']['source']}")
                        print()

                    elif len(parts) == 2 and parts[1] in ["openrouter", "google"]:
                        new_provider = parts[1]
                        if cm.has_valid_credentials(new_provider):
                            cm.set_active_provider(new_provider)
                            logger.log_success(f"Provider '{new_provider}' olarak değiştirildi. Lütfen programı yeniden başlatın.")
                        else:
                            logger.log_error(f"'{new_provider}' için credential bulunamadı. Önce 'login {new_provider}' komutunu çalıştırın.")
                    else:
                        logger.log_error("Kullanım: provider [openrouter|google]")

                    continue

                # Process query with agent
                try:
                    logger.log_user_query(query)

                    # Debug logging
                    if "--debug" in sys.argv:
                        print(f"[DEBUG] Calling agent.run() with query: {query[:50]}...")
                        print(f"[DEBUG] Conversation history has {len(conversation_history)} messages")

                    # Run agent with conversation history + loading animation + ESC cancel
                    answer, chart, messages = await run_with_loading_and_cancel(
                        agent.run(query, message_history=conversation_history)
                    )

                    # Update conversation history for next query
                    conversation_history = messages

                    if "--debug" in sys.argv:
                        print(f"[DEBUG] agent.run() returned, answer length: {len(answer)}")
                        print(f"[DEBUG] Chart present: {chart is not None}")
                        print(f"[DEBUG] Updated history now has {len(conversation_history)} messages")

                    # Display answer first
                    logger.log_summary(answer)

                    # Display chart separately if present (rendered directly to terminal)
                    if chart:
                        print()  # Empty line for spacing
                        print(chart)
                        print()  # Empty line after chart

                except asyncio.CancelledError:
                    logger.log_warning("⚠️  İşlem iptal edildi (ESC)")
                    continue

                except KeyboardInterrupt:
                    logger.log_warning("Sorgu iptal edildi")
                    continue

                except Exception as e:
                    logger.log_error(f"Sorgu işlenirken hata: {str(e)}")
                    import traceback
                    if "--debug" in sys.argv:
                        traceback.print_exc()

            except KeyboardInterrupt:
                # Ctrl+C pressed
                logger.log_warning("\nÇıkmak için 'exit' yazın")
                continue

            except EOFError:
                # Ctrl+D pressed
                print_goodbye()
                break

            except Exception as e:
                logger.log_error(f"Beklenmeyen hata: {str(e)}")
                if "--debug" in sys.argv:
                    import traceback
                    traceback.print_exc()


def main():
    """
    Main entry point for BorsaCI CLI.

    Usage:
        borsaci              - Start interactive mode
        borsaci --debug      - Start with debug output
        borsaci --help       - Show help
    """
    # Handle command line arguments
    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
BorsaCI - Türk Finans Piyasaları için AI Agent

Kullanım:
    borsaci                  Interactive mode başlat
    borsaci --debug          Debug çıktısı ile başlat
    borsaci --skip-update    Otomatik güncellemeyi atla
    borsaci --help           Bu yardım mesajını göster

Provider Seçenekleri:
    OpenRouter             API key ile (https://openrouter.ai/keys)
    Google Gemini          OAuth ile (browser'da giriş)

REPL Komutları:
    provider               Aktif provider'ı göster
    provider openrouter    OpenRouter'a geç
    provider google        Google Gemini'ye geç
    login google           Google OAuth ile yeniden giriş
    login openrouter       OpenRouter key'i yeniden gir
    clear                  Sohbet geçmişini temizle
    exit                   Programı kapat

Ortam Değişkenleri:
    OPENROUTER_API_KEY   OpenRouter API key (opsiyonel - OAuth da kullanılabilir)
    HTTP_REFERER         OpenRouter app info (opsiyonel)
    X_TITLE              OpenRouter app başlığı (opsiyonel)
    MAX_STEPS            Maksimum adım sayısı (varsayılan: 20)
    MAX_STEPS_PER_TASK   Görev başına maksimum adım (varsayılan: 5)

Credential Depolama:
    ~/.borsaci/config.json           Yapılandırma dosyası
    ~/.borsaci/credentials/          Credential dosyaları (chmod 600)

Daha fazla bilgi:
    https://github.com/saidsurucu/borsaci
        """)
        sys.exit(0)

    # Check Python version
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 veya üzeri gereklidir")
        sys.exit(1)

    # Run async main
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n\nHoşçakalın! 👋")
        sys.exit(0)


if __name__ == "__main__":
    main()
