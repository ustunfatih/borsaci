"""Configuration and credential management for BorsaCI"""

from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel
import json
import os
import time

ProviderType = Literal["openrouter", "google"]


class GoogleOAuthCredential(BaseModel):
    """Google OAuth credential storage model"""
    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp (ms)
    email: Optional[str] = None


class BorsaConfig(BaseModel):
    """BorsaCI configuration model"""
    active_provider: ProviderType = "openrouter"
    # Store source of Google credentials for refresh
    google_credential_source: Optional[str] = None  # "gemini-cli" or "antigravity"


class ConfigManager:
    """
    Manages BorsaCI configuration and credentials.

    Storage locations:
    - ~/.borsaci/config.json - Main configuration
    - ~/.borsaci/credentials/openrouter.json - OpenRouter API key
    - ~/.borsaci/credentials/google.json - Google OAuth tokens (chmod 600)
    """
    CONFIG_DIR = Path.home() / ".borsaci"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    CREDENTIALS_DIR = CONFIG_DIR / "credentials"

    def __init__(self):
        self._config: Optional[BorsaConfig] = None
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create config directories if they don't exist with secure permissions"""
        self.CONFIG_DIR.mkdir(exist_ok=True, mode=0o700)
        self.CREDENTIALS_DIR.mkdir(exist_ok=True, mode=0o700)
        # Set credentials directory permissions (rwx------)
        try:
            self.CONFIG_DIR.chmod(0o700)
            self.CREDENTIALS_DIR.chmod(0o700)
        except Exception:
            pass

    def load(self) -> BorsaConfig:
        """Load configuration from file"""
        if self._config:
            return self._config
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE) as f:
                    self._config = BorsaConfig(**json.load(f))
            except (IOError, OSError, json.JSONDecodeError, TypeError):
                self._config = BorsaConfig()
        else:
            self._config = BorsaConfig()
        return self._config

    def save(self):
        """Save configuration to file"""
        if self._config:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self._config.model_dump(), f, indent=2)

    # OpenRouter API Key Management
    def save_openrouter_key(self, api_key: str):
        """
        Save OpenRouter API key to credentials file with secure permissions.
        
        Security: File is created with restricted mode first to prevent race condition.

        Args:
            api_key: OpenRouter API key
        """
        cred_file = self.CREDENTIALS_DIR / "openrouter.json"
        # Create file with restricted permissions using os.open with mode
        import os
        fd = os.open(str(cred_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump({"api_key": api_key}, f)
        except Exception:
            os.close(fd)
            raise
        # Ensure permissions are set correctly (in case umask affected it)
        try:
            cred_file.chmod(0o600)
        except Exception:
            pass

    def get_openrouter_key(self) -> Optional[str]:
        """
        Get OpenRouter API key from environment or credentials file.

        Returns:
            API key or None
        """
        # Environment override (for backwards compatibility)
        env_key = os.getenv("OPENROUTER_API_KEY")
        if env_key and env_key != "sk-or-v1-your_key_here":
            return env_key

        # File-based storage
        cred_file = self.CREDENTIALS_DIR / "openrouter.json"
        if cred_file.exists():
            try:
                with open(cred_file) as f:
                    return json.load(f).get("api_key")
            except (IOError, OSError, json.JSONDecodeError):
                pass
        return None

    # Google OAuth Management
    def save_google_oauth(self, cred: GoogleOAuthCredential, source: Optional[str] = None):
        """
        Save Google OAuth credentials to file with secure permissions.
        
        Security: File is created with restricted mode first to prevent race condition.

        Args:
            cred: GoogleOAuthCredential instance
            source: Credential source ("gemini-cli" or "antigravity")
        """
        cred_file = self.CREDENTIALS_DIR / "google.json"
        # Create file with restricted permissions using os.open with mode
        import os
        fd = os.open(str(cred_file), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(cred.model_dump(), f, indent=2)
        except Exception:
            os.close(fd)
            raise
        # Ensure permissions are set correctly (in case umask affected it)
        try:
            cred_file.chmod(0o600)
        except Exception:
            pass

        # Store credential source for refresh
        if source:
            config = self.load()
            config.google_credential_source = source
            self.save()

    def get_google_oauth(self) -> Optional[GoogleOAuthCredential]:
        """
        Get Google OAuth credentials from file.

        Returns:
            GoogleOAuthCredential or None
        """
        cred_file = self.CREDENTIALS_DIR / "google.json"
        if cred_file.exists():
            try:
                with open(cred_file) as f:
                    return GoogleOAuthCredential(**json.load(f))
            except (IOError, OSError, json.JSONDecodeError, TypeError):
                pass
        return None

    def is_google_token_expired(self) -> bool:
        """
        Check if Google OAuth access token is expired.

        Returns:
            True if expired or no token exists
        """
        cred = self.get_google_oauth()
        if not cred:
            return True
        # Compare current time (ms) with expiry
        return int(time.time() * 1000) >= cred.expires_at

    def get_google_credential_source(self) -> Optional[str]:
        """
        Get the source of Google credentials for refresh.

        Returns:
            "gemini-cli" or "antigravity" or None
        """
        return self.load().google_credential_source

    # Provider Management
    def get_active_provider(self) -> ProviderType:
        """
        Get currently active provider.

        Returns:
            "openrouter" or "google"
        """
        return self.load().active_provider

    def set_active_provider(self, provider: ProviderType):
        """
        Set active provider.

        Args:
            provider: "openrouter" or "google"
        """
        config = self.load()
        config.active_provider = provider
        self.save()

    def has_valid_credentials(self, provider: Optional[ProviderType] = None) -> bool:
        """
        Check if valid credentials exist for a provider.

        Args:
            provider: Provider to check, or None for active provider

        Returns:
            True if valid credentials exist
        """
        provider = provider or self.get_active_provider()

        if provider == "openrouter":
            key = self.get_openrouter_key()
            return bool(key and key.startswith("sk-or-v1-"))

        elif provider == "google":
            cred = self.get_google_oauth()
            # Need valid refresh token (access token can be refreshed)
            return bool(cred and cred.refresh_token)

        return False

    def clear_credentials(self, provider: Optional[ProviderType] = None):
        """
        Clear credentials for a provider.

        Args:
            provider: Provider to clear, or None for active provider
        """
        provider = provider or self.get_active_provider()

        if provider == "openrouter":
            cred_file = self.CREDENTIALS_DIR / "openrouter.json"
            if cred_file.exists():
                cred_file.unlink()

        elif provider == "google":
            cred_file = self.CREDENTIALS_DIR / "google.json"
            if cred_file.exists():
                cred_file.unlink()

    def get_provider_info(self) -> dict:
        """
        Get information about all providers.

        Returns:
            Dict with provider status information
        """
        return {
            "active": self.get_active_provider(),
            "openrouter": {
                "configured": self.has_valid_credentials("openrouter"),
                "key_preview": self._preview_key(self.get_openrouter_key()),
            },
            "google": {
                "configured": self.has_valid_credentials("google"),
                "email": self.get_google_oauth().email if self.get_google_oauth() else None,
                "expired": self.is_google_token_expired() if self.has_valid_credentials("google") else None,
                "source": self.get_google_credential_source(),
            },
        }

    def _preview_key(self, key: Optional[str]) -> Optional[str]:
        """Create preview of API key (first 10 + last 4 chars)"""
        if not key:
            return None
        if len(key) < 20:
            return "***"
        return f"{key[:10]}...{key[-4:]}"


# Global singleton instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    Get global ConfigManager instance.

    Returns:
        ConfigManager singleton
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
