"""CLI entrypoint — extend in Phase 3 (create-skill, validate, batch-register)."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, help="智维通 zhiweitong CLI")


@app.command()
def version() -> None:
    """Print package name and version placeholder."""
    typer.echo("zhiweitong 0.1.0 (scaffold)")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
