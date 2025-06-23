"""Base element management functionality."""

from abc import ABC, abstractmethod
from enum import Enum

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from teapot_cli.core.api import APIClient, APIError
from teapot_cli.core.config import (
    VERBOSITY_DEBUG,
    VERBOSITY_DETAILED,
    TeapotConfig,
    save_config,
)
from teapot_cli.core.system import get_system_info

console = Console()


class ElementStatus(Enum):
    """Enumeration for element statuses."""

    INSTALLED = "installed"
    TO_INSTALL = "to-install"
    NEW = "new"


class TeapotElement(ABC):
    """Abstract base class for individual teapot elements (single package/alias)."""

    def __init__(
        self,
        config: TeapotConfig,
        name: str,
        description: str | None = None,
        element_id: int | None = None,
        status: ElementStatus = ElementStatus.NEW,
        dependencies: list | None = None,
        **kwargs,
    ) -> None:
        """Initialize a single element.

        Args:
            config: Configuration object containing API settings
            name: Name of the element
            description: Element description
            element_id: Unique element ID
            status: Element status
            dependencies: List of dependencies
            **kwargs: Additional element data

        """
        self.config = config
        self.name = name
        self.description = description
        self.id = element_id
        self.status = status
        self.dependencies = dependencies or []
        # Store any additional fields from API
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self) -> str:
        """Representation of the element."""
        return self.name

    def to_dict(self) -> dict:
        """Convert element to dictionary for storage."""
        result = {
            "name": self.name,
            "description": self.description,
            "id": self.id,
            "status": self.status,
            "dependencies": self.dependencies,
        }
        # Include any additional attributes (exclude config)
        for attr, value in self.__dict__.items():
            if attr not in result and attr != "config":
                result[attr] = value
        return result

    @classmethod
    def from_dict(cls, config: TeapotConfig, data: dict) -> "TeapotElement":
        """Create element from dictionary."""
        # This is an abstract method that concrete classes should override
        raise NotImplementedError("Subclasses must implement from_dict")

    @property
    @abstractmethod
    def element_type(self) -> str:
        """Return the element type ('package' or 'alias')."""

    @property
    @abstractmethod
    def element_type_plural(self) -> str:
        """Return the plural form of the element type."""

    @abstractmethod
    def _perform_install(self) -> tuple[bool, str]:
        """Perform element-specific installation logic.

        Args:
            element: Element object containing installation data
            skip_restart: Whether to skip terminal restart (for aliases)

        Returns:
            bool: True if installation succeeded

        """

    def install(self, *, skip_restart: bool = False) -> bool:
        """Install this element.

        Args:
            skip_restart: Whether to skip terminal restart (for aliases)

        Returns:
            bool: True if installation succeeded

        """
        # Load element data if not already loaded
        if not self._load_element_data():
            console.print(f"[red]Could not find element '{self.name}'[/red]")
            return False

        # Check status
        if self.status == ElementStatus.INSTALLED:
            console.print(f"[yellow]{self.name} already installed[/yellow]")
            return True

        # Install if needed
        success: bool = True
        output: str = ""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Installing {self}",
                total=None,
            )

            if not self.config.skip_install:
                success, output = self._perform_install()

            if success:
                progress.update(task, description=f"✅ Installed {self}")
                if output.strip():
                    console.print(f"[green]{output.strip()}[/green]")
                else:
                    console.print(f"[green]Successfully installed {self}[/green]")

                # Handle terminal restart for aliases
                if self.element_type == "alias" and not skip_restart:
                    self.config.system_info.restart_terminal()
                    console.print("[dim]Terminal configuration reloaded[/dim]")

                self._mark_as_installed()
                return True

            if output.strip():
                console.print(f"[red]Error: {output.strip()}[/red]")
            else:
                console.print(f"[red]Failed to install {self}[/red]")

        return False

    def _load_element_data(self) -> bool:
        """Load element data from config or search via API.

        Returns:
            bool: True if data was loaded successfully

        """
        # Already loaded
        if hasattr(self, 'id') and self.id is not None:
            return True

        # Check config first
        element_storage = getattr(self.config, self.element_type_plural)
        for element_data in element_storage.values():
            if element_data.get("name") == self.name:
                self._update_from_dict(element_data)
                return True

        # Search via API if not in config
        return self._retrieve_element_data()

    def _update_from_dict(self, data: dict) -> None:
        """Update this instance from dictionary data."""
        self.description = data.get("description")
        self.id = data.get("id")
        self.status = ElementStatus(data.get("status", "new"))
        self.dependencies = data.get("dependencies", [])
        # Store any additional fields from API
        for key, value in data.items():
            if key not in ["name", "description", "id", "status", "dependencies"]:
                setattr(self, key, value)

    def _retrieve_element_data(self) -> bool:
        """Search for element via API.

        Returns:
            bool: True if element data was found and loaded

        """
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/add_or_create",
                    params={"name": self.name},
                )

                if "element" in response:
                    element_data = response["element"]
                    element_data["status"] = "new"  # Mark as new since not in config
                    self._update_from_dict(element_data)
                    return True

            except APIError as e:
                if self.config.is_verbose():
                    console.print(
                        f"[yellow]Could not search for {self.name}: {e}[/yellow]",
                    )
        return False

    def _mark_as_installed(self) -> None:
        """Mark element as installed in local storage."""
        element_storage = getattr(self.config, self.element_type_plural)

        # Find element by name and mark as installed
        for element_data in element_storage.values():
            if element_data.get("name") == self.name:
                element_data["status"] = "installed"
                save_config(self.config)
                break


