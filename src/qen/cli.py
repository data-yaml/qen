"""Command-line interface for qen.

qen - A tiny, extensible tool for organizing multi-repository development work.
"""

import click

from . import __version__
from .commands.add import add_repository
from .commands.init import init_project, init_qen
from .commands.pull import pull_all_repositories


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


@main.command("add")
@click.argument("repo")
@click.option("--branch", "-b", help="Branch to track (default: main)")
@click.option("--path", "-p", help="Local path (default: repos/<name>)")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def add(repo: str, branch: str | None, path: str | None, verbose: bool) -> None:
    """Add a repository to the current project.

    REPO can be specified in three formats:

    \b
    - Full URL: https://github.com/org/repo
    - Org/repo: org/repo (assumes GitHub)
    - Repo name: repo (uses org from config)

    The repository will be cloned to the project's repos/ directory
    and added to pyproject.toml.

    Examples:

    \b
        # Add using full URL
        $ qen add https://github.com/myorg/myrepo

    \b
        # Add using org/repo format
        $ qen add myorg/myrepo

    \b
        # Add using repo name (uses org from config)
        $ qen add myrepo

    \b
        # Add with specific branch
        $ qen add myorg/myrepo --branch develop

    \b
        # Add with custom path
        $ qen add myorg/myrepo --path repos/custom-name
    """
    add_repository(repo, branch, path, verbose)


@main.command("pull")
@click.option(
    "--fetch-only",
    is_flag=True,
    help="Fetch only, don't merge (git fetch instead of git pull)",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def pull(fetch_only: bool, verbose: bool) -> None:
    """Pull or fetch all repositories in the current project.

    Retrieves current state and synchronizes all sub-repositories.
    Updates local repositories with remote changes and captures metadata
    about each repository's state.

    By default, performs git pull (fetch + merge) on all repositories.
    Use --fetch-only to only fetch remote changes without merging.

    Examples:

    \b
        # Pull all repositories (fetch + merge)
        $ qen pull

    \b
        # Fetch only, don't merge
        $ qen pull --fetch-only

    \b
        # Verbose output
        $ qen pull -v
    """
    pull_all_repositories(
        project_name=None,  # Use current project from config
        fetch_only=fetch_only,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()
