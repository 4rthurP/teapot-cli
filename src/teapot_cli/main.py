"""Main CLI entry point for teapot-cli."""

import typer
from typing_extensions import Annotated

from teapot_cli.commands import config, install

app = typer.Typer(
    name="teapot",
    help="A CLI tool for package installation and configuration management",
    add_completion=False,
)

app.add_typer(install.app, name="install", help="Package installation commands")
app.add_typer(config.app, name="config", help="Configuration management commands")


@app.callback()
def main(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output")] = False,
) -> None:
    """Teapot CLI - Package installation and configuration management tool."""
    if verbose:
        typer.echo("Verbose mode enabled")


if __name__ == "__main__":
    app()