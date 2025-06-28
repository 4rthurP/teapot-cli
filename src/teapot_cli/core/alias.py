"""Alias specific implementation."""

from rich.console import Console

from teapot_cli.core.element import TeapotElement

console = Console()


class TeapotAlias(TeapotElement):
    """Individual alias handler."""

    @property
    def element_type(self) -> str:
        """Return the element type ('alias')."""
        return "alias"

    @property
    def element_type_plural(self) -> str:
        """Return the plural form of the element type."""
        return "alias"

    @property
    def element_class(self) -> str:
        """Return the class name for this element."""
        return "TeapotAlias"

    def _perform_install(self) -> tuple[bool, str]:
        """Perform the alias-specific install step.

        Returns:
            tuple[bool, str]: (success, output) - True if install succeeded

        """
        # Get alias command from stored element data (no API call needed)
        alias_command = getattr(self, "command", None)
        if not alias_command:
            return (
                False,
                f"No command found for alias '{self.name}'. Element may be incomplete.",
            )

        # Get the shell configuration path from the system info
        system_info = self.config.system_info
        shell_type = system_info.shell
        config_path = system_info.get_shell_config_path()
        if not config_path:
            config_path.mkdir(parents=True, exist_ok=True)

        # Ensure config directory exists for fish
        if shell_type == "fish":
            config_path.parent.mkdir(parents=True, exist_ok=True)

        # Format alias command based on shell
        if shell_type == "fish":
            alias_line = f"alias {self.name} '{alias_command}'"
        else:
            alias_line = f"alias {self.name}='{alias_command}'"

        if not self.config.skip_install:
            try:
                # Check if alias already exists
                with config_path.open() as f:
                    content = f.read()
                    if f"alias {self.name}" in content:
                        # Already exists
                        return True, f"Alias {self.name} already exists."

                # Add alias to config file
                with config_path.open("a") as f:
                    f.write(f"{alias_line}\n")

            except (OSError, PermissionError):
                return False, f"Failed to write alias '{self.name}': Permission denied."
        return (
            True,
            f"Successfully installed alias '{self.name}' to {shell_type} config",
        )
