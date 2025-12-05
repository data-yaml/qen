"""Command-line interface for qen.

qen - A tiny, extensible tool for organizing multi-repository development work.
"""

import click

from . import __version__
from .commands.init import init_project, init_qen


@click.group()
@click.version_option(version=__version__, prog_name="qen")
def main() -> None:
    """qen - Organize multi-repository development work.

    A tiny, extensible tool for managing multiple repositories within
    a meta repository structure.
    """
    pass


@main.command("init")
@click.argument("project_name", required=False)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
def init(project_name: str | None, verbose: bool) -> None:
    """Initialize qen tooling or create a new project.

    Two modes:

    \b
    1. qen init
       Initialize qen by finding meta repo and extracting organization.

    \b
    2. qen init <project-name>
       Create a new project in the meta repository.

    Examples:

    \b
        # Initialize qen tooling
        $ qen init

    \b
        # Create a new project
        $ qen init my-project

    """
    if project_name is None:
        # Mode 1: Initialize qen tooling
        init_qen(verbose=verbose)
    else:
        # Mode 2: Create new project
        init_project(project_name, verbose=verbose)


if __name__ == "__main__":
    main()
