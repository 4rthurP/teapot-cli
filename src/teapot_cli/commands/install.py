"""Package installation commands."""

from typing import Optional, List
import typer
from typing_extensions import Annotated
from rich.console import Console
from rich.table import Table

from teapot_cli.core.config import load_config
from teapot_cli.core.packages import PackageManager

app = typer.Typer()
console = Console()


@app.command()
def install(
    packages: Annotated[List[str], typer.Argument(help="Package names to install")],
    version: Annotated[Optional[str], typer.Option("--version", "-v", help="Specific version to install")] = None,
) -> None:
    """Install one or more packages."""
    config = load_config()
    pm = PackageManager(config)
    
    for package_name in packages:
        success = pm.install_package(package_name, version)
        if not success:
            raise typer.Exit(1)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query for packages")],
    limit: Annotated[int, typer.Option("--limit", "-l", help="Maximum number of results")] = 10,
) -> None:
    """Search for packages."""
    config = load_config()
    pm = PackageManager(config)
    
    packages = pm.search_packages(query)
    
    if not packages:
        console.print("[yellow]No packages found.[/yellow]")
        return
    
    table = Table(title=f"Search results for '{query}'")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Description")
    
    for package in packages[:limit]:
        table.add_row(
            package.name,
            package.version or "latest",
            package.description or "No description available"
        )
    
    console.print(table)


@app.command()
def list() -> None:
    """List installed packages."""
    config = load_config()
    pm = PackageManager(config)
    
    packages = pm.list_installed()
    
    if not packages:
        console.print("[yellow]No packages installed.[/yellow]")
        return
    
    table = Table(title="Installed packages")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Description")
    
    for package in packages:
        table.add_row(
            package.name,
            package.version or "unknown",
            package.description or "No description available"
        )
    
    console.print(table)


@app.command()
def uninstall(
    packages: Annotated[List[str], typer.Argument(help="Package names to uninstall")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
) -> None:
    """Uninstall one or more packages."""
    config = load_config()
    pm = PackageManager(config)
    
    if not yes:
        package_list = ", ".join(packages)
        if not typer.confirm(f"Are you sure you want to uninstall: {package_list}?"):
            console.print("Aborted.")
            return
    
    for package_name in packages:
        success = pm.uninstall_package(package_name)
        if not success:
            raise typer.Exit(1)