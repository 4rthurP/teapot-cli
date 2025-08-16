"""Base element management functionality."""

from abc import ABC, abstractmethod

from rich.console import Console

from teapot_cli.core.api import APIClient, APIError
from teapot_cli.core.config import (
    TeapotConfig,
    save_config,
)

console = Console()


class TeapotElement(ABC):
    """Abstract base class for individual teapot elements (single package/alias)."""

    def __init__(
        self,
        config: TeapotConfig,
        name: str,
        description: str | None = None,
        element_id: int | None = None,
        dependencies: list | None = None,
        **kwargs,
    ) -> None:
        """Initialize a single element.

        Args:
            config: Configuration object containing API settings
            name: Name of the element
            description: Element description
            element_id: Unique element ID
            dependencies: List of dependencies
            **kwargs: Additional element data

        """
        self.config = config
        self.name = name
        self.description = description
        self.id = element_id
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
            "dependencies": self.dependencies,
        }
        # Include any additional attributes (exclude config)
        for attr, value in self.__dict__.items():
            if attr not in result and attr != "config":
                result[attr] = value
        return result

    @classmethod
    def from_dict(cls, config: TeapotConfig, data: dict) -> "TeapotElement":
        """Create TeapotElement from dictionary."""
        return cls(config=config, **data)

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
        if not self.load_element_data():
            console.print(f"[red]Could not find element '{self.name}'[/red]")
            return False

        # Check if already installed
        element_storage = getattr(self.config, self.element_type_plural)
        if str(self.id) in element_storage:
            console.print(f"[yellow]{self.name} already installed[/yellow]")
            return True

        # Install if needed - show live output without progress spinner
        console.print(f"[dim]Installing {self}...[/dim]")
        
        success, error_msg = self._perform_install()

        if success:
            console.print(f"[green]✅ Successfully installed {self}[/green]")

            # Handle terminal restart for aliases
            if self.element_type == "alias" and not skip_restart:
                self.config.system_info.restart_terminal()
                console.print("[dim]Terminal configuration reloaded[/dim]")

            self._mark_as_installed()
            return True

        if error_msg.strip():
            console.print(f"[red]❌ {error_msg.strip()}[/red]")
        else:
            console.print(f"[red]❌ Failed to install {self}[/red]")

        return False

    def load_element_data(self) -> bool:
        """Load element data from API using add_or_create endpoint.

        Returns:
            bool: True if data was loaded successfully

        """
        # Already loaded
        if hasattr(self, "id") and self.id is not None:
            return True

        # Always fetch from API using add_or_create endpoint
        return self._retrieve_element_data()

    def _update_from_dict(self, data: dict) -> None:
        """Update this instance from dictionary data."""
        self.description = data.get("description")
        self.id = data.get("id")
        self.dependencies = data.get("dependencies", [])
        # Store any additional fields from API
        for key, value in data.items():
            if key not in ["name", "description", "id", "dependencies"]:
                setattr(self, key, value)

    def _retrieve_element_data(self) -> bool:
        """Search for element via API.

        Returns:
            bool: True if element data was found and loaded

        """
        with APIClient(self.config) as client:
            try:
                response = client.get(
                    f"/teapot/{self.element_type}/get_by_name",
                    params={"name": self.name},
                )  

                data = response.get("data", None)
                if not data or data == []:
                    return False
                    
                self._update_from_dict(data)
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
        element_storage[str(self.id)] = self.name
        save_config(self.config)
