"""Status command implementation for qen.

Shows git status across all repositories (meta + sub-repos) in the current project.
Optionally includes PR information from GitHub.
"""

from dataclasses import dataclass
from pathlib import Path

import click

from ..config import QenConfigError
from ..context.runtime import RuntimeContext, RuntimeContextError
from ..git_utils import (
    GitError,
    RepoStatus,
    get_current_branch,
    get_repo_status,
    git_fetch,
)
from ..pyproject_utils import PyProjectNotFoundError, RepoConfig, load_repos_from_pyproject
from .pr import PrInfo, check_gh_installed, get_pr_info_for_branch


def build_branch_url(repo_url: str, branch: str) -> str | None:
    """Build a GitHub branch URL from repository URL and branch name.

    Args:
        repo_url: Repository URL (e.g., "https://github.com/org/repo")
        branch: Branch name (e.g., "feature-branch")

    Returns:
        Branch URL in format: https://github.com/org/repo/tree/branch
        Returns None if not a GitHub URL

    Examples:
        >>> build_branch_url("https://github.com/org/repo", "main")
        "https://github.com/org/repo/tree/main"

        >>> build_branch_url("https://github.com/org/repo/", "feature")
        "https://github.com/org/repo/tree/feature"

        >>> build_branch_url("https://github.com/org/repo.git", "dev")
        "https://github.com/org/repo/tree/dev"

        >>> build_branch_url("https://gitlab.com/org/repo", "main")
        None

        >>> build_branch_url("/local/path/repo", "main")
        None
    """
    # Only handle GitHub URLs
    if not repo_url.startswith("https://github.com/"):
        return None

    # Normalize URL: remove .git suffix first, then trailing slash
    clean_url = repo_url.removesuffix(".git").rstrip("/")

    # Build branch URL using GitHub's /tree/ path
    return f"{clean_url}/tree/{branch}"


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
    pr_infos: list[PrInfo] | None = None  # Optional PR information


