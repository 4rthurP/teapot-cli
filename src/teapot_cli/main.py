"""Main CLI entry point for teapot-cli."""

import os
from typing import Annotated

import typer
from rich.console import Console

from teapot_cli.commands import alias, config, file, package
from teapot_cli.core.api import APIClient, APIEndpointPrivacy, APIError
from teapot_cli.core.config import AuthConfig, load_config, save_config

console = Console()

app = typer.Typer(
    name="teapot",
    help="A CLI tool for package installation and configuration management",
    add_completion=False,
)

app.add_typer(package.app, name="package", help="Package management commands")
app.add_typer(alias.app, name="alias", help="Alias management commands")
app.add_typer(config.app, name="config", help="Configuration management commands")
app.add_typer(file.app, name="file", help="File management commands")


@app.command("login")
def login() -> None:
    """Login to the Teapot API."""
    config = load_config()

    if config.auth.user_id and config.auth.session_token:
        console.print(
            "[yellow]⚠️ You are already logged in. Use 'logout' to clear session.[/yellow]",
        )
        raise typer.Abort from None

    username = typer.prompt("Username")
    password = typer.prompt("Password", hide_input=True)

    console.print("Authenticating...")

    with APIClient(config) as client:
        try:
            response = client.post(
                "user/login",
                {
                    "username": username,
                    "password": password,
                },
                APIEndpointPrivacy.PUBLIC,
            )

            # Store auth data
            config.auth.user_id = response["data"]["user_id"]
            config.auth.session_token = response["data"]["session_token"]

            save_config(config)
            console.print("[green]✅ Login successful[/green]")

        except APIError as e:
            console.print(f"[red]❌ Login failed: {e}[/red]")
            raise typer.Exit(1) from e
        except KeyError as e:
            console.print(f"[red]❌ Invalid response from server: {e}[/red]")
            raise typer.Exit(1) from e
        except TypeError as e:
            console.print("[red]❌ Unexpected response format[/red]")
            raise typer.Exit(1) from e


@app.command("logout")
def logout() -> None:
    """Logout and clear authentication."""
    config = load_config()
    config.auth = AuthConfig()  # Reset to defaults
    save_config(config)
    console.print("[green]✅ Logged out successfully[/green]")


@app.callback()
def main(
    *,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            help="Enable verbose output (-v, -vv, -vvv for increasing detail)",
        ),
    ] = 0,
) -> None:
    """Teapot CLI - Package installation and configuration management tool."""
    if verbose > 0:
        level_names = ["", "basic", "detailed", "debug"]
        level_name = level_names[min(verbose, 3)]
        typer.echo(f"Verbose mode enabled (level {verbose} - {level_name})")
        # Store verbosity level in a way that command modules can access it
        os.environ["TEAPOT_VERBOSITY"] = str(verbose)


if __name__ == "__main__":
    app()
