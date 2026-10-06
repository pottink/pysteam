"""Standalone Typer wrapper for the installed ``pysteam app`` command."""

import typer

from pysteam.cli import app

main = typer.Typer(help="Inspect public PICS app info.", add_completion=False)
main.command()(app)

if __name__ == "__main__":
    main()
