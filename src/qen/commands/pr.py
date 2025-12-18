"""Implementation of qen pr status command.

Enumerate and retrieve PR information across all repositories:
1. Load configuration and find current project
2. Read all repositories from pyproject.toml
3. For each repository:
   - Query gh CLI for PR information
   - Collect PR status, checks, and metadata
4. Display comprehensive PR summary with repository indices
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import click
from platformdirs import user_config_dir

from ..context.runtime import RuntimeContext, RuntimeContextError
from ..git_utils import GitError, get_current_branch, is_git_repo
from ..init_utils import ensure_correct_branch, ensure_initialized
from ..pr_utils import parse_check_status
from ..pyproject_utils import PyProjectNotFoundError, read_pyproject


class PrCommandError(Exception):
    """Base exception for pr command errors."""

    pass


class NoActiveProjectError(PrCommandError):
    """Raised when no active project is set."""

    pass


@dataclass
class CheckInfo:
    """Individual check information."""

    name: str
    status: str
    conclusion: str | None
    details_url: str | None


@dataclass
class PrInfo:
    """PR information for a repository."""

    repo_path: str
    repo_url: str
    branch: str
    has_pr: bool
    default_branch: str = "main"  # Default branch of the repository
    pr_number: int | None = None
    pr_title: str | None = None
    pr_state: str | None = None
    pr_base: str | None = None
    pr_url: str | None = None
    pr_checks: str | None = None
    pr_check_details: list[CheckInfo] | None = None
    pr_mergeable: str | None = None
    pr_author: str | None = None
    pr_created_at: str | None = None
    pr_updated_at: str | None = None
    pr_commits: int | None = None
    pr_files_changed: int | None = None
    pr_file_paths: list[str] | None = None
    is_draft: bool | None = None
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
                "number,title,state,baseRefName,url,statusCheckRollup,mergeable,author,createdAt,updatedAt,commits,files,isDraft",
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
        pr_check_details = None
        if checks:
            # Capture detailed check information for display
            pr_check_details = []
            for c in checks:
                status = c.get("status", "").upper()
                conclusion = c.get("conclusion", "").upper() if c.get("conclusion") else None
                name = c.get("name", "unknown")
                details_url = c.get("detailsUrl")

                # Store check details
                pr_check_details.append(
                    CheckInfo(
                        name=name,
                        status=status,
                        conclusion=conclusion,
                        details_url=details_url,
                    )
                )

            # Use shared utility to determine overall check status
            pr_checks = parse_check_status(checks)

        # Extract author login
        author_data = pr_data.get("author", {})
        pr_author = author_data.get("login") if isinstance(author_data, dict) else None

        # Parse commits and files
        commits_data = pr_data.get("commits", [])
        pr_commits = len(commits_data) if isinstance(commits_data, list) else None

        files_data = pr_data.get("files", [])
        pr_files_changed = len(files_data) if isinstance(files_data, list) else None

        # Extract file paths
        pr_file_paths = None
        if isinstance(files_data, list):
            paths = [
                f.get("path")
                for f in files_data
                if isinstance(f, dict) and "path" in f and f.get("path")
            ]
            # Filter out None values and ensure we have strings
            pr_file_paths = [p for p in paths if isinstance(p, str)]

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
            pr_check_details=pr_check_details,
            pr_mergeable=pr_data.get("mergeable", "").lower(),
            pr_author=pr_author,
            pr_created_at=pr_data.get("createdAt"),
            pr_updated_at=pr_data.get("updatedAt"),
            pr_commits=pr_commits,
            pr_files_changed=pr_files_changed,
            pr_file_paths=pr_file_paths,
            is_draft=pr_data.get("isDraft"),
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


def format_pr_info(pr: PrInfo, verbose: bool = False, index: int | None = None) -> str:
    """Format PR information for display.

    Args:
        pr: PrInfo object
        verbose: Include additional details
        index: Optional 1-based index to display

    Returns:
        Formatted string
    """
    lines = []

    # Repository header with optional index
    if index is not None:
        lines.append(f"\n[{index}] 📦 {pr.repo_path} ({pr.branch})")
    else:
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
            lines.append(click.style("   ✓ Checks: passing", fg="green"))
        elif pr.pr_checks == "failing":
            lines.append(click.style("   ✗ Checks: failing", fg="red"))
            # Show which checks failed
            if pr.pr_check_details:
                failing_checks = [
                    c
                    for c in pr.pr_check_details
                    if c.conclusion in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED")
                ]
                for check in failing_checks:
                    if check.details_url:
                        lines.append(f"      • {check.name}: {check.details_url}")
                    else:
                        lines.append(f"      • {check.name}")
        elif pr.pr_checks == "pending":
            lines.append(click.style("   ⏳ Checks: pending", fg="yellow"))
        elif pr.pr_checks == "skipped":
            lines.append("   ⊝ Checks: skipped")
        else:
            lines.append(f"   ❓ Checks: {pr.pr_checks}")

    # Mergeable status
    if pr.pr_mergeable:
        if pr.pr_mergeable == "mergeable":
            lines.append(click.style("   ✓ Mergeable", fg="green"))
        elif pr.pr_mergeable == "conflicting":
            lines.append(click.style("   ✗ Has conflicts", fg="red"))

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


def identify_stacks(pr_infos: list[PrInfo]) -> dict[str, list[PrInfo]]:
    """Identify PR stacks from a list of PrInfo objects.

    A PR is considered "stacked" if its base branch is another feature branch
    (not a main branch like main/master/develop).

    Args:
        pr_infos: List of PrInfo objects to analyze

    Returns:
        Dictionary mapping root branch name (the one targeting main) to
        list of PRs in that stack, ordered from root to leaves
    """
    # Main branch names to identify non-stacked PRs
    main_branches = {"main", "master", "develop", "dev"}

    # Build branch -> PrInfo lookup for PRs
    branch_to_pr: dict[str, PrInfo] = {}
    for pr_info in pr_infos:
        if pr_info.has_pr and pr_info.branch:
            branch_to_pr[pr_info.branch] = pr_info

    # Build parent-child relationships
    # child_branch -> parent_branch
    parent_map: dict[str, str] = {}
    for pr_info in pr_infos:
        if pr_info.has_pr and pr_info.pr_base and pr_info.branch:
            # Only consider it stacked if base is NOT a main branch
            # and the base branch has a PR
            if pr_info.pr_base not in main_branches and pr_info.pr_base in branch_to_pr:
                parent_map[pr_info.branch] = pr_info.pr_base

    # Find stack roots (PRs that target main branches)
    stacks: dict[str, list[PrInfo]] = {}
    for pr_info in pr_infos:
        if pr_info.has_pr and pr_info.pr_base and pr_info.branch:
            # Root of stack: targets a main branch AND has children
            if pr_info.pr_base in main_branches:
                # Check if this branch has children (is anyone's parent?)
                has_children = any(parent == pr_info.branch for parent in parent_map.values())
                if has_children:
                    stacks[pr_info.branch] = [pr_info]

    # Build stacks recursively
    def add_children(parent_branch: str, stack: list[PrInfo]) -> None:
        """Recursively add children to the stack."""
        for child_branch, parent in parent_map.items():
            if parent == parent_branch:
                child_pr = branch_to_pr.get(child_branch)
                if child_pr:
                    stack.append(child_pr)
                    # Recurse to find grandchildren
                    add_children(child_branch, stack)

    # Add all children to their stacks
    for root_branch, stack in stacks.items():
        add_children(root_branch, stack)

    return stacks


def identify_stacks_from_repo(repo_path: Path) -> dict[str, list[PrInfo]]:
    """Identify PR stacks from a single repository.

    Args:
        repo_path: Path to repository

    Returns:
        Dictionary mapping root branch name to list of PRs in that stack
    """
    if not is_git_repo(repo_path):
        return {}

    # Get current branch
    try:
        current_branch = get_current_branch(repo_path)
    except GitError:
        return {}

    # Get PR info for current branch
    # Note: We need the repo URL, but for stack detection we can use a placeholder
    # since we're only analyzing branch relationships within this repo
    pr_info = get_pr_info_for_branch(repo_path, current_branch, "")

    if not pr_info.has_pr:
        return {}

    # Use identify_stacks to detect stacks
    return identify_stacks([pr_info])


def format_stack_display(stacks: dict[str, list[PrInfo]], verbose: bool = False) -> str:
    """Format stack information for display.

    Args:
        stacks: Dictionary of stacks (root branch -> list of PRs)
        verbose: Include additional details

    Returns:
        Formatted string showing tree structure
    """
    if not stacks:
        return "No stacks found."

    lines = []
    for root_branch, prs in stacks.items():
        lines.append(f"\n🌳 Stack rooted at: {root_branch}")

        for i, pr in enumerate(prs):
            is_last = i == len(prs) - 1
            prefix = "   └─" if is_last else "   ├─"

            # PR title and number
            if pr.pr_number and pr.pr_title:
                lines.append(f"{prefix} PR #{pr.pr_number}: {pr.pr_title}")

            # Stats: commits and files
            stats = []
            if pr.pr_commits is not None:
                stats.append(f"{pr.pr_commits} commits")
            if pr.pr_files_changed is not None:
                stats.append(f"{pr.pr_files_changed} files")
            if stats:
                indent = "      " if is_last else "   │  "
                lines.append(f"{indent}📊 {', '.join(stats)}")

            # Base branch
            if pr.pr_base:
                indent = "      " if is_last else "   │  "
                lines.append(f"{indent}🎯 Base: {pr.pr_base}")

            # Check status
            if pr.pr_checks:
                indent = "      " if is_last else "   │  "
                if pr.pr_checks == "passing":
                    lines.append(click.style(f"{indent}✓ Checks: passing", fg="green"))
                elif pr.pr_checks == "failing":
                    lines.append(click.style(f"{indent}✗ Checks: failing", fg="red"))
                    # Show which checks failed
                    if pr.pr_check_details:
                        failing_checks = [
                            c
                            for c in pr.pr_check_details
                            if c.conclusion in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED")
                        ]
                        fail_indent = "         " if is_last else "   │     "
                        for check in failing_checks:
                            if check.details_url:
                                lines.append(f"{fail_indent}• {check.name}: {check.details_url}")
                            else:
                                lines.append(f"{fail_indent}• {check.name}")
                elif pr.pr_checks == "pending":
                    lines.append(click.style(f"{indent}⏳ Checks: pending", fg="yellow"))
                elif pr.pr_checks == "skipped":
                    lines.append(f"{indent}⊝ Checks: skipped")

            # Mergeable status
            if pr.pr_mergeable:
                indent = "      " if is_last else "   │  "
                if pr.pr_mergeable == "mergeable":
                    lines.append(click.style(f"{indent}✓ Mergeable", fg="green"))
                elif pr.pr_mergeable == "conflicting":
                    lines.append(click.style(f"{indent}✗ Has conflicts", fg="red"))
                    # In verbose mode, show which files are changed (may be conflicting)
                    if verbose and pr.pr_file_paths:
                        lines.append(f"{indent}   📄 Changed files:")
                        for file_path in pr.pr_file_paths:
                            lines.append(f"{indent}      • {file_path}")

            # Verbose information
            if verbose:
                indent = "      " if is_last else "   │  "
                if pr.pr_author:
                    lines.append(f"{indent}👤 Author: {pr.pr_author}")
                if pr.pr_url:
                    lines.append(f"{indent}🔗 URL: {pr.pr_url}")

    return "\n".join(lines)


def get_stack_summary(stacks: dict[str, list[PrInfo]]) -> dict[str, int]:
    """Get summary statistics for stacks.

    Args:
        stacks: Dictionary of stacks (root branch -> list of PRs)

    Returns:
        Dictionary with summary statistics
    """
    total_stacks = len(stacks)
    total_prs_in_stacks = sum(len(prs) for prs in stacks.values())
    max_depth = max((len(prs) for prs in stacks.values()), default=0)

    return {
        "total_stacks": total_stacks,
        "total_prs_in_stacks": total_prs_in_stacks,
        "max_depth": max_depth,
    }


def get_all_pr_infos(
    runtime_ctx: RuntimeContext | None = None,
    project_name: str | None = None,
    config_dir: Path | str | None = None,
    storage: Any | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> list[PrInfo]:
    """Get PR information for all repositories in the current project.

    This is the core data-fetching function without any display logic.
    Used by both pr_status_command and pr_stack_command.

    Args:
        runtime_ctx: Runtime context with CLI overrides (new preferred API)
        project_name: DEPRECATED - use runtime_ctx instead
        config_dir: DEPRECATED - use runtime_ctx instead
        storage: DEPRECATED - use runtime_ctx instead
        meta_path_override: DEPRECATED - use runtime_ctx instead
        current_project_override: DEPRECATED - use runtime_ctx instead

    Returns:
        List of PrInfo objects for all repositories

    Raises:
        RuntimeContextError: If no project is currently active or config errors
        click.Abort: If validation fails or dependencies missing
    """
    from qenvy.base import QenvyBase

    # Support backward compatibility with old test signatures
    if runtime_ctx is None:
        # Use old ensure_initialized pattern for tests
        config = ensure_initialized(
            config_dir=config_dir,
            storage=cast(QenvyBase, storage) if storage else None,
            meta_path_override=meta_path_override,
            current_project_override=current_project_override,
            verbose=False,
        )
        # Ensure the project is on the correct branch
        ensure_correct_branch(config, verbose=False)

        # Get current project
        main_config = config.read_main_config()
        current_project = main_config.get("current_project")
        if not current_project:
            click.echo(
                "Error: No active project. Create a project with 'qen init <project-name>' first.",
                err=True,
            )
            raise click.Abort()
    else:
        # New RuntimeContext API
        try:
            current_project = runtime_ctx.get_current_project()
        except RuntimeContextError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort() from e

        config = runtime_ctx.config_service
        # Ensure the project is on the correct branch
        ensure_correct_branch(config, verbose=False)

    # Check if gh CLI is available
    if not check_gh_installed():
        click.echo("Error: GitHub CLI (gh) is not installed or not accessible.", err=True)
        click.echo("Install it from: https://cli.github.com/", err=True)
        raise click.Abort()

    # Get project directory
    try:
        project_config = config.read_project_config(current_project)
    except Exception as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    # Check for per-project meta (new format)
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
        return []

    # Query PR info for each repository
    pr_infos = []
    for repo_entry in repos:
        if not isinstance(repo_entry, dict):
            continue

        url = repo_entry.get("url", "")
        branch = repo_entry.get("branch", "main")
        path = repo_entry.get("path", "")
        default_branch = repo_entry.get("default_branch", "main")

        # Construct full path to repository
        repo_path = project_dir / path

        # Check if repository exists
        if not repo_path.exists():
            pr_info = PrInfo(
                repo_path=str(Path(path).name),
                repo_url=url,
                branch=branch,
                default_branch=default_branch,
                has_pr=False,
                error="Repository not found on disk",
            )
        else:
            pr_info = get_pr_info_for_branch(repo_path, branch, url)
            # Add default_branch to the retrieved pr_info
            pr_info.default_branch = default_branch

        pr_infos.append(pr_info)

    return pr_infos


def pr_status_command(
    runtime_ctx: RuntimeContext | None = None,
    project_name: str | None = None,
    verbose: bool = False,
    config_dir: Path | str | None = None,
    storage: Any | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> list[PrInfo]:
    """Get PR status for all repositories in the current project.

    Args:
        runtime_ctx: Runtime context with CLI overrides (new preferred API)
        project_name: DEPRECATED - use runtime_ctx instead
        verbose: Enable verbose output
        config_dir: DEPRECATED - use runtime_ctx instead
        storage: DEPRECATED - use runtime_ctx instead
        meta_path_override: DEPRECATED - use runtime_ctx instead
        current_project_override: DEPRECATED - use runtime_ctx instead

    Returns:
        List of PrInfo objects for all repositories

    Raises:
        RuntimeContextError: If no project is currently active
        click.Abort: If validation fails
    """
    from qenvy.base import QenvyBase

    # Support backward compatibility with old test signatures
    if runtime_ctx is None:
        # Use old ensure_initialized pattern for tests
        config = ensure_initialized(
            config_dir=config_dir,
            storage=cast(QenvyBase, storage) if storage else None,
            meta_path_override=meta_path_override,
            current_project_override=current_project_override,
            verbose=False,
        )
        ensure_correct_branch(config, verbose=False)
        main_config = config.read_main_config()
        current_project = main_config.get("current_project")
    else:
        # New RuntimeContext API
        try:
            current_project = runtime_ctx.get_current_project()
        except RuntimeContextError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort() from e

        # Ensure the project is on the correct branch
        ensure_correct_branch(runtime_ctx.config_service, verbose=False)

    if verbose:
        click.echo(f"Current project: {current_project}")

    # Get all PR info using shared function
    pr_infos = get_all_pr_infos(
        runtime_ctx=runtime_ctx,
        project_name=project_name,
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Display header
    click.echo(f"PR Status for project: {current_project}")

    # Display each PR with 1-based index
    for idx, pr_info in enumerate(pr_infos, start=1):
        click.echo(format_pr_info(pr_info, verbose, index=idx))

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


def pr_stack_command(
    runtime_ctx: RuntimeContext | None = None,
    project_name: str | None = None,
    verbose: bool = False,
    config_dir: Path | str | None = None,
    storage: Any | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> dict[str, list[PrInfo]]:
    """Identify and display stacked PRs across all repositories.

    Args:
        runtime_ctx: Runtime context with CLI overrides (new preferred API)
        project_name: DEPRECATED - use runtime_ctx instead
        verbose: Enable verbose output
        config_dir: DEPRECATED - use runtime_ctx instead
        storage: DEPRECATED - use runtime_ctx instead
        meta_path_override: DEPRECATED - use runtime_ctx instead
        current_project_override: DEPRECATED - use runtime_ctx instead

    Returns:
        Dictionary of stacks (root branch -> list of PRs)

    Raises:
        click.Abort: If no PRs found or other errors
    """
    # Get all PR info using shared data-fetching function
    pr_infos = get_all_pr_infos(
        runtime_ctx=runtime_ctx,
        project_name=project_name,
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Check if we have any PRs
    prs_with_pr = [pr for pr in pr_infos if pr.has_pr]
    if not prs_with_pr:
        click.echo("Error: No PRs found in project.", err=True)
        click.echo("Create PRs first, then identify stacks.", err=True)
        raise click.Abort()

    # Identify stacks
    stacks = identify_stacks(pr_infos)

    if not stacks:
        click.echo("No stacks found.")
        click.echo(
            "\nStacks are identified when a PR's base branch is another feature branch.",
            err=False,
        )
        return {}

    # Display stacks
    click.echo("\nStacked PRs in project:")
    click.echo(format_stack_display(stacks, verbose=verbose))

    # Display summary
    summary = get_stack_summary(stacks)
    click.echo("\nSummary:")
    click.echo(
        f"  {summary['total_stacks']} {'stack' if summary['total_stacks'] == 1 else 'stacks'} found"
    )
    click.echo(f"  {summary['total_prs_in_stacks']} PRs in stacks")
    click.echo(f"  Maximum stack depth: {summary['max_depth']}")

    return stacks


def parse_repo_owner_and_name(repo_url: str) -> tuple[str, str] | None:
    """Parse owner and name from a GitHub repository URL.

    Args:
        repo_url: GitHub repository URL (https://github.com/owner/repo)

    Returns:
        Tuple of (owner, repo_name) or None if parsing fails
    """
    # Handle different URL formats:
    # - https://github.com/owner/repo
    # - git@github.com:owner/repo.git
    # - owner/repo
    try:
        if repo_url.startswith("https://github.com/"):
            parts = repo_url.replace("https://github.com/", "").rstrip("/").split("/")
            if len(parts) >= 2:
                return (parts[0], parts[1].replace(".git", ""))
        elif repo_url.startswith("git@github.com:"):
            parts = repo_url.replace("git@github.com:", "").rstrip("/").split("/")
            if len(parts) >= 2:
                return (parts[0], parts[1].replace(".git", ""))
        elif "/" in repo_url and not repo_url.startswith("http"):
            # Assume owner/repo format
            parts = repo_url.split("/")
            if len(parts) == 2:
                return (parts[0], parts[1])
    except Exception:
        pass

    return None


def restack_pr(owner: str, repo: str, pr_number: int, dry_run: bool = False) -> bool:
    """Update a PR branch to be based on the latest version of its base branch.

    Uses GitHub API via gh CLI to update the PR branch.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number to update
        dry_run: If True, don't actually update the branch

    Returns:
        True if update succeeded, False otherwise
    """
    if dry_run:
        click.echo(f"   [DRY RUN] Would update PR #{pr_number} in {owner}/{repo}")
        return True

    try:
        # Use gh API to update the PR branch
        # https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request-branch
        result = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{owner}/{repo}/pulls/{pr_number}/update-branch",
                "-X",
                "PUT",
                "-f",
                "expected_head_sha=",  # Empty means update regardless
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            # Check if error is about branch being up to date
            if "already up to date" in result.stderr.lower():
                click.echo(f"   ✓ PR #{pr_number} already up to date")
                return True
            else:
                click.echo(f"   ✗ Failed to update PR #{pr_number}: {result.stderr}", err=True)
                return False

        click.echo(f"   ✓ Updated PR #{pr_number}")
        return True

    except subprocess.TimeoutExpired:
        click.echo(f"   ✗ Timeout updating PR #{pr_number}", err=True)
        return False
    except Exception as e:
        click.echo(f"   ✗ Error updating PR #{pr_number}: {e}", err=True)
        return False


def pr_restack_command(
    runtime_ctx: RuntimeContext | None = None,
    project_name: str | None = None,
    dry_run: bool = False,
    config_dir: Path | str | None = None,
    storage: Any | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> dict[str, list[tuple[PrInfo, bool]]]:
    """Update all stacked PRs to be based on latest versions of their base branches.

    Args:
        runtime_ctx: Runtime context with CLI overrides (new preferred API)
        project_name: DEPRECATED - use runtime_ctx instead
        dry_run: If True, show what would be done without making changes
        config_dir: DEPRECATED - use runtime_ctx instead
        storage: DEPRECATED - use runtime_ctx instead
        meta_path_override: DEPRECATED - use runtime_ctx instead
        current_project_override: DEPRECATED - use runtime_ctx instead

    Returns:
        Dictionary mapping root branch to list of (PrInfo, success) tuples

    Raises:
        click.Abort: If no stacks found or other errors
    """
    # Get stacks using existing command
    stacks = pr_stack_command(
        runtime_ctx=runtime_ctx,
        project_name=project_name,
        verbose=False,
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    if not stacks:
        click.echo("Error: No stacks found to restack.", err=True)
        raise click.Abort()

    if dry_run:
        click.echo("\n=== DRY RUN MODE ===")
        click.echo("No changes will be made.\n")

    click.echo("\nRestacking PRs...")

    results: dict[str, list[tuple[PrInfo, bool]]] = {}

    for root_branch, prs in stacks.items():
        click.echo(f"\n📚 Stack: {root_branch}")
        stack_results: list[tuple[PrInfo, bool]] = []

        # Process PRs in order (parent before children)
        for pr in prs:
            if not pr.pr_number or not pr.repo_url:
                click.echo("   ⚠ Skipping PR: missing number or URL")
                stack_results.append((pr, False))
                continue

            # Parse owner and repo from URL
            parsed = parse_repo_owner_and_name(pr.repo_url)
            if not parsed:
                click.echo(f"   ⚠ Skipping PR #{pr.pr_number}: failed to parse repo URL")
                stack_results.append((pr, False))
                continue

            owner, repo = parsed
            click.echo(f"   📋 PR #{pr.pr_number}: {pr.pr_title or '(no title)'}")

            # Update the PR
            success = restack_pr(owner, repo, pr.pr_number, dry_run=dry_run)
            stack_results.append((pr, success))

        results[root_branch] = stack_results

    # Display summary
    total_prs = sum(len(stack_results) for stack_results in results.values())
    successful = sum(
        1 for stack_results in results.values() for _, success in stack_results if success
    )
    failed = total_prs - successful

    click.echo("\n=== Summary ===")
    click.echo(f"Total PRs processed: {total_prs}")
    if dry_run:
        click.echo(f"Would update: {successful}")
    else:
        click.echo(f"Successfully updated: {successful}")
        if failed > 0:
            click.echo(f"Failed: {failed}")

    return results


@click.command(name="pr")
@click.argument("indices", nargs=-1, type=int)
@click.option("--action", type=click.Choice(["merge", "close", "create", "update", "stack"]))
@click.option("--yes", is_flag=True, help="Skip all confirmations")
@click.option("--strategy", type=click.Choice(["squash", "merge", "rebase"]), help="Merge strategy")
@click.option("--title", help="PR title for create action")
@click.option("--body", help="PR body for create action")
@click.option("--base", help="Base branch for create action (default: main)")
@click.pass_context
def pr_command(
    ctx: click.Context,
    indices: tuple[int, ...],
    action: str | None,
    yes: bool,
    strategy: str | None,
    title: str | None,
    body: str | None,
    base: str | None,
) -> None:
    """Interactive PR management across repositories.

    Launch an interactive TUI to select repositories and perform PR operations
    (merge, close, create, update branch, view stacks).

    You can also specify repository indices directly for quick operations:

    \b
        qen pr 1 3 --action merge --yes          # Merge PRs for repos 1 and 3
        qen pr 2 --action create --title "..."   # Create PR for repo 2
        qen pr --action update                   # Update branches to sync with base

    Repositories are indexed ([1], [2], etc.) based on their order in the
    project configuration.

    Requires GitHub CLI (gh) to be installed and authenticated.

    Examples:

    \b
        # Launch interactive TUI
        $ qen pr

    \b
        # Pre-select repos and choose action interactively
        $ qen pr 1 3

    \b
        # Direct merge with confirmation
        $ qen pr 1 --action merge --strategy squash --yes

    \b
        # Create PR for repo 2
        $ qen pr 2 --action create --title "Add feature X"
    """
    from .pr_tui import (
        display_interactive_table,
        handle_close,
        handle_create,
        handle_merge,
        handle_stack_view,
        handle_update_branch,
        prompt_for_action,
    )

    # Get runtime context from Click context
    overrides = ctx.obj.get("config_overrides", {})
    runtime_ctx = RuntimeContext(
        config_dir=overrides.get("config_dir") or Path(user_config_dir("qen")),
        current_project_override=overrides.get("current_project"),
        meta_path_override=overrides.get("meta_path"),
    )

    # Get all PR info
    pr_infos = get_all_pr_infos(runtime_ctx)

    if not pr_infos:
        click.echo("No repositories found in project.")
        return

    # Mode 1: Direct operation with indices and action
    if indices and action:
        # Validate indices
        invalid_indices = [idx for idx in indices if idx < 1 or idx > len(pr_infos)]
        if invalid_indices:
            raise click.ClickException(
                f"Invalid repository indices: {invalid_indices}. Valid range: 1-{len(pr_infos)}"
            )

        # Build selected rows
        from .pr_tui import build_pr_table

        rows = build_pr_table(pr_infos)
        selected_rows = [rows[idx - 1] for idx in indices]

        click.echo(f"Selected {len(selected_rows)} repositories")

        # Execute action
        success, failure = 0, 0
        if action == "merge":
            success, failure = handle_merge(
                selected_rows, skip_confirm=yes, merge_strategy=strategy
            )
        elif action == "close":
            success, failure = handle_close(selected_rows, skip_confirm=yes)
        elif action == "create":
            success, failure = handle_create(
                selected_rows, skip_confirm=yes, title=title, body=body, base=base
            )
        elif action == "update":
            success, failure = handle_update_branch(selected_rows, dry_run=not yes)
        elif action == "stack":
            handle_stack_view(selected_rows)
            return

        # Show summary
        total = success + failure
        click.echo(f"\n✓ {success}/{total} operations successful")
        if failure > 0:
            click.echo(f"✗ {failure}/{total} operations failed", err=True)

    # Mode 2: Pre-selected indices, prompt for action
    elif indices:
        # Validate indices
        invalid_indices = [idx for idx in indices if idx < 1 or idx > len(pr_infos)]
        if invalid_indices:
            raise click.ClickException(
                f"Invalid repository indices: {invalid_indices}. Valid range: 1-{len(pr_infos)}"
            )

        # Build selected rows
        from .pr_tui import build_pr_table

        rows = build_pr_table(pr_infos)
        selected_rows = [rows[idx - 1] for idx in indices]

        click.echo(f"Selected {len(selected_rows)} repositories:")
        for row in selected_rows:
            click.echo(f"  [{row.index}] {row.repo_name} ({row.branch})")

        # Prompt for action
        selected_action = prompt_for_action()
        if not selected_action:
            click.echo("Cancelled.")
            return

        # Execute action
        success, failure = 0, 0
        if selected_action == "merge":
            success, failure = handle_merge(
                selected_rows, skip_confirm=yes, merge_strategy=strategy
            )
        elif selected_action == "close":
            success, failure = handle_close(selected_rows, skip_confirm=yes)
        elif selected_action == "create":
            success, failure = handle_create(
                selected_rows, skip_confirm=yes, title=title, body=body, base=base
            )
        elif selected_action == "update":
            success, failure = handle_update_branch(selected_rows, dry_run=False)
        elif selected_action == "stack":
            handle_stack_view(selected_rows)
            return

        # Show summary
        total = success + failure
        if total > 0:
            click.echo(f"\n✓ {success}/{total} operations successful")
            if failure > 0:
                click.echo(f"✗ {failure}/{total} operations failed", err=True)

    # Mode 3: Full interactive mode
    else:
        click.echo("Interactive PR Manager")
        click.echo("=" * 40)
        click.echo("")

        # Display interactive table
        selected_rows_result = display_interactive_table(pr_infos)

        if not selected_rows_result:
            click.echo("No repositories selected. Exiting.")
            return

        selected_rows = selected_rows_result

        click.echo(f"\nSelected {len(selected_rows)} repositories:")
        for row in selected_rows:
            click.echo(f"  [{row.index}] {row.repo_name} ({row.branch})")

        # Prompt for action
        selected_action = prompt_for_action()
        if not selected_action:
            click.echo("Cancelled.")
            return

        # Execute action
        success, failure = 0, 0
        if selected_action == "merge":
            success, failure = handle_merge(
                selected_rows, skip_confirm=yes, merge_strategy=strategy
            )
        elif selected_action == "close":
            success, failure = handle_close(selected_rows, skip_confirm=yes)
        elif selected_action == "create":
            success, failure = handle_create(
                selected_rows, skip_confirm=yes, title=title, body=body, base=base
            )
        elif selected_action == "update":
            success, failure = handle_update_branch(selected_rows, dry_run=False)
        elif selected_action == "stack":
            handle_stack_view(selected_rows)
            return

        # Show summary
        total = success + failure
        if total > 0:
            click.echo(f"\n✓ {success}/{total} operations successful")
            if failure > 0:
                click.echo(f"✗ {failure}/{total} operations failed", err=True)
