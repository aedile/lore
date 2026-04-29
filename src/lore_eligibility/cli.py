"""Command-line interface entry point for lore-eligibility."""

from __future__ import annotations

import click

from lore_eligibility import __version__


@click.group()
@click.version_option(version=__version__, prog_name="lore-eligibility")
def cli() -> None:
    """lore-eligibility — eligibility data ingestion, cleansing, and identity verification."""


@cli.command()
def version() -> None:
    """Print the installed package version."""
    click.echo(__version__)
