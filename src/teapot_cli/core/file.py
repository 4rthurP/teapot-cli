"""File management functionality."""

import base64
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from teapot_cli.core.api import APIClient, APIError
from teapot_cli.core.config import TeapotConfig

console = Console()


class TeapotFile:
    """Individual file handler for downloading files from API."""

    def __init__(self, config: TeapotConfig, name: str = "", slug: str = "", extension: str = "") -> None:
        """Initialize a file instance.

        Args:
            config: Configuration object containing API settings
            name: Name of the file
            slug: Unique slug identifier for the file
            extension: File extension (with or without leading dot)

        """
        self.config = config
        self.name = name
        self.slug = slug
        self.extension = extension if extension.startswith(".") or not extension else f".{extension}"
        self.content: str | None = None

    def __str__(self) -> str:
        """String representation of the file."""
        if self.name and self.extension:
            return self.name + self.extension
        return self.name or self.slug

    @classmethod
    def list_available(cls, config: TeapotConfig) -> list[dict]:
        """List all available files from API.

        Args:
            config: Configuration object

        Returns:
            list[dict]: List of dictionaries with 'name' and 'slug' keys

        """
        with APIClient(config) as client:
            try:
                response = client.get("/teapot/file/list")
                files_data = response.get("data", [])
                return [
                    {
                        "name": file_info.get("name", ""),
                        "slug": file_info.get("slug", ""),
                        "extension": file_info.get("extension", ""),
                    }
                    for file_info in files_data
                    if file_info.get("name") and file_info.get("slug")
                ]
            except APIError as e:
                console.print(f"[red]Error fetching file list:[/red] {e}")
                return []

    def get_content(self) -> bool:
        """Fetch file content from API using slug.

        Returns:
            bool: True if content was fetched successfully

        """
        if not self.slug:
            console.print(
                "[red]Error: No slug provided for file content retrieval[/red]"
            )
            return False

        with APIClient(self.config) as client:
            try:
                response = client.get(
                    "/teapot/file/get_content",
                    params={"slug": self.slug},
                )

                file_data = response.get("data", {})
                raw_content = file_data.get("content", "")

                # Decode base64 content
                try:
                    self.content = base64.b64decode(raw_content).decode("utf-8")
                except Exception as e:
                    console.print(f"[red]Error decoding file content:[/red] {e}")
                    return False

                # Update name if provided by API and not already set
                if not self.name and file_data.get("name"):
                    self.name = file_data.get("name")
                
                # Update extension if provided by API and not already set
                if not self.extension and file_data.get("extension"):
                    extension = file_data.get("extension")
                    self.extension = extension if extension.startswith(".") or not extension else f".{extension}"

                return bool(self.content)

            except APIError as e:
                console.print(f"[red]Error fetching file content:[/red] {e}")
                return False

    def save_to_disk(
        self, path: str | None = None, filename: str | None = None
    ) -> bool:
        """Save file content to disk.

        Args:
            path: Directory to save to (default: current directory)
            filename: Custom filename (default: use self.name)

        Returns:
            bool: True if file was saved successfully

        """
        if not self.content:
            console.print(
                "[red]Error: No content to save. Call get_content() first.[/red]"
            )
            return False

        # Determine filename
        if filename:
            save_filename = filename
        elif self.name and self.extension:
            save_filename = self.name + self.extension
        elif self.name:
            save_filename = self.name
        else:
            console.print(
                "[red]Error: No filename available. Provide filename parameter.[/red]"
            )
            return False

        # Determine save path
        save_path = Path(path) if path else Path.cwd()

        # Create directory if it doesn't exist
        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            console.print(f"[red]Error creating directory {save_path}:[/red] {e}")
            return False

        # Full file path
        file_path = save_path / save_filename

        # Check if file already exists and ask for confirmation
        if file_path.exists() and not typer.confirm(
            f"File '{file_path}' already exists. Overwrite?"
        ):
            console.print("[yellow]Operation cancelled by user.[/yellow]")
            return False

        # Save content to file
        try:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(self.content)

            console.print(f"[green]File saved to:[/green] {file_path}")
            return True

        except OSError as e:
            console.print(f"[red]Error saving file to {file_path}:[/red] {e}")
            return False

    def download_and_save(
        self, path: str | None = None, filename: str | None = None
    ) -> bool:
        """Download file content and save to disk in one operation.

        Args:
            path: Directory to save to (default: current directory)
            filename: Custom filename (default: use self.name)

        Returns:
            bool: True if download and save were both successful

        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Download content
            task = progress.add_task(f"Downloading {self}", total=None)

            if not self.get_content():
                progress.update(task, description=f"❌ Failed to download {self}")
                return False

            # Save to disk
            progress.update(task, description=f"Saving {self}...")

            if self.save_to_disk(path, filename):
                progress.update(task, description=f"✅ Downloaded {self}")
                return True

            progress.update(task, description=f"❌ Failed to save {self}")
            return False

    def upload_content(self) -> bool:
        """Upload file content to API using name and content.

        Returns:
            bool: True if upload was successful

        """
        if not self.name:
            console.print("[red]Error: No file name provided for upload[/red]")
            return False

        if not self.content:
            console.print(
                "[red]Error: No content to upload. Call read_from_disk() first.[/red]"
            )
            return False

        with APIClient(self.config) as client:
            try:
                # Base64 encode the content for API transmission
                encoded_content = base64.b64encode(self.content.encode("utf-8")).decode(
                    "utf-8"
                )

                data = {
                    "name": self.name,
                    "extension": self.extension,
                    "slug": self.slug,
                    "content": encoded_content,
                }
                if self.extension:
                    data["extension"] = self.extension
                
                response = client.post(
                    "/teapot/file/put_content",
                    data=data,
                )

                if response.get("success"):
                    return True

                console.print(
                    f"[red]Upload failed:[/red] {response.get('message', 'Unknown error')}"
                )
                return False

            except APIError as e:
                console.print(f"[red]Error uploading file:[/red] {e}")
                return False

    def read_from_disk(self, file_path: str) -> bool:
        """Read file content from disk and store in self.content.

        Args:
            file_path: Path to the file to read

        Returns:
            bool: True if file was read successfully

        """
        path = Path(file_path)

        if not path.exists():
            console.print(f"[red]Error: File not found:[/red] {file_path}")
            return False

        if not path.is_file():
            console.print(f"[red]Error: Path is not a file:[/red] {file_path}")
            return False

        try:
            with path.open("r", encoding="utf-8") as f:
                self.content = f.read()

            # Set name and extension from file if not already set
            if not self.name:
                self.name = path.stem  # filename without extension
            if not self.extension:
                self.extension = path.suffix  # file extension with dot

            return True

        except OSError as e:
            console.print(f"[red]Error reading file {file_path}:[/red] {e}")
            return False
        except UnicodeDecodeError as e:
            console.print(f"[red]Error: File contains non-UTF-8 content:[/red] {e}")
            return False

    def upload_and_send(self, file_path: str) -> bool:
        """Read file from disk and upload to API in one operation.

        Args:
            file_path: Path to the file to upload

        Returns:
            bool: True if read and upload were both successful

        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Read file from disk
            task = progress.add_task(f"Reading {file_path}...", total=None)

            if not self.read_from_disk(file_path):
                progress.update(task, description=f"❌ Failed to read {file_path}")
                return False

            # Upload to API
            progress.update(task, description=f"Uploading {self.name}...")

            if self.upload_content():
                progress.update(task, description=f"✅ Uploaded {self.name}")
                return True

            progress.update(task, description=f"❌ Failed to upload {self.name}")
            return False
