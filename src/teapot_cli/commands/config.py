"""Configuration management commands."""

import os
from enum import Enum
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.syntax import Syntax

from teapot_cli.core.api import APIClient, APIEndpointPrivacy, APIError
from teapot_cli.core.config import get_config_path, load_config, save_config


class ConfigKey(str, Enum):
    """Valid configuration keys with dot notation."""

    API_BASE_URL = "api.base_url"
    API_TIMEOUT = "api.timeout"
    API_KEY = "api.api_key"
    SYSTEM_ID = "system.id"
    SYSTEM_NAME = "system.name"
    SYSTEM_PREFERRED_PACKAGE_MANAGER = "system.preferred_package_manager"
    AUTH_USER_ID = "auth.user_id"
    AUTH_NONCE = "auth.nonce"
    AUTH_NONCE_EXPIRATION = "auth.nonce_expiration"
    AUTH_SESSION_TOKEN = "auth.session_token"
    VERBOSITY = "verbosity"
    SKIP_INSTALL = "skip_install"


app = typer.Typer()
console = Console()


@app.command()
def show() -> None:
    """Show current configuration."""
    config = load_config()
    config_dict = config.model_dump(mode="json")

    yaml_content = yaml.dump(config_dict, default_flow_style=False)
    syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)

    console.print("Current configuration:")
    console.print(syntax)


@app.command("set")
def set_config(
    key: Annotated[ConfigKey, typer.Argument(help="Configuration key")],
    value: Annotated[str, typer.Argument(help="Configuration value")],
) -> None:
    """Set a configuration value."""
    config = load_config()

    # Handle nested keys like 'api.base_url'
    keys = key.value.split(".")
    current = config

    try:
        # Navigate to the parent of the target key
        for k in keys[:-1]:
            current = getattr(current, k)

        # Set the final key
        final_key = keys[-1]
        if hasattr(current, final_key):
            # Convert value to appropriate type based on current value
            current_value = getattr(current, final_key)
            if isinstance(current_value, bool):
                value = value.lower() in ("true", "1", "yes", "on")
            elif isinstance(current_value, int):
                value = int(value)

            setattr(current, final_key, value)
            save_config(config)
            console.print(f"[green]Set {key.value} = {value}[/green]")

            # Auto-test API connection when base_url is changed
            if key == ConfigKey.API_BASE_URL:
                test_api()
        else:
            console.print(f"[red]Configuration key '{key.value}' not found[/red]")
            raise typer.Exit(1)

    except (AttributeError, ValueError) as e:
        console.print(f"[red]Error setting configuration: {e}[/red]")
        raise typer.Exit(1) from None


@app.command("get")
def get_config(
    key: Annotated[ConfigKey, typer.Argument(help="Configuration key")],
) -> None:
    """Get a configuration value."""
    config = load_config()

    # Handle nested keys like 'api.base_url'
    keys = key.value.split(".")
    current = config

    try:
        for k in keys:
            current = getattr(current, k)

        console.print(f"{key.value}: {current}")

    except AttributeError:
        console.print(f"[red]Configuration key '{key.value}' not found[/red]")
        raise typer.Exit(1) from None


@app.command()
def path() -> None:
    """Show the path to the configuration file."""
    config_path = get_config_path()
    console.print(f"Configuration file: {config_path}")

    if config_path.exists():
        console.print(
            "[green]✅ File exists[/green]",
        )
    else:
        console.print(
            "[yellow]⚠️  File does not exist (will be created on first save)[/yellow]",
        )


@app.command()
def edit() -> None:
    """Open the configuration file in the default editor."""
    config_path = get_config_path()

    # Ensure config file exists
    if not config_path.exists():
        config = load_config()
        save_config(config)

    editor = os.environ.get("EDITOR", "nano")

    try:
        typer.launch(str(config_path), editor)
    except Exception as e:
        console.print(f"[red]Error opening editor: {e}[/red]")
        console.print(f"Try: {editor} {config_path}")


@app.command("system")
def configure_system(
    name: Annotated[str, typer.Argument(help="System name to configure")],
) -> None:
    """Configure system by name (fetches ID from API)."""
    config = load_config()

    console.print(f"Looking up system: {name}")

    with APIClient(config) as client:
        try:
            # Use existing get method directly
            response = client.get("/teapot/system/get_id", params={"name": name})
            system_id = response["data"].get("id")

            if system_id:
                # Update system configuration
                config.system.id = system_id
                config.system.name = name
                save_config(config)

                console.print(
                    f"[green]✅ System configured: {name} (ID: {system_id})[/green]",
                )
            else:
                console.print(f"[red]❌ System '{name}' not found[/red]")
                raise typer.Exit(1)

        except APIError as e:
            console.print(f"[red]Error looking up system: {e}[/red]")
            raise typer.Exit(1) from e


@app.command("test-api")
def test_api() -> None:
    """Test the API connection."""
    config = load_config()

    console.print("Testing API connection...")
    console.print(f"[dim]API URL: {config.api.base_url}[/dim]")

    with APIClient(config) as client:
        try:
            response = client.get(
                "teapot/api/test", endpoint_privacy=APIEndpointPrivacy.PUBLIC
            )
            if response.get("success", False):
                console.print("[green]✅ API connection successful[/green]")
            else:
                console.print("[red]❌ API connection failed[/red]")
                console.print(
                    "[yellow]Check your API URL and network connection[/yellow]"
                )
                raise typer.Exit(1)
        except APIError as e:
            console.print(f"[red]❌ API connection failed: {e}[/red]")
            console.print("[yellow]Check your API URL and network connection[/yellow]")
            raise typer.Exit(1) from e


@app.command("system-info")
def show_system_info() -> None:
    """Show detected system information and package manager options."""

    config = load_config()
    system_info = config.system_info

    console.print("System Information:")
    console.print(f"  Platform: {system_info.platform}")
    console.print(f"  Architecture: {system_info.architecture}")
    console.print(f"  Kernel: {system_info.kernel}")
    if system_info.distro:
        console.print(f"  Distribution: {system_info.distro}")
    console.print(f"  Shell: {system_info.shell}")
    if system_info.terminal:
        console.print(f"  Terminal: {system_info.terminal}")

    console.print("\nPackage Manager:")
    if system_info.package_manager:
        console.print(f"  Detected: {system_info.package_manager}")
    else:
        console.print("  Detected: None")

    preferred = config.system.preferred_package_manager
    if preferred:
        console.print(f"  Preferred (configured): {preferred}")
        effective = config.get_effective_package_manager()
        console.print(f"  Effective: {effective}")
    else:
        console.print("  Preferred: Not set (using detected)")

    console.print("\n[dim]To set a preferred package manager:[/dim]")
    console.print(
        "[dim]  teapot config set system.preferred_package_manager <manager>[/dim]"
    )
    console.print(
        "[dim]  Available: apt, yum, dnf, pacman, brew, zypper, apk, pkg, portage[/dim]"
    )


@app.command()
def reset() -> None:
    """Reset configuration to defaults."""
    if typer.confirm("Are you sure you want to reset all configuration to defaults?"):
        config_path = get_config_path()
        if config_path.exists():
            config_path.unlink()
        console.print("[green]Configuration reset to defaults[/green]")
    else:
        console.print("Aborted.")
