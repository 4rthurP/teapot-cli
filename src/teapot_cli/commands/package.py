"""Package management commands."""

from typing import Annotated

import typer
from rich.console import Console

from teapot_cli.core.config import load_config
from teapot_cli.core.element_manager import ElementManager

console = Console()

app = typer.Typer()


@app.command()
def install(
    packages: Annotated[
        list[str] | None,
        typer.Argument(help="Package names to install (optional if using --all)"),
    ] = None,
    *,
    all_packages: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Install all available packages for this system"
        ),
    ] = False,
) -> None:
    """Install packages using simplified workflow."""
    config = load_config()
    manager = ElementManager(config, "package")

    # Validate arguments
    if all_packages and packages:
        console.print(
            "[red]Error: Cannot specify both package names and --all flag[/red]"
        )
        raise typer.Exit(1)

    if not all_packages and not packages:
        console.print(
            "[red]Error: Must specify either package names or use --all flag[/red]"
        )
        raise typer.Exit(1)

    # Install packages
    success = manager.install_all() if all_packages else manager.install(packages)

    if not success:
        raise typer.Exit(1)


@app.command()
def uninstall(
    packages: Annotated[
        list[str],
        typer.Argument(help="Package names to uninstall"),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation"),
    ] = False,
) -> None:
    """Uninstall packages from the system."""
    config = load_config()
    manager = ElementManager(config, "package")

    success = manager.uninstall(packages, confirm=not yes)
    if not success:
        raise typer.Exit(1)


list_app = typer.Typer()


@list_app.command("installed")
def list_installed() -> None:
    """List locally installed packages."""
    config = load_config()
    manager = ElementManager(config, "package")

    installed_packages = manager.list_installed()
    if not installed_packages:
        console.print("[yellow]No packages installed.[/yellow]")
        return

    console.print("Installed packages:")
    for package_id, package_name in installed_packages.items():
        console.print(f"  {package_name} (ID: {package_id})")


@list_app.command("available")
def list_available() -> None:
    """List all available packages from API."""
    config = load_config()
    manager = ElementManager(config, "package")

    available_packages = manager.list_all_available()
    if not available_packages:
        console.print("[yellow]No packages available.[/yellow]")
        return

    console.print(f"Available packages ({len(available_packages)} total):")
    for package_name in sorted(available_packages):
        console.print(f"  📦 {package_name}")


@list_app.command("system")
def list_system() -> None:
    """List packages assigned to this system with status."""
    config = load_config()
    manager = ElementManager(config, "package")
    manager.display_system_list()


@list_app.callback(invoke_without_command=True)
def list_packages(ctx: typer.Context) -> None:
    """List packages. Defaults to showing installed packages."""
    if ctx.invoked_subcommand is None:
        list_installed()


app.add_typer(list_app, name="list", help="List packages")


@app.command()
def get(
    package: Annotated[
        str,
        typer.Argument(help="Package name to get information about"),
    ],
) -> None:
    """Get information about a specific package."""
    config = load_config()
    manager = ElementManager(config, "package")

    package_info = manager.get_info(package)
    if package_info:
        manager.display_info_table(
            [package_info], f"Information for package '{package}'"
        )
    else:
        console.print(f"Package '{package}' not found.")
        raise typer.Exit(1)
