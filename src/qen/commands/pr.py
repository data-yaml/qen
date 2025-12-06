"""Implementation of qen pr status command.

Enumerate and retrieve PR information across all repositories:
1. Load configuration and find current project
2. Read all repositories from pyproject.toml
3. For each repository:
   - Query gh CLI for PR information
   - Collect PR status, checks, and metadata
4. Display comprehensive PR summary
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click

from qenvy.base import QenvyBase

from ..config import QenConfig, QenConfigError
from ..git_utils import GitError, get_current_branch, is_git_repo
from ..pyproject_utils import PyProjectNotFoundError, read_pyproject


class PrCommandError(Exception):
    """Base exception for pr command errors."""

    pass


class NoActiveProjectError(PrCommandError):
    """Raised when no active project is set."""

    pass


@dataclass
class PrInfo:
    """PR information for a repository."""

    repo_path: str
    repo_url: str
    branch: str
    has_pr: bool
    pr_number: int | None = None
    pr_title: str | None = None
    pr_state: str | None = None
    pr_base: str | None = None
    pr_url: str | None = None
    pr_checks: str | None = None
    pr_mergeable: str | None = None
    pr_author: str | None = None
    pr_created_at: str | None = None
    pr_updated_at: str | None = None
    pr_commits: int | None = None
    pr_files_changed: int | None = None
    error: str | None = None


def check_gh_installed() -> bool:
    """Check if GitHub CLI (gh) is installed.

    Returns:
        True if gh is installed and accessible
    """
    try:
        subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_pr_info_for_branch(repo_path: Path, branch: str, url: str) -> PrInfo:
    """Get PR information for a branch using gh CLI.

    Args:
        repo_path: Path to repository
        branch: Branch name
        url: Repository URL

    Returns:
        PrInfo object with PR details
    """
    if not is_git_repo(repo_path):
        return PrInfo(
            repo_path=str(repo_path.name),
            repo_url=url,
            branch=branch,
            has_pr=False,
            error="Not a git repository",
        )

    # Get current branch if not in detached HEAD
    try:
        current_branch = get_current_branch(repo_path)
    except GitError as e:
        return PrInfo(
            repo_path=str(repo_path.name),
            repo_url=url,
            branch=branch,
            has_pr=False,
            error=f"Failed to get branch: {e}",
        )

    try:
        # Query PR for current branch using gh CLI
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                current_branch,
                "--json",
                "number,title,state,baseRefName,url,statusCheckRollup,mergeable,author,createdAt,updatedAt,commits,files",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            # No PR found for this branch
            return PrInfo(
                repo_path=str(repo_path.name),
                repo_url=url,
                branch=current_branch,
                has_pr=False,
            )

        pr_data = json.loads(result.stdout)

        # Parse check status
        checks = pr_data.get("statusCheckRollup", [])
        pr_checks = None
        if checks:
            check_states = [c.get("state", "").upper() for c in checks]
            if "FAILURE" in check_states or "ERROR" in check_states:
                pr_checks = "failing"
            elif "PENDING" in check_states or "IN_PROGRESS" in check_states:
                pr_checks = "pending"
            elif all(s == "SUCCESS" for s in check_states):
                pr_checks = "passing"
            else:
                pr_checks = "unknown"

        # Extract author login
        author_data = pr_data.get("author", {})
        pr_author = author_data.get("login") if isinstance(author_data, dict) else None

        # Parse commits and files
        commits_data = pr_data.get("commits", [])
        pr_commits = len(commits_data) if isinstance(commits_data, list) else None

        files_data = pr_data.get("files", [])
        pr_files_changed = len(files_data) if isinstance(files_data, list) else None

        return PrInfo(
            repo_path=str(repo_path.name),
            repo_url=url,
            branch=current_branch,
            has_pr=True,
            pr_number=pr_data.get("number"),
            pr_title=pr_data.get("title"),
            pr_state=pr_data.get("state", "").lower(),
            pr_base=pr_data.get("baseRefName"),
            pr_url=pr_data.get("url"),
            pr_checks=pr_checks,
            pr_mergeable=pr_data.get("mergeable", "").lower(),
            pr_author=pr_author,
            pr_created_at=pr_data.get("createdAt"),
            pr_updated_at=pr_data.get("updatedAt"),
            pr_commits=pr_commits,
            pr_files_changed=pr_files_changed,
        )

    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return PrInfo(
            repo_path=str(repo_path.name),
            repo_url=url,
            branch=current_branch,
            has_pr=False,
            error=f"Failed to query PR: {e}",
        )
    except Exception as e:
        return PrInfo(
            repo_path=str(repo_path.name),
            repo_url=url,
            branch=current_branch,
            has_pr=False,
            error=f"Unexpected error: {e}",
        )


def format_pr_info(pr: PrInfo, verbose: bool = False) -> str:
    """Format PR information for display.

    Args:
        pr: PrInfo object
        verbose: Include additional details

    Returns:
        Formatted string
    """
    lines = []

    # Repository header
    lines.append(f"\n📦 {pr.repo_path} ({pr.branch})")

    # Error handling
    if pr.error:
        lines.append(f"   ✗ {pr.error}")
        return "\n".join(lines)

    # No PR case
    if not pr.has_pr:
        lines.append("   • No PR for this branch")
        return "\n".join(lines)

    # PR information
    if pr.pr_number and pr.pr_title:
        lines.append(f"   📋 PR #{pr.pr_number}: {pr.pr_title}")

    if pr.pr_state:
        state_emoji = "🟢" if pr.pr_state == "open" else "🔵" if pr.pr_state == "merged" else "🔴"
        lines.append(f"   {state_emoji} State: {pr.pr_state}")

    if pr.pr_base:
        lines.append(f"   🎯 Target: {pr.pr_base}")

    # Check status
    if pr.pr_checks:
        if pr.pr_checks == "passing":
            lines.append("   ✓ Checks: passing")
        elif pr.pr_checks == "failing":
            lines.append("   ✗ Checks: failing")
        elif pr.pr_checks == "pending":
            lines.append("   ⏳ Checks: pending")
        else:
            lines.append(f"   ❓ Checks: {pr.pr_checks}")

    # Mergeable status
    if pr.pr_mergeable:
        if pr.pr_mergeable == "mergeable":
            lines.append("   ✓ Mergeable")
        elif pr.pr_mergeable == "conflicting":
            lines.append("   ✗ Has conflicts")

    # Verbose information
    if verbose:
        if pr.pr_author:
            lines.append(f"   👤 Author: {pr.pr_author}")
        if pr.pr_url:
            lines.append(f"   🔗 URL: {pr.pr_url}")
        if pr.pr_created_at:
            lines.append(f"   📅 Created: {pr.pr_created_at}")
        if pr.pr_updated_at:
            lines.append(f"   🔄 Updated: {pr.pr_updated_at}")

    return "\n".join(lines)


def pr_status_command(
    project_name: str | None = None,
    verbose: bool = False,
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
) -> list[PrInfo]:
    """Get PR status for all repositories in the current project.

    Args:
        project_name: Name of project (if None, use current project from config)
        verbose: Enable verbose output
        config_dir: Override config directory (for testing)
        storage: Override storage backend (for testing)

    Returns:
        List of PrInfo objects for all repositories

    Raises:
        NoActiveProjectError: If no project is currently active
        QenConfigError: If configuration cannot be read
        PyProjectNotFoundError: If pyproject.toml not found
    """
    # Load configuration
    config = QenConfig(config_dir=config_dir, storage=storage)

    if not config.main_config_exists():
        click.echo("Error: qen is not initialized. Run 'qen init' first.", err=True)
        raise click.Abort()

    try:
        main_config = config.read_main_config()
    except QenConfigError as e:
        click.echo(f"Error reading configuration: {e}", err=True)
        raise click.Abort() from e

    # Get current project
    current_project = main_config.get("current_project")
    if not current_project:
        click.echo(
            "Error: No active project. Create a project with 'qen init <project-name>' first.",
            err=True,
        )
        raise click.Abort()

    if verbose:
        click.echo(f"Current project: {current_project}")

    # Check if gh CLI is available
    if not check_gh_installed():
        click.echo("Error: GitHub CLI (gh) is not installed or not accessible.", err=True)
        click.echo("Install it from: https://cli.github.com/", err=True)
        raise click.Abort()

    # Get project directory
    try:
        project_config = config.read_project_config(current_project)
    except QenConfigError as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    meta_path = Path(main_config["meta_path"])
    folder = project_config["folder"]
    project_dir = meta_path / folder

    if not project_dir.exists():
        click.echo(f"Error: Project directory not found: {project_dir}", err=True)
        raise click.Abort()

    # Read repositories from pyproject.toml
    try:
        pyproject = read_pyproject(project_dir)
    except PyProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

    if not repos:
        click.echo("No repositories found in project.")
        click.echo("Add repositories with: qen add <repo>")
        return []

    # Display header
    click.echo(f"PR Status for project: {current_project}")

    # Query PR info for each repository
    pr_infos = []
    for repo_entry in repos:
        if not isinstance(repo_entry, dict):
            continue

        url = repo_entry.get("url", "")
        branch = repo_entry.get("branch", "main")
        path = repo_entry.get("path", "")

        # Construct full path to repository
        repo_path = project_dir / path

        # Check if repository exists
        if not repo_path.exists():
            pr_info = PrInfo(
                repo_path=str(Path(path).name),
                repo_url=url,
                branch=branch,
                has_pr=False,
                error="Repository not found on disk",
            )
        else:
            pr_info = get_pr_info_for_branch(repo_path, branch, url)

        pr_infos.append(pr_info)

        # Display result
        click.echo(format_pr_info(pr_info, verbose))

    # Display summary
    total = len(pr_infos)
    with_pr = sum(1 for p in pr_infos if p.has_pr)
    without_pr = total - with_pr
    errors = sum(1 for p in pr_infos if p.error)

    # PR state breakdown
    open_prs = sum(1 for p in pr_infos if p.has_pr and p.pr_state == "open")
    merged_prs = sum(1 for p in pr_infos if p.has_pr and p.pr_state == "merged")
    closed_prs = sum(1 for p in pr_infos if p.has_pr and p.pr_state == "closed")

    # Check status breakdown
    passing_checks = sum(1 for p in pr_infos if p.has_pr and p.pr_checks == "passing")
    failing_checks = sum(1 for p in pr_infos if p.has_pr and p.pr_checks == "failing")
    pending_checks = sum(1 for p in pr_infos if p.has_pr and p.pr_checks == "pending")

    click.echo("\nSummary:")
    click.echo(f"  {total} {'repository' if total == 1 else 'repositories'} checked")
    click.echo(f"  {with_pr} with PRs, {without_pr} without PRs")

    if with_pr > 0:
        states = []
        if open_prs > 0:
            states.append(f"{open_prs} open")
        if merged_prs > 0:
            states.append(f"{merged_prs} merged")
        if closed_prs > 0:
            states.append(f"{closed_prs} closed")
        if states:
            click.echo(f"  PR states: {', '.join(states)}")

        checks = []
        if passing_checks > 0:
            checks.append(f"{passing_checks} passing")
        if failing_checks > 0:
            checks.append(f"{failing_checks} failing")
        if pending_checks > 0:
            checks.append(f"{pending_checks} pending")
        if checks:
            click.echo(f"  Check status: {', '.join(checks)}")

    if errors > 0:
        click.echo(f"  {errors} {'error' if errors == 1 else 'errors'}")

    return pr_infos


@click.group(name="pr")
def pr_command() -> None:
    """Manage pull requests across repositories.

    Commands for querying and managing pull requests in all repositories
    within the current project.
    """
    pass


@pr_command.command("status")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed PR information")
def pr_status(verbose: bool) -> None:
    """Show PR status for all repositories in the current project.

    Queries GitHub CLI (gh) to retrieve PR information for each repository,
    including PR state, checks, and mergeable status.

    Requires GitHub CLI (gh) to be installed and authenticated.

    Examples:

    \b
        # Show PR status for all repos
        $ qen pr status

    \b
        # Show detailed PR information
        $ qen pr status -v
    """
    pr_status_command(verbose=verbose)
