"""File management commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from teapot_cli.core.config import load_config
from teapot_cli.core.file import TeapotFile

console = Console()

app = typer.Typer()


@app.command()
def list() -> None:
    """List all available files from API."""
    config = load_config()

    files = TeapotFile.list_available(config)

    if not files:
        console.print("[yellow]No files available.[/yellow]")
        return

    # Create table to display files
    table = Table(title=f"Available Files ({len(files)} total)")
    table.add_column("Name", style="cyan")
    table.add_column("Extension", style="magenta")
    table.add_column("Slug", style="green")

    for file_info in files:
        table.add_row(file_info["name"], file_info["extension"], file_info["slug"])

    console.print(table)


@app.command()
def get(
    slug: Annotated[
        str,
        typer.Argument(help="File slug to download content for"),
    ],
    path: Annotated[
        str | None,
        typer.Option(
            "--path",
            "-p",
            help="Directory to save file to (default: current directory)",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Custom filename to use (default: use API provided name)",
        ),
    ] = None,
) -> None:
    """Download file content by slug and save to disk."""
    config = load_config()

    # Create file instance with the slug
    file_instance = TeapotFile(config, slug=slug)

    # Download and save the file
    success = file_instance.download_and_save(path=path, filename=name)

    if not success:
        console.print(f"[red]Failed to download file with slug: {slug}[/red]")
        raise typer.Exit(1)


@app.command()
def upload(
    file_path: Annotated[
        str,
        typer.Argument(help="Path to the file to upload"),
    ],
    slug: Annotated[
        str,
        typer.Argument(help="Slug for the file to upload"),
    ],
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Custom name for the uploaded file (default: use filename)",
        ),
    ] = None,
    extension: Annotated[
        str | None,
        typer.Option(
            "--extension",
            "-e",
            help="File extension (default: auto-detect from file)",
        ),
    ] = None,
) -> None:
    """Upload a file to the API."""
    config = load_config()

    # Create file instance with custom name and extension if provided
    file_instance = TeapotFile(
        config, 
        slug=slug, 
        name=name or "", 
        extension=extension or "",
    )

    # Upload the file
    success = file_instance.upload_and_send(file_path)

    if not success:
        console.print(f"[red]Failed to upload file: {file_path}[/red]")
        raise typer.Exit(1)
