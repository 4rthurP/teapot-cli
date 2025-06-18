"""Package management functionality."""

from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from teapot_cli.core.api import APIClient, APIError
from teapot_cli.core.config import TeapotConfig

console = Console()


class Package:
    """Represents a package."""
    
    def __init__(self, name: str, version: Optional[str] = None, description: Optional[str] = None):
        self.name = name
        self.version = version
        self.description = description
    
    def __str__(self) -> str:
        if self.version:
            return f"{self.name}=={self.version}"
        return self.name


class PackageManager:
    """Manages package operations."""
    
    def __init__(self, config: TeapotConfig):
        self.config = config
        self.cache_dir = config.cache_dir
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def search_packages(self, query: str) -> List[Package]:
        """Search for packages by name or description."""
        with APIClient(self.config) as client:
            try:
                response = client.get("/packages/search", params={"q": query})
                packages = []
                
                for pkg_data in response.get("packages", []):
                    packages.append(Package(
                        name=pkg_data["name"],
                        version=pkg_data.get("version"),
                        description=pkg_data.get("description")
                    ))
                
                return packages
            
            except APIError as e:
                console.print(f"[red]Error searching packages:[/red] {e}")
                return []
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package."""
        package = Package(package_name, version)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Installing {package}...", total=None)
            
            try:
                with APIClient(self.config) as client:
                    data = {"name": package_name}
                    if version:
                        data["version"] = version
                    
                    response = client.post("/packages/install", data=data)
                    
                    if response.get("success"):
                        progress.update(task, description=f"✅ Installed {package}")
                        console.print(f"[green]Successfully installed {package}[/green]")
                        return True
                    else:
                        error_msg = response.get("error", "Unknown error")
                        console.print(f"[red]Failed to install {package}: {error_msg}[/red]")
                        return False
            
            except APIError as e:
                console.print(f"[red]Error installing {package}:[/red] {e}")
                return False
    
    def list_installed(self) -> List[Package]:
        """List installed packages."""
        with APIClient(self.config) as client:
            try:
                response = client.get("/packages/installed")
                packages = []
                
                for pkg_data in response.get("packages", []):
                    packages.append(Package(
                        name=pkg_data["name"],
                        version=pkg_data.get("version"),
                        description=pkg_data.get("description")
                    ))
                
                return packages
            
            except APIError as e:
                console.print(f"[red]Error listing packages:[/red] {e}")
                return []
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a package."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Uninstalling {package_name}...", total=None)
            
            try:
                with APIClient(self.config) as client:
                    response = client.delete(f"/packages/{package_name}")
                    
                    if response.get("success"):
                        progress.update(task, description=f"✅ Uninstalled {package_name}")
                        console.print(f"[green]Successfully uninstalled {package_name}[/green]")
                        return True
                    else:
                        error_msg = response.get("error", "Unknown error")
                        console.print(f"[red]Failed to uninstall {package_name}: {error_msg}[/red]")
                        return False
            
            except APIError as e:
                console.print(f"[red]Error uninstalling {package_name}:[/red] {e}")
                return False