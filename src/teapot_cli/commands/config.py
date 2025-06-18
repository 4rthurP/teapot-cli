"""Configuration management commands."""

from typing import Optional
import typer
from typing_extensions import Annotated
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
import yaml

from teapot_cli.core.config import load_config, save_config, get_config_path

app = typer.Typer()
console = Console()


@app.command()
def show() -> None:
    """Show current configuration."""
    config = load_config()
    config_dict = config.model_dump(mode="json")
    
    # Convert Path objects to strings for display
    if config_dict.get("cache_dir"):
        config_dict["cache_dir"] = str(config_dict["cache_dir"])
    
    yaml_content = yaml.dump(config_dict, default_flow_style=False)
    syntax = Syntax(yaml_content, "yaml", theme="monokai", line_numbers=True)
    
    console.print("Current configuration:")
    console.print(syntax)


@app.command()
def set(
    key: Annotated[str, typer.Argument(help="Configuration key (e.g., 'api.base_url')")],
    value: Annotated[str, typer.Argument(help="Configuration value")],
) -> None:
    """Set a configuration value."""
    config = load_config()
    
    # Handle nested keys like 'api.base_url'
    keys = key.split('.')
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
                value = value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(current_value, int):
                value = int(value)
            
            setattr(current, final_key, value)
            save_config(config)
            console.print(f"[green]Set {key} = {value}[/green]")
        else:
            console.print(f"[red]Configuration key '{key}' not found[/red]")
            raise typer.Exit(1)
    
    except (AttributeError, ValueError) as e:
        console.print(f"[red]Error setting configuration: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def get(
    key: Annotated[str, typer.Argument(help="Configuration key (e.g., 'api.base_url')")],
) -> None:
    """Get a configuration value."""
    config = load_config()
    
    # Handle nested keys like 'api.base_url'
    keys = key.split('.')
    current = config
    
    try:
        for k in keys:
            current = getattr(current, k)
        
        console.print(f"{key}: {current}")
    
    except AttributeError:
        console.print(f"[red]Configuration key '{key}' not found[/red]")
        raise typer.Exit(1)


@app.command()
def path() -> None:
    """Show the path to the configuration file."""
    config_path = get_config_path()
    console.print(f"Configuration file: {config_path}")
    
    if config_path.exists():
        console.print("[green]✅ File exists[/green]")
    else:
        console.print("[yellow]⚠️  File does not exist (will be created on first save)[/yellow]")


@app.command()
def edit() -> None:
    """Open the configuration file in the default editor."""
    config_path = get_config_path()
    
    # Ensure config file exists
    if not config_path.exists():
        config = load_config()
        save_config(config)
    
    import os
    editor = os.environ.get('EDITOR', 'nano')
    
    try:
        typer.launch(str(config_path), editor)
    except Exception as e:
        console.print(f"[red]Error opening editor: {e}[/red]")
        console.print(f"Try: {editor} {config_path}")


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