"""Status command implementation for qen.

Shows git status across all repositories (meta + sub-repos) in the current project.
"""

from dataclasses import dataclass
from pathlib import Path

import click

from ..config import QenConfig, QenConfigError
from ..git_utils import (
    GitError,
    RepoStatus,
    find_meta_repo,
    get_current_branch,
    get_repo_status,
    git_fetch,
)
from ..project import ProjectNotFoundError, find_project_root
from ..pyproject_utils import PyProjectNotFoundError, RepoConfig, load_repos_from_pyproject


class StatusError(Exception):
    """Base exception for status command errors."""

    pass


@dataclass
class ProjectStatus:
    """Complete status information for a project."""

    project_name: str
    project_dir: Path
    branch: str
    meta_status: RepoStatus
    repo_statuses: list[tuple[RepoConfig, RepoStatus]]


def get_project_status(project_dir: Path, meta_path: Path, fetch: bool = False) -> ProjectStatus:
    """Get status for all repositories in a project.

    Args:
        project_dir: Path to project directory
        meta_path: Path to meta repository
        fetch: If True, fetch before checking status

    Returns:
        ProjectStatus object with all status information

    Raises:
        StatusError: If status cannot be retrieved
    """
    # Get project name from directory
    project_name = project_dir.name

    # Get branch from meta repo
    try:
        branch = get_current_branch(meta_path)
    except GitError as e:
        raise StatusError(f"Failed to get branch: {e}") from e

    # Get meta repo status
    try:
        meta_status = get_repo_status(meta_path, fetch=fetch)
    except GitError as e:
        raise StatusError(f"Failed to get meta repository status: {e}") from e

    # Load repositories from pyproject.toml
    try:
        repos = load_repos_from_pyproject(project_dir)
    except (PyProjectNotFoundError, Exception) as e:
        raise StatusError(f"Failed to load repositories: {e}") from e

    # Get status for each sub-repository
    repo_statuses: list[tuple[RepoConfig, RepoStatus]] = []
    for repo_config in repos:
        repo_path = repo_config.local_path(project_dir)
        try:
            status = get_repo_status(repo_path, fetch=fetch)
            repo_statuses.append((repo_config, status))
        except GitError:
            # If we can't get status, create a not-exists status
            repo_statuses.append((repo_config, RepoStatus(exists=False)))

    return ProjectStatus(
        project_name=project_name,
        project_dir=project_dir,
        branch=branch,
        meta_status=meta_status,
        repo_statuses=repo_statuses,
    )


def format_status_output(
    status: ProjectStatus, verbose: bool = False, meta_only: bool = False, repos_only: bool = False
) -> str:
    """Format status output for display.

    Args:
        status: ProjectStatus object
        verbose: If True, show detailed file lists
        meta_only: If True, only show meta repository
        repos_only: If True, only show sub-repositories

    Returns:
        Formatted status output
    """
    lines: list[str] = []

    # Project header (always show unless repos_only)
    if not repos_only:
        lines.append(f"Project: {status.project_name}")
        lines.append(f"Branch: {status.branch}")
        lines.append("")

    # Meta repository status (unless repos_only)
    if not repos_only:
        lines.append("Meta Repository")
        lines.append(f"  Status: {status.meta_status.status_description()}")
        lines.append(f"  Branch: {status.branch}")
        if status.meta_status.sync:
            lines.append(f"  Sync:   {status.meta_status.sync.description()}")

        # Show detailed files if verbose and there are changes
        if verbose and not status.meta_status.is_clean():
            if status.meta_status.modified:
                lines.append("  Modified files:")
                for file in status.meta_status.modified:
                    lines.append(f"    - {file}")
            if status.meta_status.staged:
                lines.append("  Staged files:")
                for file in status.meta_status.staged:
                    lines.append(f"    - {file}")
            if status.meta_status.untracked:
                lines.append("  Untracked files:")
                for file in status.meta_status.untracked:
                    lines.append(f"    - {file}")

        lines.append("")

    # Sub-repositories status (unless meta_only)
    if not meta_only:
        if status.repo_statuses:
            lines.append("Sub-repositories:")
            lines.append("")

            for repo_config, repo_status in status.repo_statuses:
                # Extract repo name from URL for display
                repo_display = f"{repo_config.path} ({repo_config.url})"
                lines.append(f"  {repo_display}")

                if not repo_status.exists:
                    lines.append("    Warning: Repository not cloned. Run 'qen add' to clone.")
                else:
                    lines.append(f"    Status: {repo_status.status_description()}")
                    lines.append(f"    Branch: {repo_status.branch}")
                    if repo_status.sync:
                        lines.append(f"    Sync:   {repo_status.sync.description()}")

                    # Show detailed files if verbose and there are changes
                    if verbose and not repo_status.is_clean():
                        if repo_status.modified:
                            lines.append("    Modified files:")
                            for file in repo_status.modified:
                                lines.append(f"      - {file}")
                        if repo_status.staged:
                            lines.append("    Staged files:")
                            for file in repo_status.staged:
                                lines.append(f"      - {file}")
                        if repo_status.untracked:
                            lines.append("    Untracked files:")
                            for file in repo_status.untracked:
                                lines.append(f"      - {file}")

                lines.append("")
        elif not repos_only:
            lines.append("Sub-repositories: (none)")
            lines.append("")

    return "\n".join(lines)