class ElementManager:
    """Manager for multiple element operations."""

    def __init__(self, config: TeapotConfig, element_type: str) -> None:
        """Initialize the element manager.

        Args:
            config: Configuration object
            element_type: Type of elements to manage ('package' or 'alias')

        """
        self.config = config
        self.element_type = element_type
        if element_type == "alias":
            self.element_type_plural = "aliases"
        else:
            self.element_type_plural = f"{element_type}s"
        self.cache_dir = config.cache_dir
        if self.cache_dir:
            if self.config.is_verbose(VERBOSITY_DEBUG):
                console.print(
                    f"[dim]📁 Creating cache directory: {self.cache_dir}[/dim]",
                )
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_elements_for_install(self, *, no_update: bool = False) -> list[str]:
        """Get element names that need installation.

        Args:
            no_update: Skip updating from API

        Returns:
            list[str]: List of element names to install

        """
        if not no_update:
            # Refresh from API first
            if self.config.is_verbose(VERBOSITY_DEBUG):
                console.print(
                    f"[dim]  Updating {self.element_type} list from API[/dim]",
                )
            self.list_in_system()

        # Get elements marked for installation
        stored_elements = self._get_stored_elements()
        return [
            elem.name
            for elem in stored_elements
            if elem.status in ["to-install", "new"]
        ]


    def add_in_system(
        self, element_names: list[str], version: str | None = None,
    ) -> bool:
        """Add elements to system tracking.

        Args:
            element_names: List of element names to add
            version: Optional version specification

        Returns:
            bool: True if all elements were added successfully

        """
        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print(
                f"[dim]📥 Adding {len(element_names)} {self.element_type} to system tracking[/dim]",  # noqa: E501
            )

        if self.config.is_verbose(VERBOSITY_DEBUG):
            console.print(f"[dim]  Elements: {element_names}[/dim]")
            if version:
                console.print(f"[dim]  Version constraint: {version}[/dim]")

        with APIClient(self.config) as client:
            try:
                data = {"names": element_names}
                if version:
                    data["version"] = version

                response = client.post(
                    f"/teapot/{self.element_type}/add_in_system", data=data,
                )

                if response.get("success"):
                    element_list = ", ".join(element_names)
                    console.print(
                        f"[green]Successfully added {element_list} to system tracking[/green]",  # noqa: E501
                    )
                    return True

                error_msg = response.get("error", "Unknown error")
                console.print(f"[red]Failed to add elements: {error_msg}[/red]")

            except APIError as e:
                console.print(f"[red]Error adding elements:[/red] {e}")
                return False
            else:
                return False

    def _store_elements(
        self, elements_data: list[dict], dependencies_data: list[dict] | None = None,
    ) -> None:
        """Store elements in config with status tracking.

        Args:
            elements_data: List of element data from API
            dependencies_data: List of dependency data from API

        """
        element_storage = getattr(self.config, self.element_type_plural)

        # Process main elements
        for element_data in elements_data:
            element_id = element_data.get("id")
            element_name = element_data.get("name")

            if not element_id or not element_name:
                continue

            # Check if element already exists
            existing = element_storage.get(str(element_id))
            if existing:
                # Update existing element if needed
                for key, value in element_data.items():
                    if key in existing and existing[key] != value:
                        existing[key] = value
                # Preserve status if already set, otherwise set to "to-install"
                if "status" not in existing:
                    existing["status"] = "to-install"
            else:
                # Add new element
                element_data["status"] = "new"
                element_storage[str(element_id)] = element_data

        # Process dependencies if provided
        if dependencies_data:
            for dep_data in dependencies_data:
                dep_id = dep_data.get("id")
                dep_name = dep_data.get("name")

                if not dep_id or not dep_name:
                    continue

                existing_dep = element_storage.get(str(dep_id))
                if existing_dep:
                    # Update existing dependency
                    for key, value in dep_data.items():
                        if key in existing_dep and existing_dep[key] != value:
                            existing_dep[key] = value
                else:
                    # Add new dependency
                    dep_data["status"] = "to-install"
                    element_storage[str(dep_id)] = dep_data

        save_config(self.config)

    def list_in_system(self) -> dict[str, Element]:
        """List elements from system, store locally, and return cached elements.

        Returns:
            list[Element]: List of elements with their current status

        """
        # First try to fetch from API and update local storage
        try:
            with APIClient(self.config) as client:
                response = client.get(
                    f"/teapot/{self.element_type_plural}/list_in_system",
                    {"system_id": self.config.system.id},
                )

                # Extract elements and dependencies from response
                elements_data = response.get(self.element_type_plural, [])
                dependencies_data = response.get("dependencies", [])

                # Store in config
                self._store_elements(elements_data, dependencies_data)

        except APIError as e:
            if self.config.is_verbose():
                console.print(
                    f"[yellow]Warning: Could not fetch from API: {e}[/yellow]",
                )

        # Return elements from local storage
        return self._get_stored_elements()

    def _get_stored_elements(
        self,
        element_status: str | list[ElementStatus] | None = None,
    ) -> dict[str, Element]:
        """Get elements from local storage.

        Args:
            element_status: Filter elements by status (e.g. "installed", "to-install")

        Returns:
            list[Element]: List of stored elements

        """
        if isinstance(element_status, str):
            element_status = [element_status]

        element_storage = getattr(self.config, self.element_type_plural)
        return {
            element_data.get("name"): Element.from_dict(element_data)
            for element_data in element_storage.values()
            if element_status is None or element_data.get("status") in element_status
        }

    def _mark_element_installed(self, element_name: str) -> None:
        """Mark an element as installed in local storage.

        Args:
            element_name: Name of the element to mark as installed

        """
        element_storage = getattr(self.config, self.element_type_plural)

        # Find element by name and mark as installed
        for element_data in element_storage.values():
            if element_data.get("name") == element_name:
                element_data["status"] = "installed"
                save_config(self.config)
                break

    def get_info(self, element_name: str) -> Element | None:
        """Get information about a specific element.

        Args:
            element_name: Name of the element to query

        Returns:
            Element | None: Element information or None if not found

        """
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/info/{element_name}",
                )

                if "element" in response:
                    element_data = response["element"]
                    return Element(
                        name=element_data["name"],
                        version=element_data.get("version"),
                        description=element_data.get("description"),
                    )

            except APIError as e:
                console.print(f"[red]Error getting element info:[/red] {e}")

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
                                task, description=f"✅ Uninstalled {element_name}",
                            )
                            console.print(
                                f"[green]Successfully uninstalled {element_name}[/green]",  # noqa: E501
                            )
                            success_count += 1
                        else:
                            error_msg = response.get("error", "Unknown error")
                            console.print(
                                f"[red]Failed to uninstall {element_name}: {error_msg}[/red]",  # noqa: E501
                            )

                except APIError as e:
                    console.print(f"[red]Error uninstalling {element_name}:[/red] {e}")

        return success_count == len(element_names)

    def install(
        self,
        element_names: list[str] | None = None,
        *,
        install_all: bool = False,
        no_update: bool = False,
    ) -> bool:
        """Install elements (add to system + perform install step).

        Args:
            element_names: List of element names to install, or None to install all pending
            install_all: Install all elements marked as to-install or new
            no_update: Skip updating from API when using install_all

        Returns:
            bool: True if all elements were installed successfully

        """
        if self.config.is_verbose(VERBOSITY_DETAILED):
            if install_all:
                console.print(
                    f"[dim]🚀 Installing all {self.element_type} marked for installation[/dim]",  # noqa: E501
                )
            else:
                console.print(
                    f"[dim]🚀 Installing {len(element_names)} {self.element_type}[/dim]",  # noqa: E501
                )


        # Handle --all flag
        if install_all:
            if not no_update:
                # Refresh from API first
                if self.config.is_verbose(VERBOSITY_DEBUG):
                    console.print(
                        f"[dim]  Updating {self.element_type} list from API[/dim]",
                    )
                self.list_in_system()

            # Get elements marked for installation
            elements_to_install_in_system = [
                elem for elem in stored_elements if elem.status in ["to-install", "new"]
            ]

            if not elements_to_install_in_system:
                console.print(
                    f"[yellow]No {self.element_type} marked for installation.[/yellow]",
                )
                return True

            # Display elements that will be installed
            console.print(
                f"Found {len(elements_to_install_in_system)} {self.element_type} to install:",  # noqa: E501
            )
            self.display_info_table(
                elements_to_install_in_system, f"{self.element_type.title()} to install",  # noqa: E501
            )

            element_names = [elem.name for elem in elements_to_install_in_system]

        stored_elements = self._get_stored_elements()

        if not install_all:
            for element_name in element_names:
                if element_name in stored_elements:
                    elements_to_install_in_system.append(stored_by_name[element_name])
                else:
                    # Create a minimal Element object for elements not in storage
                    new_element = Element(name=element_name)
                    elements_to_install_in_system.append(new_element)

        # Get Element objects for installation
        else:
            # Need to find Element objects for the specified names
            stored_elements = self._get_stored_elements()
            stored_by_name = {elem.name: elem for elem in stored_elements}


        # Perform install step for each element
        if self.config.is_verbose(VERBOSITY_DEBUG):
            console.print(
                f"[dim]  Beginning installation process for {len(elements_to_install_in_system)} elements[/dim]",  # noqa: E501
            )

        success_count = 0
        is_batch = len(elements_to_install_in_system) > 1

        for element in elements_to_install_in_system:
            # Skip restart for batch installs (we'll restart once at the end)
            if self.perform_install(element, skip_restart=is_batch):
                success_count += 1

        # For batch alias installs, restart terminal once at the end
        if is_batch and self.element_type == "alias" and success_count > 0:
            system_info = get_system_info()
            system_info.restart_terminal()
            console.print(
                f"[dim]Terminal configuration reloaded for {success_count} aliases[/dim]",  # noqa: E501
            )

        if self.config.is_verbose(VERBOSITY_DETAILED):
            console.print(
                f"[dim]📊 Installation complete: {success_count}/{len(elements_to_install_in_system)} successful[/dim]",  # noqa: E501
            )

        return success_count == len(elements_to_install_in_system)

    def display_info_table(
        self, elements: list[Element], title: str, *, show_dependencies: bool = False,
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
        table.add_column("Version")
        table.add_column("Status")
        table.add_column("Description")
        if show_dependencies:
            table.add_column("Dependencies")

        # Filter elements: main elements vs dependencies
        main_elements = [e for e in elements if not self._is_dependency(e)]
        dep_elements = [e for e in elements if self._is_dependency(e)]

        # Show main elements first
        for element in main_elements:
            status_color = self._get_status_color(element.status)
            row_data = [
                element.name,
                element.version or "unknown",
                f"[{status_color}]{element.status}[/{status_color}]",
                element.description or "No description available",
            ]
            if show_dependencies:
                deps = (
                    ", ".join(element.dependencies) if element.dependencies else "None"
                )
                row_data.append(deps)
            table.add_row(*row_data)

        # Show dependencies if requested
        if show_dependencies and dep_elements:
            table.add_section()
            table.add_row(
                "[bold]DEPENDENCIES[/bold]", "", "", "", "",
            )
            for dep in dep_elements:
                status_color = self._get_status_color(dep.status)
                row_data = [
                    f"  └─ {dep.name}",
                    dep.version or "unknown",
                    f"[{status_color}]{dep.status}[/{status_color}]",
                    dep.description or "No description available",
                ]
                if show_dependencies:
                    row_data.append("")
                table.add_row(*row_data)

        console.print(table)

    def _get_status_color(self, status: str) -> str:
        """Get color for status display.

        Args:
            status: Element status

        Returns:
            str: Color name for rich formatting

        """
        color_map = {
            "installed": "green",
            "to-install": "yellow",
            "new": "blue",
        }
        return color_map.get(status, "white")

    def _is_dependency(self, element: Element) -> bool:
        """Check if element is a dependency.

        Args:
            element: Element to check

        Returns:
            bool: True if element is a dependency

        """
        # This is a simple heuristic - you might want to track this differently
        # For now, assume elements marked as dependencies have a special attribute
        return getattr(element, "is_dependency", False)


class TeapotPackage(TeapotElement):
    """Individual package handler."""

    @property
    def element_type(self) -> str:
        """Return the element type ('package')."""
        return "package"

    @property
    def element_type_plural(self) -> str:
        """Return the plural form of the element type."""
        return "packages"

    def _perform_install(self) -> tuple[bool, str]:
        """Perform the package-specific install step.

        Returns:
            tuple[bool, str]: (success, output) - True if install succeeded

        """
        system_info = self.config.system_info
        package_manager = self.config.get_effective_package_manager()

        if not package_manager:
            return (
                False,
                f"No package manager detected. Please install {self.name} manually.",
            )

        # Build package name with version if specified
        command = system_info.get_package_install_command(self.name)
        if not command:
            return False, f"Unsupported package manager: {package_manager}"

        return system_info.run_command(command, capture_output=True)

    @classmethod
    def from_dict(cls, config: TeapotConfig, data: dict) -> "TeapotPackage":
        """Create TeapotPackage from dictionary."""
        return cls(config=config, **data)

class TeapotAlias(TeapotElement):
    """Individual alias handler."""

    @property
    def element_type(self) -> str:
        """Return the element type ('alias')."""
        return "alias"

    @property
    def element_type_plural(self) -> str:
        """Return the plural form of the element type."""
        return "aliases"

    def _perform_install(self) -> tuple[bool, str]:
        """Perform the alias-specific install step.

        Returns:
            tuple[bool, str]: (success, output) - True if install succeeded

        """
        system_info = self.config.system_info
        # Get alias command from stored element data (no API call needed)
        alias_command = getattr(self, "command", None)

        if not alias_command:
            return (
                False,
                f"No command found for alias '{self.name}'. Element may be incomplete.",
            )

        success, output = system_info.add_alias_to_shell(self.name, alias_command)
        return success, output

    @classmethod
    def from_dict(cls, config: TeapotConfig, data: dict) -> "TeapotAlias":
        """Create TeapotAlias from dictionary."""
        return cls(config=config, **data)