def get_project_status(
    project_dir: Path, meta_path: Path, fetch: bool = False, fetch_pr: bool = False
) -> ProjectStatus:
    """Get status for all repositories in a project.

    Args:
        project_dir: Path to project directory
        meta_path: Path to meta repository
        fetch: If True, fetch before checking status
        fetch_pr: If True, fetch PR information from GitHub

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

    # Optionally fetch PR information
    pr_infos: list[PrInfo] | None = None
    if fetch_pr:
        if not check_gh_installed():
            # Silently skip PR fetching if gh is not installed
            pr_infos = None
        else:
            pr_infos = []
            for repo_config in repos:
                repo_path = repo_config.local_path(project_dir)
                if repo_path.exists():
                    pr_info = get_pr_info_for_branch(repo_path, repo_config.branch, repo_config.url)
                    pr_infos.append(pr_info)
                else:
                    # Repository not on disk
                    pr_infos.append(
                        PrInfo(
                            repo_path=str(Path(repo_config.path).name),
                            repo_url=repo_config.url,
                            branch=repo_config.branch,
                            has_pr=False,
                            error="Repository not found on disk",
                        )
                    )

    return ProjectStatus(
        project_name=project_name,
        project_dir=project_dir,
        branch=branch,
        meta_status=meta_status,
        repo_statuses=repo_statuses,
        pr_infos=pr_infos,
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

            # Use enumerate to add 1-based indices
            for idx, (repo_config, repo_status) in enumerate(status.repo_statuses, start=1):
                # Extract repo name from URL for display
                repo_display = f"{repo_config.path} ({repo_config.url})"
                lines.append(f"  [{idx}] {repo_display}")

                if not repo_status.exists:
                    lines.append("    Warning: Repository not cloned. Run 'qen add' to clone.")
                else:
                    lines.append(f"    Status: {repo_status.status_description()}")
                    # Build branch line with optional URL
                    branch_line = f"    Branch: {repo_status.branch}"
                    if repo_status.branch:
                        branch_url = build_branch_url(repo_config.url, repo_status.branch)
                        if branch_url:
                            branch_line += f" → {branch_url}"
                    lines.append(branch_line)
                    if repo_status.sync:
                        lines.append(f"    Sync:   {repo_status.sync.description()}")

                    # Show PR information if available
                    if status.pr_infos and idx <= len(status.pr_infos):
                        pr_info = status.pr_infos[idx - 1]
                        if pr_info.error:
                            lines.append(f"    PR:     Error: {pr_info.error}")
                        elif pr_info.has_pr:
                            # Format: PR: #123 (open, checks passing)
                            pr_line = f"    PR:     #{pr_info.pr_number}"
                            if pr_info.pr_state:
                                pr_line += f" ({pr_info.pr_state}"
                                if pr_info.pr_checks:
                                    pr_line += f", checks {pr_info.pr_checks}"
                                pr_line += ")"
                            # Add PR URL if available
                            if pr_info.pr_url:
                                pr_line += f" → {pr_info.pr_url}"
                            lines.append(pr_line)
                        else:
                            lines.append("    PR:     -")

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

    # Use enumerate to show indices when fetching
    for idx, repo_config in enumerate(repos, start=1):
        repo_path = repo_config.local_path(project_dir)
        if not repo_path.exists():
            if verbose:
                click.echo(f"  [{idx}] {repo_config.path} (not cloned)")
            continue

        try:
            git_fetch(repo_path)
            if verbose:
                click.echo(f"  [{idx}] ✓ {repo_config.path}")
        except GitError as e:
            if verbose:
                click.echo(f"  [{idx}] ✗ {repo_config.path} ({e})")

    if verbose:
        click.echo("")


def show_project_status(
    ctx: RuntimeContext,
    project_name: str | None = None,
    fetch: bool = False,
    fetch_pr: bool = False,
    verbose: bool = False,
    meta_only: bool = False,
    repos_only: bool = False,
) -> None:
    """Show status for current or specified project.

    Args:
        ctx: RuntimeContext with config access
        project_name: Project name (None = use current project from context)
        fetch: If True, fetch before showing status
        fetch_pr: If True, fetch PR information from GitHub
        verbose: If True, show detailed file lists
        meta_only: If True, only show meta repository
        repos_only: If True, only show sub-repositories

    Raises:
        StatusError: If status cannot be retrieved
        click.ClickException: For user-facing errors
    """
    try:
        # Determine which project to use
        if project_name:
            # Use specified project - temporarily override in context
            target_project = project_name
        else:
            # Use current project from context (handles CLI override)
            target_project = ctx.get_current_project()

        # Get project configuration
        config_service = ctx.config_service
        project_config = config_service.read_project_config(target_project)

        # Check for per-project meta repo field
        if "repo" not in project_config:
            click.echo(
                f"Error: Project '{target_project}' uses old configuration format.\n"
                f"This version requires per-project meta clones.\n"
                f"To migrate: qen init --force {target_project}",
                err=True,
            )
            raise click.Abort()

        per_project_meta = Path(project_config["repo"])
        project_dir = per_project_meta / project_config["folder"]

        # Verify project directory exists
        if not project_dir.exists():
            raise click.ClickException(f"Project directory does not exist: {project_dir}")

        # Fetch if requested
        if fetch:
            try:
                fetch_all_repos(project_dir, per_project_meta, verbose=verbose)
            except StatusError as e:
                click.echo(f"Warning: Fetch failed: {e}", err=True)

        # Get and display status
        status = get_project_status(project_dir, per_project_meta, fetch=False, fetch_pr=fetch_pr)
        output = format_status_output(
            status, verbose=verbose, meta_only=meta_only, repos_only=repos_only
        )
        click.echo(output)

    except RuntimeContextError as e:
        # User-friendly error from RuntimeContext
        raise click.ClickException(str(e)) from e
    except QenConfigError as e:
        # Config error - probably project not found
        raise click.ClickException(
            f"Project '{project_name or 'current'}' not found in qen configuration: {e}"
        ) from e
    except StatusError as e:
        # Status operation error
        raise click.ClickException(str(e)) from e


@click.command("status")
@click.option("--fetch", is_flag=True, help="Fetch from remotes before showing status")
@click.option("--pr", is_flag=True, help="Include PR information from GitHub (requires gh CLI)")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed file lists")
@click.option("--project", help="Project name (default: current project)")
@click.option("--meta-only", is_flag=True, help="Show only meta repository status")
@click.option("--repos-only", is_flag=True, help="Show only sub-repository status")
@click.pass_context
def status_command(
    ctx: click.Context,
    fetch: bool,
    pr: bool,
    verbose: bool,
    project: str | None,
    meta_only: bool,
    repos_only: bool,
) -> None:
    """Show git status across all repositories in the current project.

    Displays branch information, uncommitted changes, and sync status
    for both the meta repository and all sub-repositories.

    Use --pr to include PR information (PR#, state, check status) for each repository.

    Repositories are shown with indices ([1], [2], etc.) based on their
    order in the project configuration.

    Examples:

    \b
        # Show status for current project
        $ qen status

    \b
        # Show status with PR information
        $ qen status --pr

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
    # Get RuntimeContext from Click context
    runtime_ctx = ctx.obj.get("runtime_context")
    if not runtime_ctx:
        raise click.ClickException("RuntimeContext not available. This is a bug.")

    try:
        show_project_status(
            ctx=runtime_ctx,
            project_name=project,
            fetch=fetch,
            fetch_pr=pr,
            verbose=verbose,
            meta_only=meta_only,
            repos_only=repos_only,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
