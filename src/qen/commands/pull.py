"""Implementation of qen pull command.

Pull or fetch all repositories in the current project:
1. Load configuration and find current project
2. Read all repositories from pyproject.toml
3. For each repository:
   - Fetch or pull from remote
   - Update metadata (branch, updated, pr, pr_base, issue)
   - Detect PR/issue associations via gh CLI
4. Display comprehensive summary
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from qenvy.base import QenvyBase

from ..config import QenConfigError
from ..git_utils import GitError, get_current_branch, is_git_repo, run_git_command
from ..init_utils import ensure_correct_branch, ensure_initialized
from ..pr_utils import parse_check_status
from ..pyproject_utils import PyProjectNotFoundError, PyProjectUpdateError, read_pyproject


class PullCommandError(Exception):
    """Base exception for pull command errors."""

    pass


class NoActiveProjectError(PullCommandError):
    """Raised when no active project is set."""

    pass


class RepoStateError(PullCommandError):
    """Raised when repository is in invalid state."""

    pass


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


def get_pr_info(repo_path: Path, branch: str) -> dict[str, Any]:
    """Get PR information for a branch using gh CLI.

    Args:
        repo_path: Path to repository
        branch: Branch name

    Returns:
        Dictionary with pr, pr_base, pr_status, pr_checks fields (all optional)
    """
    info: dict[str, Any] = {}

    try:
        # Query PR for current branch
        result = subprocess.run(
            ["gh", "pr", "view", branch, "--json", "number,baseRefName,state,statusCheckRollup"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            import json

            pr_data = json.loads(result.stdout)
            info["pr"] = pr_data.get("number")
            info["pr_base"] = pr_data.get("baseRefName")
            info["pr_status"] = pr_data.get("state", "").lower()

            # Parse check status using shared utility
            checks = pr_data.get("statusCheckRollup", [])
            info["pr_checks"] = parse_check_status(checks)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError):
        # If gh command fails, just skip PR info
        pass

    return info


def get_issue_info(repo_path: Path, branch: str) -> int | None:
    """Get issue number from branch name or PR.

    Args:
        repo_path: Path to repository
        branch: Branch name

    Returns:
        Issue number if detected, None otherwise
    """
    # Try to extract issue number from branch name (e.g., issue-123, fix/issue-456)
    import re

    match = re.search(r"issue[_-](\d+)", branch, re.IGNORECASE)
    if match:
        return int(match.group(1))

    # TODO: Could also query gh to find linked issues in the PR
    return None


def is_detached_head(repo_path: Path) -> bool:
    """Check if repository is in detached HEAD state.

    Args:
        repo_path: Path to repository

    Returns:
        True if in detached HEAD state
    """
    try:
        branch = get_current_branch(repo_path)
        return branch == "HEAD"
    except GitError:
        return True


def has_remote(repo_path: Path, remote: str = "origin") -> bool:
    """Check if repository has a remote configured.

    Args:
        repo_path: Path to repository
        remote: Remote name (default: origin)

    Returns:
        True if remote exists
    """
    try:
        run_git_command(["remote", "get-url", remote], cwd=repo_path)
        return True
    except GitError:
        return False


def git_fetch(repo_path: Path, verbose: bool = False) -> tuple[bool, str]:
    """Fetch from remote.

    Args:
        repo_path: Path to repository
        verbose: Enable verbose output

    Returns:
        Tuple of (success, message)
    """
    try:
        if verbose:
            run_git_command(["fetch", "origin", "-v"], cwd=repo_path)
        else:
            run_git_command(["fetch", "origin"], cwd=repo_path)
        return (True, "Fetched successfully")
    except GitError as e:
        return (False, str(e))


def git_pull(repo_path: Path, verbose: bool = False) -> tuple[bool, str, dict[str, Any]]:
    """Pull from remote (fetch + merge).

    Args:
        repo_path: Path to repository
        verbose: Enable verbose output

    Returns:
        Tuple of (success, message, stats_dict)
        stats_dict contains: commits_pulled, files_changed, has_conflicts
    """
    stats: dict[str, Any] = {
        "commits_pulled": 0,
        "files_changed": 0,
        "has_conflicts": False,
    }

    try:
        # Get current commit before pull
        current_commit = run_git_command(["rev-parse", "HEAD"], cwd=repo_path)

        # Get current branch for explicit pull
        current_branch = get_current_branch(repo_path)

        # Perform pull - explicitly specify branch to avoid "did not specify a branch" error
        if verbose:
            result = run_git_command(["pull", "origin", current_branch, "-v"], cwd=repo_path)
        else:
            result = run_git_command(["pull", "origin", current_branch], cwd=repo_path)

        # Check if already up to date
        if "Already up to date" in result or "Already up-to-date" in result:
            return (True, "Already up to date", stats)

        # Get new commit after pull
        new_commit = run_git_command(["rev-parse", "HEAD"], cwd=repo_path)

        # Count commits pulled
        if current_commit != new_commit:
            try:
                commit_log = run_git_command(
                    ["rev-list", "--count", f"{current_commit}..{new_commit}"],
                    cwd=repo_path,
                )
                stats["commits_pulled"] = int(commit_log)
            except (GitError, ValueError):
                stats["commits_pulled"] = 1  # At least one commit

        return (True, f"Pulled {stats['commits_pulled']} commits", stats)

    except GitError as e:
        error_msg = str(e)

        # Detect merge conflicts
        if "conflict" in error_msg.lower() or "CONFLICT" in error_msg:
            stats["has_conflicts"] = True
            return (False, "Merge conflicts detected", stats)

        return (False, error_msg, stats)


def check_repo_status(repo_path: Path) -> dict[str, Any]:
    """Check repository status for uncommitted changes and ahead/behind.

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary with status information
    """
    status: dict[str, Any] = {
        "dirty": False,
        "uncommitted_changes": 0,
        "ahead": 0,
        "behind": 0,
    }

    try:
        # Check for uncommitted changes
        git_status = run_git_command(["status", "--porcelain"], cwd=repo_path)
        if git_status.strip():
            status["dirty"] = True
            status["uncommitted_changes"] = len(git_status.strip().splitlines())

        # Check ahead/behind
        try:
            branch = get_current_branch(repo_path)
            tracking_info = run_git_command(
                ["rev-list", "--left-right", "--count", f"{branch}...origin/{branch}"],
                cwd=repo_path,
            )
            parts = tracking_info.split()
            if len(parts) >= 2:
                status["ahead"] = int(parts[0])
                status["behind"] = int(parts[1])
        except (GitError, ValueError, IndexError):
            # Tracking branch might not exist
            pass

    except GitError:
        pass

    return status


def pull_repository(
    repo_entry: dict[str, Any],
    project_dir: Path,
    fetch_only: bool,
    gh_available: bool,
    verbose: bool,
) -> dict[str, Any]:
    """Pull or fetch a single repository and update metadata.

    Args:
        repo_entry: Repository entry from pyproject.toml
        project_dir: Path to project directory
        fetch_only: If True, only fetch (don't merge)
        gh_available: Whether GitHub CLI is available
        verbose: Enable verbose output

    Returns:
        Dictionary with operation results and updated metadata
    """
    url = repo_entry.get("url", "")
    branch = repo_entry.get("branch", "main")
    path = repo_entry.get("path", "")

    result: dict[str, Any] = {
        "url": url,
        "branch": branch,
        "path": path,
        "success": False,
        "message": "",
        "updated_metadata": {},
        "status": {},
    }

    # Construct full path to repository
    repo_path = project_dir / path

    # Check if repository exists
    if not repo_path.exists():
        result["message"] = "Repository not found on disk"
        return result

    if not is_git_repo(repo_path):
        result["message"] = "Not a git repository"
        return result

    # Check for detached HEAD
    if is_detached_head(repo_path):
        result["message"] = "Detached HEAD state"
        result["status"]["detached"] = True
        return result

    # Check for remote
    if not has_remote(repo_path, "origin"):
        result["message"] = "No remote configured"
        return result

    # Get current branch
    try:
        current_branch = get_current_branch(repo_path)
    except GitError as e:
        result["message"] = f"Failed to get current branch: {e}"
        return result

    # Perform fetch or pull
    if fetch_only:
        success, message = git_fetch(repo_path, verbose)
        result["success"] = success
        result["message"] = message
    else:
        success, message, stats = git_pull(repo_path, verbose)
        result["success"] = success
        result["message"] = message
        result["stats"] = stats

        if stats.get("has_conflicts"):
            result["status"]["conflicts"] = True

    # Check repository status
    status_info = check_repo_status(repo_path)
    result["status"].update(status_info)

    # Update metadata if successful
    if result["success"]:
        result["updated_metadata"]["branch"] = current_branch
        result["updated_metadata"]["updated"] = datetime.now(UTC).isoformat()

        # Get PR/issue info if gh is available
        if gh_available:
            pr_info = get_pr_info(repo_path, current_branch)
            if pr_info:
                result["updated_metadata"].update(pr_info)
                result["pr_info"] = pr_info

            issue = get_issue_info(repo_path, current_branch)
            if issue:
                result["updated_metadata"]["issue"] = issue

    return result


def update_pyproject_metadata(
    project_dir: Path,
    repo_url: str,
    repo_branch: str,
    updated_metadata: dict[str, Any],
) -> None:
    """Update repository metadata in pyproject.toml.

    Args:
        project_dir: Path to project directory
        repo_url: Repository URL
        repo_branch: Repository branch
        updated_metadata: Metadata fields to update

    Raises:
        PyProjectUpdateError: If update fails
    """
    from qenvy.formats import TOMLHandler

    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise PyProjectUpdateError(f"pyproject.toml not found in {project_dir}")

    handler = TOMLHandler()

    try:
        config = handler.read(pyproject_path)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to read pyproject.toml: {e}") from e

    # Find the repository entry
    repos = config.get("tool", {}).get("qen", {}).get("repos", [])

    found = False
    for repo in repos:
        if isinstance(repo, dict):
            if repo.get("url") == repo_url and repo.get("branch") == repo_branch:
                # Update metadata fields
                for key, value in updated_metadata.items():
                    # Only update metadata fields (not core fields like url, path)
                    if key in [
                        "branch",
                        "updated",
                        "pr",
                        "pr_base",
                        "pr_status",
                        "pr_checks",
                        "issue",
                    ]:
                        repo[key] = value
                found = True
                break

    if not found:
        raise PyProjectUpdateError(
            f"Repository not found in pyproject.toml: {repo_url} (branch: {repo_branch})"
        )

    # Write back to file
    try:
        handler.write(pyproject_path, config)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to write pyproject.toml: {e}") from e


def format_repo_output(result: dict[str, Any]) -> str:
    """Format output for a single repository.

    Args:
        result: Repository operation result

    Returns:
        Formatted output string
    """
    lines = []

    # Repository header
    repo_name = Path(result["path"]).name
    branch = result["branch"]
    lines.append(f"\n📦 {repo_name} ({branch})")

    # Operation result
    if result["success"]:
        if result.get("stats", {}).get("commits_pulled", 0) > 0:
            commits = result["stats"]["commits_pulled"]
            lines.append(f"   ✓ Pulled {commits} commit{'s' if commits != 1 else ''}")
        else:
            lines.append(f"   ✓ {result['message']}")
    else:
        lines.append(f"   ✗ {result['message']}")

    # Status warnings
    status = result.get("status", {})
    if status.get("conflicts"):
        lines.append("   ✗ Merge conflicts detected")
    if status.get("behind", 0) > 0:
        lines.append(
            f"   ⚠ {status['behind']} commit{'s' if status['behind'] != 1 else ''} behind origin/{branch}"
        )
    if status.get("uncommitted_changes", 0) > 0:
        changes = status["uncommitted_changes"]
        lines.append(f"   ⚠ {changes} uncommitted change{'s' if changes != 1 else ''}")
    if status.get("detached"):
        lines.append("   ⚠ Detached HEAD state")

    # PR information
    pr_info = result.get("pr_info", {})
    if pr_info.get("pr"):
        pr_num = pr_info["pr"]
        pr_status = pr_info.get("pr_status", "unknown")
        pr_base = pr_info.get("pr_base", "unknown")
        lines.append(f"   📋 PR #{pr_num} ({pr_status}) → {pr_base}")

        # Check status
        pr_checks = pr_info.get("pr_checks")
        if pr_checks == "passing":
            lines.append("   ✓ Checks passing")
        elif pr_checks == "failing":
            lines.append("   ✗ Checks failing")
        elif pr_checks == "pending":
            lines.append("   ⏳ Checks pending")
    elif result["success"]:
        lines.append("   • No PR")

    return "\n".join(lines)


def pull_all_repositories(
    project_name: str | None = None,
    fetch_only: bool = False,
    verbose: bool = False,
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Pull or fetch all repositories in the current project.

    Args:
        project_name: Name of project (if None, use current project from config)
        fetch_only: If True, only fetch (don't merge)
        verbose: Enable verbose output
        config_dir: Override config directory (for testing)
        storage: Override storage backend (for testing with in-memory storage)
        meta_path_override: Runtime override for meta_path
        current_project_override: Runtime override for current_project

    Raises:
        NoActiveProjectError: If no project is currently active
        QenConfigError: If configuration cannot be read
        PyProjectNotFoundError: If pyproject.toml not found
    """
    # Load configuration (auto-initialize if needed)
    config = ensure_initialized(
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
        verbose=verbose,
    )

    # Ensure correct branch configuration
    ensure_correct_branch(config, verbose=verbose)

    # Config is now guaranteed to exist
    main_config = config.read_main_config()

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

    # Get project directory
    try:
        project_config = config.read_project_config(current_project)
    except QenConfigError as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    # Check for per-project meta repo field
    if "repo" not in project_config:
        click.echo(
            f"Error: Project '{current_project}' uses old configuration format.\n"
            f"This version requires per-project meta clones.\n"
            f"To migrate: qen init --force {current_project}",
            err=True,
        )
        raise click.Abort()

    per_project_meta = Path(project_config["repo"])
    folder = project_config["folder"]
    project_dir = per_project_meta / folder

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
        return

    # Check if gh CLI is available
    gh_available = check_gh_installed()
    if not gh_available and verbose:
        click.echo("Note: GitHub CLI (gh) not found. PR/issue detection disabled.")

    # Display header
    operation = "Fetching" if fetch_only else "Pulling"
    click.echo(f"{operation} project: {current_project}")

    # Pull each repository
    results = []
    for repo_entry in repos:
        if not isinstance(repo_entry, dict):
            continue

        result = pull_repository(
            repo_entry,
            project_dir,
            fetch_only,
            gh_available,
            verbose,
        )
        results.append(result)

        # Display result
        click.echo(format_repo_output(result))

        # Update pyproject.toml if successful
        if result["success"] and result.get("updated_metadata"):
            try:
                update_pyproject_metadata(
                    project_dir,
                    result["url"],
                    result["branch"],
                    result["updated_metadata"],
                )
            except PyProjectUpdateError as e:
                if verbose:
                    click.echo(f"   Warning: Failed to update metadata: {e}")

    # Display summary
    total = len(results)
    successful = sum(1 for r in results if r["success"])
    failed = total - successful
    conflicts = sum(1 for r in results if r.get("status", {}).get("conflicts"))
    prs = sum(1 for r in results if r.get("pr_info", {}).get("pr"))

    click.echo("\nSummary:")
    click.echo(f"  {total} {'repository' if total == 1 else 'repositories'} processed")
    if failed > 0:
        click.echo(f"  {failed} need{'s' if failed == 1 else ''} attention")
    if conflicts > 0:
        click.echo(f"  {conflicts} have merge conflicts")
    if prs > 0:
        pr_statuses: dict[str, int] = {}
        for r in results:
            pr_status = r.get("pr_info", {}).get("pr_status")
            if pr_status:
                pr_statuses[pr_status] = pr_statuses.get(pr_status, 0) + 1

        status_str = ", ".join(f"{count} {status}" for status, count in pr_statuses.items())
        click.echo(f"  {prs} PR{'s' if prs != 1 else ''} tracked ({status_str})")
