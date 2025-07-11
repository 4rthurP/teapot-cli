"""Tests for configuration management."""

from teapot_cli.core.config import APIConfig, TeapotConfig, load_config, save_config


def test_api_config_defaults():
    """Test APIConfig default values."""
    config = APIConfig()
    assert config.base_url == "https://api.example.com"
    assert config.timeout == 30
    assert config.api_key is None


def test_teapot_config_defaults():
    """Test TeapotConfig default values."""
    config = TeapotConfig()
    assert isinstance(config.api, APIConfig)
    assert config.verbosity == 0


def test_config_with_custom_values():
    """Test configuration with custom values."""
    api_config = APIConfig(
        base_url="https://custom.api.com",
        timeout=60,
        api_key="secret-key",
    )

    config = TeapotConfig(
        api=api_config,
        verbosity=2,
    )

    assert config.api.base_url == "https://custom.api.com"
    assert config.api.timeout == 60
    assert config.api.api_key == "secret-key"
    assert config.verbosity == 2


def test_config_serialization():
    """Test configuration serialization."""
    config = TeapotConfig(verbosity=1)
    config_dict = config.model_dump(mode="json")

    assert "api" in config_dict
    assert "verbosity" in config_dict
    assert config_dict["verbosity"] == 1


def test_save_and_load_config(temp_dir, monkeypatch):
    """Test saving and loading configuration."""
    config_path = temp_dir / "config.yaml"

    # Mock get_config_path to use our temp directory
    monkeypatch.setattr("teapot_cli.core.config.get_config_path", lambda: config_path)

    # Create and save a config
    original_config = TeapotConfig(verbosity=1)
    original_config.api.base_url = "https://test.com"
    save_config(original_config)

    # Load and verify
    loaded_config = load_config()
    assert loaded_config.verbosity == 1
    assert loaded_config.api.base_url == "https://test.com"


def test_load_config_nonexistent_file(temp_dir, monkeypatch):
    """Test loading config when file doesn't exist."""
    config_path = temp_dir / "nonexistent.yaml"
    monkeypatch.setattr("teapot_cli.core.config.get_config_path", lambda: config_path)

    config = load_config()
    assert isinstance(config, TeapotConfig)
    assert config.api.base_url == "https://api.example.com"  # default value
