"""Alias management commands."""

from typing import Annotated

import typer
from rich.console import Console

from teapot_cli.core.config import load_config
from teapot_cli.core.element_manager import ElementManager

console = Console()

app = typer.Typer()


@app.command()
def install(
    aliases: Annotated[
        list[str] | None,
        typer.Argument(help="Alias names to install (optional if using --all)"),
    ] = None,
    *,
    all_aliases: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Install all available aliases for this system"
        ),
    ] = False,
) -> None:
    """Install aliases using simplified workflow."""
    config = load_config()
    manager = ElementManager(config, "alias")

    # Validate arguments
    if all_aliases and aliases:
        console.print(
            "[red]Error: Cannot specify both alias names and --all flag[/red]"
        )
        raise typer.Exit(1)

    if not all_aliases and not aliases:
        console.print(
            "[red]Error: Must specify either alias names or use --all flag[/red]"
        )
        raise typer.Exit(1)

    # Install aliases
    if all_aliases:
        success = manager.install_all()
    else:
        success = manager.install(aliases)

    if not success:
        raise typer.Exit(1)


@app.command()
def uninstall(
    aliases: Annotated[list[str], typer.Argument(help="Alias names to uninstall")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Uninstall aliases from the system."""
    config = load_config()
    manager = ElementManager(config, "alias")

    success = manager.uninstall(aliases, confirm=not yes)
    if not success:
        raise typer.Exit(1)


list_app = typer.Typer()


@list_app.command("installed")
def list_installed() -> None:
    """List locally installed aliases."""
    config = load_config()
    manager = ElementManager(config, "alias")

    installed_aliases = manager.list_installed()
    if not installed_aliases:
        console.print("[yellow]No aliases installed.[/yellow]")
        return

    console.print("Installed aliases:")
    for alias_id, alias_name in installed_aliases.items():
        console.print(f"  {alias_name} (ID: {alias_id})")


@list_app.command("available")
def list_available() -> None:
    """List all available aliases from API."""
    config = load_config()
    manager = ElementManager(config, "alias")

    available_aliases = manager.list_all_available()
    if not available_aliases:
        console.print("[yellow]No aliases available.[/yellow]")
        return

    console.print(f"Available aliases ({len(available_aliases)} total):")
    for alias_name in sorted(available_aliases):
        console.print(f"  📦 {alias_name}")


@list_app.command("system")
def list_system() -> None:
    """List aliases assigned to this system with status."""
    config = load_config()
    manager = ElementManager(config, "alias")
    manager.display_system_list()


@list_app.callback(invoke_without_command=True)
def list_aliases(ctx: typer.Context) -> None:
    """List aliases. Defaults to showing installed aliases."""
    if ctx.invoked_subcommand is None:
        list_installed()


app.add_typer(list_app, name="list", help="List aliases")


@app.command()
def get(
    alias: Annotated[str, typer.Argument(help="Alias name to get information about")],
) -> None:
    """Get information about a specific alias."""
    config = load_config()
    manager = ElementManager(config, "alias")

    alias_info = manager.get_info(alias)
    if alias_info:
        manager.display_info_table([alias_info], f"Information for alias '{alias}'")
    else:
        console.print(f"Alias '{alias}' not found.")
        raise typer.Exit(1)
