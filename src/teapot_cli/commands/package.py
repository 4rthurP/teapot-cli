"""Package management commands."""

from typing import Annotated

import typer
from rich.console import Console

from teapot_cli.core.config import load_config
from teapot_cli.core.element import ElementManager, TeapotPackage

console = Console()

app = typer.Typer()


@app.command()
def add(
    packages: Annotated[
        list[str],
        typer.Argument(help="Package names to add to system tracking"),
    ],
    version: Annotated[
        str | None,
        typer.Option("--version", "-v", help="Specific version"),
    ] = None,
) -> None:
    """Add packages to system tracking."""
    config = load_config()
    manager = ElementManager(config, "package")

    success = manager.add_in_system(packages, version)
    if not success:
        raise typer.Exit(1)


@app.command()
def install(
    packages: Annotated[
        list[str] | None,
        typer.Argument(
            help="Package names to install (optional - installs all pending if not specified)",  # noqa: E501
        ),
    ] = None,
    version: Annotated[
        str | None,
        typer.Option(
            "--version", "-v", help="Specific version",
        ),
    ] = None,
    *,
    all_packages: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Install all packages marked as to-install or new",
        ),
    ] = False,
    no_update: Annotated[
        bool,
        typer.Option(
            "--no-update", help="Skip updating from API when using --all",
        ),
    ] = False,
) -> None:
    """Install packages (add to system + perform install step)."""
    config = load_config()
    manager = ElementManager(config, "package")

    # Get package names to install
    if all_packages or not packages:
        package_names = manager.get_elements_for_install(no_update)
        if not package_names:
            console.print("[yellow]No packages found for installation.[/yellow]")
            return
    else:
        package_names = packages
        # Add to system tracking first
        success = manager.add_in_system(package_names, version)
        if not success:
            raise typer.Exit(1)

    # Install each package individually
    success_count = 0
    total_packages = len(package_names)
    
    for name in package_names:
        pkg = TeapotPackage(config, name)
        if pkg.install():
            success_count += 1
    
    if success_count == 0:
        console.print("[red]No packages were installed successfully.[/red]")
        raise typer.Exit(1)
    elif success_count < total_packages:
        console.print(f"[yellow]Installed {success_count}/{total_packages} packages.[/yellow]")
        raise typer.Exit(1)
    else:
        console.print(f"[green]Successfully installed {success_count} packages.[/green]")


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


@app.command("list")
def list_packages(
    list_dep: Annotated[
        bool,
        typer.Option("--list-dep", help="Show dependencies"),
    ] = False,
) -> None:
    """List packages pending installation."""
    config = load_config()
    manager = ElementManager(config, "package")

    packages = manager.list_in_system()
    manager.display_info_table(
        list(packages.values()), "Packages in system", show_dependencies=list_dep,
    )


@app.command()
def get(
    package: Annotated[
        str,
        typer.Argument(help="Package name to get information about"),
    ],
) -> None:
    """Get information about a specific package."""
    config = load_config()
    pm = TeapotPackage(config)

    package_info = pm.get_info(package)
    if package_info:
        pm.display_info_table([package_info], f"Information for package '{package}'")
    else:
        console.print(f"Package '{package}' not found.")
        raise typer.Exit(1)
