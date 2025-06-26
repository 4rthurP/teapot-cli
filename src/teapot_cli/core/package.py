"""Package specific implementation."""

from rich.console import Console

from teapot_cli.core.config import TeapotConfig
from teapot_cli.core.element import TeapotElement

console = Console()


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

    @property
    def element_class(self) -> str:
        """Return the class name for this element."""
        return "TeapotPackage"

    def _perform_install(self) -> tuple[bool, str]:
        """Perform the package-specific install step.

        Returns:
            tuple[bool, str]: (success, output) - True if install succeeded

        """
        system_info = self.config.system_info

        # Check if element has custom install commands
        commands = getattr(self, "commands", None)
        if not commands:
            # Use default package manager installation
            package_manager = self.config.get_effective_package_manager()

            if not package_manager:
                return (
                    False,
                    f"No package manager detected. Installation aborted for {self.name}.",
                )

            # Build package name with version if specified
            commands = system_info.get_package_install_command(self.name)
            if not commands:
                return False, f"Unsupported package manager: {package_manager}"

        outputs = []
        for command in commands:
            if not self.config.skip_install:
                success, output = system_info.run_command(command, capture_output=True)
            outputs.append(output)
            if not success:
                return False, f"Failed to run command '{command}': {output}"

        return True, f"Successfully installed package {self.name}."

    @classmethod
    def from_dict(cls, config: TeapotConfig, data: dict) -> "TeapotPackage":
        """Create TeapotPackage from dictionary."""
        return cls(config=config, **data)
