"""Alias management commands."""

from typing import Annotated

import typer
from rich.console import Console

from teapot_cli.core.config import load_config
from teapot_cli.core.element import ElementManager, TeapotAlias

console = Console()

app = typer.Typer()


@app.command()
def add(
    aliases: Annotated[list[str], typer.Argument(help="Alias names to add to system tracking")],
    version: Annotated[str | None, typer.Option("--version", "-v", help="Specific version")] = None,
) -> None:
    """Add aliases to system tracking."""
    config = load_config()
    am = TeapotAlias(config)

    success = am.add_in_system(aliases, version)
    if not success:
        raise typer.Exit(1)


@app.command()
def install(
    aliases: Annotated[
        list[str] | None, 
        typer.Argument(help="Alias names to install (optional - installs all pending if not specified)")
    ] = None,
    version: Annotated[
        str | None, 
        typer.Option("--version", "-v", help="Specific version")
    ] = None,
    all: Annotated[
        bool,
        typer.Option("--all", "-a", help="Install all aliases marked as to-install or new"),
    ] = False,
    no_update: Annotated[
        bool,
        typer.Option("--no-update", help="Skip updating from API when using --all"),
    ] = False,
) -> None:
    """Install aliases (add to system + perform install step)."""
    config = load_config()
    manager = ElementManager(config, "alias")

    # Get alias names to install
    if all or not aliases:
        alias_names = manager.get_elements_for_install(no_update)
        if not alias_names:
            console.print("[yellow]No aliases found for installation.[/yellow]")
            return
    else:
        alias_names = aliases
        # Add to system tracking first
        success = manager.add_in_system(alias_names)
        if not success:
            raise typer.Exit(1)

    # Install each alias individually (with batch restart optimization)
    is_batch = len(alias_names) > 1
    success_count = 0
    total_aliases = len(alias_names)
    
    for name in alias_names:
        alias = TeapotAlias(config, name)
        # Skip restart for batch installs (we'll restart once at the end)
        if alias.install(skip_restart=is_batch):
            success_count += 1
    
    # Single restart for batch
    if is_batch and success_count > 0:
        config.system_info.restart_terminal()
        console.print(f"[dim]Terminal configuration reloaded for {success_count} aliases[/dim]")
    
    if success_count == 0:
        console.print("[red]No aliases were installed successfully.[/red]")
        raise typer.Exit(1)
    elif success_count < total_aliases:
        console.print(f"[yellow]Installed {success_count}/{total_aliases} aliases.[/yellow]")
        raise typer.Exit(1)
    else:
        console.print(f"[green]Successfully installed {success_count} aliases.[/green]")


@app.command()
def uninstall(
    aliases: Annotated[list[str], typer.Argument(help="Alias names to uninstall")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Uninstall aliases from the system."""
    config = load_config()
    am = TeapotAlias(config)

    success = am.uninstall(aliases, confirm=not yes)
    if not success:
        raise typer.Exit(1)


@app.command()
def list(
    list_dep: Annotated[
        bool,
        typer.Option("--list-dep", help="Show dependencies"),
    ] = False,
) -> None:
    """List aliases pending installation."""
    config = load_config()
    am = TeapotAlias(config)

    aliases = am.list_in_system()
    am.display_info_table(aliases, "Aliases in system", show_dependencies=list_dep)


@app.command()
def get(
    alias: Annotated[str, typer.Argument(help="Alias name to get information about")],
) -> None:
    """Get information about a specific alias."""
    config = load_config()
    am = TeapotAlias(config)

    alias_info = am.get_info(alias)
    if alias_info:
        am.display_info_table([alias_info], f"Information for alias '{alias}'")
    else:
        console.print(f"Alias '{alias}' not found.")
        raise typer.Exit(1)
