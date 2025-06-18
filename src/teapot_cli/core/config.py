"""Configuration management for teapot-cli."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from platformdirs import user_config_dir
import yaml


class APIConfig(BaseModel):
    """API configuration settings."""
    
    base_url: str = "https://api.example.com"
    timeout: int = 30
    api_key: Optional[str] = None


class TeapotConfig(BaseSettings):
    """Main configuration for teapot-cli."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TEAPOT_",
        case_sensitive=False,
    )
    
    api: APIConfig = Field(default_factory=APIConfig)
    cache_dir: Optional[Path] = None
    verbose: bool = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.cache_dir is None:
            self.cache_dir = Path(user_config_dir("teapot-cli")) / "cache"


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    config_dir = Path(user_config_dir("teapot-cli"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def load_config() -> TeapotConfig:
    """Load configuration from file and environment variables."""
    config_path = get_config_path()
    
    if config_path.exists():
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}
    else:
        config_data = {}
    
    return TeapotConfig(**config_data)


def save_config(config: TeapotConfig) -> None:
    """Save configuration to file."""
    config_path = get_config_path()
    
    # Convert to dict and handle Path objects
    config_dict = config.model_dump(mode="json")
    if config_dict.get("cache_dir"):
        config_dict["cache_dir"] = str(config_dict["cache_dir"])
    
    with open(config_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False)