"""Base element management functionality."""

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from teapot_cli.core.api import APIClient, APIError
from teapot_cli.core.config import (
    VERBOSITY_DETAILED,
    TeapotConfig,
    save_config,
)
from teapot_cli.core.element import TeapotElement

console = Console()


class ElementManager:
    """Manager for multiple element operations."""

    def __init__(self, config: TeapotConfig, element_type: str) -> None:
        """Initialize the element manager.

        Args:
            config: Configuration object
            element_type: Type of elements to manage ('package' or 'alias')

        """
        self.element_type = element_type
        if element_type == "alias":
            self.element_type_plural = "alias"
        else:
            self.element_type_plural = f"{element_type}s"

        self.config = config

    @property
    def element_class(self):
        """Return the class for the specific element type (TeapotPackage or TeapotAlias)."""
        if self.element_type == "package":
            from teapot_cli.core.package import TeapotPackage

            return TeapotPackage
        if self.element_type == "alias":
            from teapot_cli.core.alias import TeapotAlias

            return TeapotAlias

        error_msg = f"Unknown element type: {self.element_type}"
        raise ValueError(error_msg)

    def _store_installed_element(self, element_id: str, element_name: str) -> None:
        """Store installed element as simple id -> name mapping.

        Args:
            element_id: Element ID
            element_name: Element name

        """
        element_storage = getattr(self.config, self.element_type_plural)
        element_storage[str(element_id)] = element_name
        save_config(self.config)

    def _load_element(self, element_name: str) -> TeapotElement | None:
        """Load a specific element by name using add_or_create API.

        Args:
            element_name: Name of the element to load

        Returns:
            TeapotElement | None: Loaded element or None if not found

        """
        # Always fetch from API using add_or_create endpoint
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/get_by_name",
                    params={"name": element_name},
                )
                data = response.get("data", None)
                if data is not None:
                    return self.element_class.from_dict(
                        self.config,
                        data,
                    )
            except APIError as e:
                console.print(f"[red]Error loading element {element_name}:[/red] {e}")

        return None

    def list_installed(self) -> dict[str, str]:
        """List installed elements from local storage.

        Returns:
            dict[str, str]: Dictionary of element_id -> element_name mappings

        """
        element_storage = getattr(self.config, self.element_type_plural)
        return element_storage.copy()

    def list_all_available(self) -> list[str]:
        """Fetch all available element names from API for current system.

        Returns:
            list[str]: List of element names available for the system

        """
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/list_all",
                    params={"system_id": self.config.system.id},
                )

                # Extract element names from response
                elements_data = response.get("data", {})
                return [elem.get("name") for elem in elements_data if elem.get("name")]

            except APIError as e:
                console.print(
                    f"[red]Error fetching available {self.element_type_plural}:[/red] {e}"
                )
                return []

    def list_system_assigned(self) -> tuple[list, list]:
        """Fetch elements assigned to the current system from API.

        Returns:
            list[str]: List of element names assigned to the system

        """
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/list_in_system",
                    params={"system_id": self.config.system.id},
                )

                # Extract element names from response
                response_data = response.get("data", {})
                return response_data.get("elements", []), response_data.get("dependencies", [])

            except APIError as e:
                console.print(
                    f"[red]Error fetching system {self.element_type_plural}:[/red] {e}"
                )
                return []

    def get_info(self, element_name: str) -> TeapotElement | None:
        """Get information about a specific element using add_or_create API.

        Args:
            element_name: Name of the element to query

        Returns:
            Element | None: Element information or None if not found

        """
        return self._load_element(element_name)

    def uninstall(self, element_names: list[str], *, confirm: bool = True) -> bool:
        """Uninstall elements from the system.

        Args:
            element_names: List of element names to uninstall
            confirm: Whether to show confirmation prompt

        Returns:
            bool: True if all elements were uninstalled successfully

        """
        if confirm:
            element_list = ", ".join(element_names)

            if not typer.confirm(
                f"Are you sure you want to uninstall: {element_list}?",
            ):
                console.print("Aborted.")
                return False

        success_count = 0
        element_storage = getattr(self.config, self.element_type_plural)

        for element_name in element_names:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Uninstalling {element_name}...", total=None)

                try:
                    with APIClient(self.config) as client:
                        response = client.delete(f"/{self.element_type}/{element_name}")

                        if response.get("success"):
                            progress.update(
                                task,
                                description=f"✅ Uninstalled {element_name}",
                            )
                            console.print(
                                f"[green]Successfully uninstalled {element_name}[/green]",
                            )

                            # Remove from local storage
                            element_id_to_remove = None
                            for element_id, name in element_storage.items():
                                if name == element_name:
                                    element_id_to_remove = element_id
                                    break

                            if element_id_to_remove:
                                del element_storage[element_id_to_remove]
                                save_config(self.config)

                            success_count += 1
                        else:
                            error_msg = response.get("error", "Unknown error")
                            console.print(
                                f"[red]Failed to uninstall {element_name}: {error_msg}[/red]",
                            )

                except APIError as e:
                    console.print(f"[red]Error uninstalling {element_name}:[/red] {e}")

        return success_count == len(element_names)

    def install(self, element_names: list[str], elements_data: dict | None = None) -> bool:
        """Install elements using simplified workflow.

        Args:
            element_names: List of element names to install

        Returns:
            bool: True if all elements were installed successfully

        """
        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print(
                f"[dim]🚀 Installing {len(element_names)} {self.element_type}[/dim]",
            )

        success_count = 0
        is_batch = len(element_names) > 1

        for element_name in element_names:
            if element_name in elements_data:
                # Use provided data if available
                element = elements_data[element_name]
            else:
                # Load element data from API
                element = self._load_element(element_name)
                if not element:
                    # Try installing with the default package manager
                    element = self.element_class(
                        config=self.config,
                        name=element_name,
                    )

            # Install the element
            if element.install(skip_restart=is_batch):
                success_count += 1

        # For batch alias installs, restart terminal once at the end
        if is_batch and self.element_type == "alias" and success_count > 0:
            from teapot_cli.core.system import get_system_info

            system_info = get_system_info()
            system_info.restart_terminal()
            console.print(
                f"[dim]Terminal configuration reloaded for {success_count} aliases[/dim]",
            )

        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print(
                f"[dim]📊 Installation complete: {success_count}/{len(element_names)} successful[/dim]",
            )

        return success_count == len(element_names)

    def install_all(self) -> bool:
        """Install all available elements that aren't already installed.

        Returns:
            bool: True if all elements were installed successfully

        """
        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print(
                f"[dim]🔍 Fetching all available {self.element_type_plural} for system...[/dim]"
            )

        # Get all available elements from API
        available_elements, dependencies = self.list_system_assigned()
        if not available_elements:
            console.print(
                f"[yellow]No {self.element_type_plural} available for installation.[/yellow]"
            )
            return True

        # Get currently installed elements
        installed_elements = self.list_installed()
        installed_names = set(installed_elements.values())

        # Filter out already installed elements
        elements_to_install = [
            available_elements[elem]["name"] for elem in available_elements if available_elements[elem]["name"] not in installed_names
        ]
        dependencies_to_install = [
            dep for dep in dependencies if dep not in installed_names and dep not in elements_to_install
        ]

        elements_to_install.extend(dependencies_to_install)

        if not elements_to_install:
            console.print(
                f"[green]All available {self.element_type_plural} are already installed.[/green]"
            )
            return True

        console.print(
            f"Found {len(elements_to_install)} {self.element_type_plural} to install:"
        )
        for element_name in elements_to_install:
            console.print(f"  • {element_name}")

        # Install the elements
        return self.install(elements_to_install, available_elements)

    def display_info_table(
        self,
        elements: list[TeapotElement],
        title: str,
        *,
        show_dependencies: bool = False,
    ) -> None:
        """Display elements in a formatted table.

        Args:
            elements: List of elements to display
            title: Table title
            show_dependencies: Whether to show dependencies

        """
        if not elements:
            console.print(f"[yellow]No {self.element_type} found.[/yellow]")
            return

        table = Table(title=title)
        table.add_column("Name")
        table.add_column("Description")
        if show_dependencies:
            table.add_column("Dependencies")

        for element in elements:
            row_data = [
                element.name,
                element.description or "No description available",
            ]
            if show_dependencies:
                deps = (
                    ", ".join(element.dependencies) if element.dependencies else "None"
                )
                row_data.append(deps)
            table.add_row(*row_data)

        console.print(table)

    def display_system_list(self) -> None:
        """Display system-assigned elements with installation status."""
        system_elements, dependencies = self.list_system_assigned()
        if not system_elements:
            console.print(f"[yellow]No {self.element_type_plural} assigned to this system.[/yellow]")
            return

        installed_elements = self.list_installed()
        installed_names = set(installed_elements.values())

        # Categorize elements
        installed = [system_elements[elem]["name"] for elem in system_elements if system_elements[elem]["name"] in installed_names]
        pending = [system_elements[elem]["name"] for elem in system_elements if system_elements[elem]["name"] not in installed_names]

        console.print(f"System {self.element_type_plural} ({len(system_elements)} total):")
        
        # Show installed first
        for name in installed:
            console.print(f"  [green]✅ {name}[/green] (installed)")
        
        # Show pending installation
        for name in pending:
            console.print(f"  [yellow]⏳ {name}[/yellow] (pending installation)")

        console.print(f"{len(dependencies)} dependencies associated")
        
        if pending:
            console.print(f"\n[dim]Run 'teapot {self.element_type} install --all' to install pending {self.element_type_plural}[/dim]")
