"""Command-line interface for qen.

qen - A tiny, extensible tool for organizing multi-repository development work.
"""

from pathlib import Path

import click

from . import __version__
from .commands.add import add_repository
from .commands.commit import commit_command
from .commands.config import config_command
from .commands.init import init_project, init_qen
from .commands.pr import pr_command
from .commands.pull import pull_all_repositories
from .commands.push import push_command
from .commands.sh import sh_command
from .commands.status import status_command
from .commands.workspace import workspace_command


@click.group()
@click.version_option(version=__version__, prog_name="qen")
@click.option(
    "--config-dir",
    type=click.Path(exists=False, file_okay=False, dir_okay=True, path_type=Path),
    help="Override configuration directory (default: $XDG_CONFIG_HOME/qen)",
)
@click.option(
    "--meta",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Override meta repository path",
)
@click.option(
    "--proj",
    "--project",
    "proj",
    help="Override current project name",
)
@click.pass_context
def main(ctx: click.Context, config_dir: Path | None, meta: Path | None, proj: str | None) -> None:
    """qen - Organize multi-repository development work.

    A tiny, extensible tool for managing multiple repositories within
    a meta repository structure.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_overrides"] = {
        "config_dir": config_dir,
        "meta_path": meta,
        "current_project": proj,
    }


@main.command("init")
@click.argument("project_name", required=False)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose output",
)
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm prompts (e.g., PR creation)")
@click.pass_context
def init(ctx: click.Context, project_name: str | None, verbose: bool, yes: bool) -> None:
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

    \b
        # Create a new project without PR creation prompt
        $ qen init my-project --yes

    """
    overrides = ctx.obj.get("config_overrides", {})
    if project_name is None:
        # Mode 1: Initialize qen tooling
        init_qen(
            verbose=verbose,
            storage=None,
            config_dir=overrides.get("config_dir"),
            meta_path_override=overrides.get("meta_path"),
            current_project_override=overrides.get("current_project"),
        )
    else:
        # Mode 2: Create new project
        init_project(
            project_name,
            verbose=verbose,
            yes=yes,
            storage=None,
            config_dir=overrides.get("config_dir"),
            meta_path_override=overrides.get("meta_path"),
            current_project_override=overrides.get("current_project"),
        )


@main.command("add")
@click.argument("repo")
@click.option("--branch", "-b", help="Branch to track (default: main)")
@click.option("--path", "-p", help="Local path (default: repos/<name>)")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--force", is_flag=True, help="Force re-add if repository exists")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm prompts")
@click.pass_context
def add(
    ctx: click.Context,
    repo: str,
    branch: str | None,
    path: str | None,
    verbose: bool,
    force: bool,
    yes: bool,
) -> None:
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
    overrides = ctx.obj.get("config_overrides", {})
    add_repository(
        repo,
        branch,
        path,
        verbose,
        force,
        yes,
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )


@main.command("pull")
@click.option(
    "--fetch-only",
    is_flag=True,
    help="Fetch only, don't merge (git fetch instead of git pull)",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def pull(ctx: click.Context, fetch_only: bool, verbose: bool) -> None:
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
    overrides = ctx.obj.get("config_overrides", {})
    pull_all_repositories(
        project_name=None,  # Use current project from config
        fetch_only=fetch_only,
        verbose=verbose,
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )


# Register commands
main.add_command(config_command)
main.add_command(commit_command)
main.add_command(pr_command)
main.add_command(push_command)
main.add_command(sh_command)
main.add_command(status_command)


@main.command("workspace")
@click.option(
    "--editor",
    "-e",
    type=click.Choice(["vscode", "sublime", "all"], case_sensitive=False),
    default="all",
    help="Editor type to generate workspace for (default: all)",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def workspace(ctx: click.Context, editor: str, verbose: bool) -> None:
    """Generate editor workspace files for the current project.

    Creates workspace configuration files in the workspaces/ directory
    that span all repositories in the current project.

    Supported editors:
    - vscode: VS Code (.code-workspace)
    - sublime: Sublime Text (.sublime-project)
    - all: Generate for all supported editors (default)

    Examples:

    \b
        # Generate workspaces for all editors
        $ qen workspace

    \b
        # Generate only VS Code workspace
        $ qen workspace --editor vscode

    \b
        # Generate only Sublime Text workspace
        $ qen workspace --editor sublime

    \b
        # Open VS Code workspace
        $ qen workspace
        $ code workspaces/vscode.code-workspace
    """
    overrides = ctx.obj.get("config_overrides", {})
    workspace_command(
        editor=editor,
        verbose=verbose,
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )


if __name__ == "__main__":
    main()
