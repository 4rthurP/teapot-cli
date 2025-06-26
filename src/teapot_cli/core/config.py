"""Configuration management for teapot-cli."""

import contextlib
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from platformdirs import user_config_dir
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from teapot_cli.core.system import SystemInfo

# Verbosity level constants
VERBOSITY_QUIET = 0
VERBOSITY_BASIC = 1
VERBOSITY_DETAILED = 2
VERBOSITY_DEBUG = 3


class APIConfig(BaseModel):
    """API configuration settings."""

    base_url: str = "https://api.example.com"
    timeout: int = 30
    api_key: str | None = None


class SystemConfig(BaseModel):
    """System configuration settings."""

    id: int | None = None
    name: str | None = None
    preferred_package_manager: str | None = None


class AuthConfig(BaseModel):
    """Authentication configuration settings."""

    user_id: int | None = None
    nonce: str | None = None
    nonce_expiration: str | None = None
    session_token: str | None = None


class TeapotConfig(BaseSettings):
    """Main configuration for teapot-cli."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TEAPOT_",
        case_sensitive=False,
    )

    api: APIConfig = Field(default_factory=APIConfig)
    system: SystemConfig = Field(default_factory=SystemConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    verbosity: int = 0
    tz: None | ZoneInfo = None
    packages: dict[str, str] = Field(default_factory=dict)
    alias: dict[str, str] = Field(default_factory=dict)
    skip_install: bool = False

    # Private cached system info
    _system_info: "SystemInfo | None" = None

    def __init__(self, **kwargs) -> None:
        """Initialize TeapotConfig with default values."""
        super().__init__(**kwargs)

        # Override verbosity from environment if set (from CLI)
        if "TEAPOT_VERBOSITY" in os.environ:
            with contextlib.suppress(ValueError):
                self.verbosity = int(os.environ["TEAPOT_VERBOSITY"])

        # Adds timezone if not set
        if self.tz is None:
            self.tz = ZoneInfo(os.environ.get("TZ", "UTC"))

        # Initialize system info cache
        self._system_info = None

        # Look for the TEAPOT_SKIP_INSTALL environment variable
        if "TEAPOT_SKIP_INSTALL" in os.environ:
            self.skip_install = os.environ["TEAPOT_SKIP_INSTALL"].lower() in (
                "1",
                "true",
                "yes",
            )

    def is_verbose(self, level: int = 1) -> bool:
        """Check if verbosity is at or above the specified level."""
        return self.verbosity >= level

    @property
    def verbose(self) -> bool:
        """Backward compatibility property."""
        return self.verbosity > 0

    @property
    def system_info(self) -> "SystemInfo":
        """Get cached SystemInfo instance.

        Returns:
            SystemInfo: Cached system information instance

        """
        if self._system_info is None:
            # Import here to avoid circular imports
            self._system_info = SystemInfo()
        return self._system_info

    def get_effective_package_manager(self) -> str | None:
        """Get effective package manager from user preference and system detection.

        Returns:
            str | None: Package manager to use, or None if none available

        """
        # Use user preference if set
        if self.system.preferred_package_manager:
            return self.system.preferred_package_manager

        # Otherwise use system detection
        return self.system_info.package_manager


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    config_dir = Path(user_config_dir("teapot-cli"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def load_config() -> TeapotConfig:
    """Load configuration from file and environment variables."""
    config_path = get_config_path()

    if config_path.exists():
        with Path.open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}

    return TeapotConfig(**config_data)


def save_config(config: TeapotConfig) -> None:
    """Save configuration to file."""
    config_path = get_config_path()

    # Convert to dict for serialization
    config_dict = config.model_dump(mode="json")

    with Path.open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False)
