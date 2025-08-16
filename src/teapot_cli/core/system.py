"""System detection utilities for teapot-cli."""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Literal

PackageManager = Literal[
    "apt",
    "yum",
    "dnf",
    "pacman",
    "brew",
    "zypper",
    "apk",
    "pkg",
    "portage",
]
ShellType = Literal["bash", "zsh", "omz", "fish", "tcsh", "csh", "unknown"]


class SystemInfo:
    """System information and utilities for local operations."""

    def __init__(self) -> None:
        """Initialize SystemInfo with auto-detected system properties."""
        self.platform = platform.system()
        self.distro = self._detect_distro()
        self.package_manager = self._detect_package_manager()
        self.shell = self._detect_shell()
        self.terminal = self._detect_terminal()
        self.architecture = platform.machine()
        self.kernel = platform.release()

    def _detect_package_manager(self) -> PackageManager | None:
        """Detect the system's package manager.

        Returns:
            PackageManager | None: Detected package manager or None if unknown

        """
        # Check for package managers by command availability
        managers = {
            "apt": ["apt", "apt-get"],
            "dnf": ["dnf"],
            "yum": ["yum"],
            "pacman": ["pacman"],
            "brew": ["brew"],
            "zypper": ["zypper"],
            "apk": ["apk"],
            "pkg": ["pkg"],
            "portage": ["emerge"],
        }

        for manager, commands in managers.items():
            for cmd in commands:
                if shutil.which(cmd):
                    return manager

        return None

    def _detect_distro(self) -> str | None:
        """Detect Linux distribution.

        Returns:
            str | None: Distribution name or None if unknown

        """
        # Try /etc/os-release first (standard)
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            try:
                with os_release_path.open() as f:
                    for line in f:
                        if line.startswith("ID="):
                            return line.split("=", 1)[1].strip().strip('"')
            except (OSError, IndexError):
                pass

        # Fallback to platform detection
        try:
            return platform.linux_distribution()[0].lower()
        except AttributeError:
            # platform.linux_distribution() removed in Python 3.8+
            pass

        # Try some common files as last resort
        distro_files = {
            "/etc/debian_version": "debian",
            "/etc/redhat-release": "rhel",
            "/etc/fedora-release": "fedora",
            "/etc/arch-release": "arch",
            "/etc/gentoo-release": "gentoo",
        }

        for file_path, distro in distro_files.items():
            if Path(file_path).exists():
                return distro

        return None

    def _detect_shell(self) -> ShellType:
        """Detect the current shell.

        Returns:
            ShellType: Detected shell type

        """
        # Check SHELL environment variable
        shell_path = os.environ.get("SHELL", "")
        shell_name = Path(shell_path).name if shell_path else ""

        shell_mapping = {
            "bash": "bash",
            "zsh": "zsh",
            "fish": "fish",
            "tcsh": "tcsh",
            "csh": "csh",
        }

        return shell_mapping.get(shell_name, "unknown")

    def _detect_terminal_type(self) -> str:
        """Detect terminal type for reload commands.

        Returns:
            str: Terminal type ("omz" for Oh My Zsh, "shell" for others)

        """
        # Check if Oh My Zsh is available
        if self.shell == "zsh" and shutil.which("omz"):
            return "omz"
        return "shell"

    def _detect_terminal(self) -> str | None:
        """Detect terminal emulator.

        Returns:
            str | None: Terminal name or None if unknown

        """
        # Try various environment variables
        terminal_vars = ["TERMINAL", "TERM_PROGRAM", "TERM"]

        for var in terminal_vars:
            if var in os.environ:
                return os.environ[var]

        return None

    def get_package_install_command(self, package_name: str) -> str:
        """Get the command to install a package.

        Args:
            package_name: Name of the package to install
            package_manager: Package manager to use (defaults to detected one)

        Returns:
            str: Command to install the package

        """
        pm = self.package_manager
        if not pm:
            return ""

        commands = {
            "apt": f"sudo apt install -y {package_name}",
            "yum": f"sudo yum install -y {package_name}",
            "dnf": f"sudo dnf install -y {package_name}",
            "pacman": f"sudo pacman -S --noconfirm {package_name}",
            "brew": f"brew install {package_name}",
            "zypper": f"sudo zypper install -y {package_name}",
            "apk": f"sudo apk add {package_name}",
            "pkg": f"sudo pkg install -y {package_name}",
            "portage": f"sudo emerge {package_name}",
        }

        return commands.get(pm, "")

    def get_shell_config_path(self, shell: ShellType | None = None) -> Path | None:
        """Get the path to the shell configuration file.

        Args:
            shell: The shell type (defaults to detected shell)

        Returns:
            Path | None: Path to shell config file or None if unknown

        """
        shell_type = shell or self.shell
        home = Path.home()

        config_files = {
            "bash": home / ".bashrc",
            "zsh": home / ".zshrc",
            "omz": home / ".zshrc",
            "fish": home / ".config" / "fish" / "config.fish",
            "tcsh": home / ".tcshrc",
            "csh": home / ".cshrc",
        }

        return config_files.get(shell_type)

    def restart_terminal(self) -> bool:
        """Restart or reload terminal configuration.

        Returns:
            bool: True if restart/reload was successful

        """
        terminal_type = self._detect_terminal_type()

        if terminal_type == "omz":
            # Use Oh My Zsh reload command
            success, _ = self.run_command(["omz", "reload"])
            return success
        if self.shell != "unknown":
            # Source the appropriate config file
            config_path = self.get_shell_config_path()
            if config_path and config_path.exists():
                if self.shell == "fish":
                    # Fish uses a different syntax
                    success, _ = self.run_command(
                        ["fish", "-c", f"source {config_path}"],
                    )
                elif self.shell == "omz":
                    # Oh My Zsh specific reload
                    success, _ = self.run_command(
                        ["omz", "reload"],
                    )
                else:
                    # Bash, zsh, etc.
                    success, _ = self.run_command(
                        ["source", str(config_path)],
                    )
                return success

        return False

    def run_command(self, command: str) -> tuple[bool, str]:
        """Run a system command with real-time output display and user interaction.

        Args:
            command: Command and arguments to run

        Returns:
            tuple[bool, str]: (success, empty string since output shown live)

        """
        try:
            # Use Popen to allow real-time interaction with the terminal
            # stdout=None, stderr=None, stdin=None means inherit parent's file descriptors
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=None,  # Inherit parent stdout for live display
                stderr=None,  # Inherit parent stderr for live display  
                stdin=None,   # Inherit parent stdin for user interaction
                text=True,
            )
            
            # Wait for the process to complete
            returncode = process.wait()
            
            return returncode == 0, ""

        except (subprocess.SubprocessError, FileNotFoundError) as e:
            return False, str(e)


def get_system_info() -> SystemInfo:
    """Get system information instance (backward compatibility).

    Returns:
        SystemInfo: New system information instance

    """
    return SystemInfo()