def fetch_all_repos(project_dir: Path, meta_path: Path, verbose: bool = False) -> None:
    """Fetch all repositories in a project.

    Args:
        project_dir: Path to project directory
        meta_path: Path to meta repository
        verbose: If True, show progress messages

    Raises:
        StatusError: If fetch fails
    """
    if verbose:
        click.echo("Fetching updates...")

    # Fetch meta repo
    try:
        git_fetch(meta_path)
        if verbose:
            click.echo("  ✓ meta")
    except GitError as e:
        if verbose:
            click.echo(f"  ✗ meta ({e})")

    # Load and fetch sub-repos
    try:
        repos = load_repos_from_pyproject(project_dir)
    except (PyProjectNotFoundError, Exception) as e:
        raise StatusError(f"Failed to load repositories: {e}") from e

    for repo_config in repos:
        repo_path = repo_config.local_path(project_dir)
        if not repo_path.exists():
            if verbose:
                click.echo(f"  - {repo_config.path} (not cloned)")
            continue

        try:
            git_fetch(repo_path)
            if verbose:
                click.echo(f"  ✓ {repo_config.path}")
        except GitError as e:
            if verbose:
                click.echo(f"  ✗ {repo_config.path} ({e})")

    if verbose:
        click.echo("")


def show_project_status(
    project_name: str | None = None,
    fetch: bool = False,
    verbose: bool = False,
    meta_only: bool = False,
    repos_only: bool = False,
) -> None:
    """Show status for current or specified project.

    Args:
        project_name: Project name (None = use current project)
        fetch: If True, fetch before showing status
        verbose: If True, show detailed file lists
        meta_only: If True, only show meta repository
        repos_only: If True, only show sub-repositories

    Raises:
        StatusError: If status cannot be retrieved
        click.ClickException: For user-facing errors
    """
    # Find project directory
    if project_name:
        # Load project from config
        config = QenConfig()
        try:
            project_config = config.read_project_config(project_name)
            meta_path = Path(config.read_main_config()["meta_path"])
            project_dir = meta_path / project_config["folder"]
        except QenConfigError as e:
            raise click.ClickException(
                f"Project '{project_name}' not found in qen configuration: {e}"
            ) from e
    else:
        # Use current directory
        try:
            project_dir = find_project_root()
        except ProjectNotFoundError as e:
            raise click.ClickException(str(e)) from e

        # Find meta repo
        try:
            meta_path = find_meta_repo(project_dir)
        except Exception as e:
            raise click.ClickException(f"Cannot find meta repository: {e}") from e

    # Verify project directory exists
    if not project_dir.exists():
        raise click.ClickException(f"Project directory does not exist: {project_dir}")

    # Fetch if requested
    if fetch:
        try:
            fetch_all_repos(project_dir, meta_path, verbose=verbose)
        except StatusError as e:
            click.echo(f"Warning: Fetch failed: {e}", err=True)

    # Get and display status
    try:
        status = get_project_status(project_dir, meta_path, fetch=False)
        output = format_status_output(
            status, verbose=verbose, meta_only=meta_only, repos_only=repos_only
        )
        click.echo(output)
    except StatusError as e:
        raise click.ClickException(str(e)) from e


@click.command("status")
@click.option("--fetch", is_flag=True, help="Fetch from remotes before showing status")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed file lists")
@click.option("--project", help="Project name (default: current project)")
@click.option("--meta-only", is_flag=True, help="Show only meta repository status")
@click.option("--repos-only", is_flag=True, help="Show only sub-repository status")
def status_command(
    fetch: bool, verbose: bool, project: str | None, meta_only: bool, repos_only: bool
) -> None:
    """Show git status across all repositories in the current project.

    Displays branch information, uncommitted changes, and sync status
    for both the meta repository and all sub-repositories.

    Examples:

    \b
        # Show status for current project
        $ qen status

    \b
        # Show status with fetch
        $ qen status --fetch

    \b
        # Show detailed file lists
        $ qen status --verbose

    \b
        # Show status for specific project
        $ qen status --project my-project

    \b
        # Show only meta repository
        $ qen status --meta-only

    \b
        # Show only sub-repositories
        $ qen status --repos-only
    """
    try:
        show_project_status(
            project_name=project,
            fetch=fetch,
            verbose=verbose,
            meta_only=meta_only,
            repos_only=repos_only,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
