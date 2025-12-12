"""Remove repositories from a qen project.

This module implements the `qen rm` command which safely removes repositories
from a qen project by:

1. Safety checks - Prompt if repository has unpushed/unmerged changes
2. Config cleanup - Remove entry from pyproject.toml
3. Filesystem cleanup - Delete repository directory from repos/
4. Workspace update - Regenerate workspace files (unless --no-workspace)
"""

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click


@dataclass
class RepoToRemove:
    """Repository to be removed."""

    index: int  # 1-based index in pyproject.toml
    url: str  # Repository URL
    branch: str  # Branch name
    path: str  # Local path (relative to project)
    repo_entry: dict[str, Any]  # Full repo dict from pyproject.toml


@dataclass
class SafetyCheck:
    """Safety check result for a repository."""

    repo_url: str
    repo_branch: str
    has_unpushed: bool = False
    has_uncommitted: bool = False
    has_unmerged_pr: bool = False
    unpushed_count: int = 0
    uncommitted_files: list[str] = field(default_factory=list)
    pr_number: int | None = None
    pr_status: str | None = None

    def is_safe(self) -> bool:
        """Check if removal is safe without --force."""
        return not (self.has_unpushed or self.has_uncommitted or self.has_unmerged_pr)

    def warning_message(self) -> str:
        """Generate warning message for unsafe removal."""
        parts = []
        if self.has_unpushed:
            commit_word = "commit" if self.unpushed_count == 1 else "commits"
            parts.append(f"{self.unpushed_count} unpushed {commit_word}")
        if self.has_uncommitted:
            file_word = "file" if len(self.uncommitted_files) == 1 else "files"
            parts.append(f"{len(self.uncommitted_files)} uncommitted {file_word}")
        if self.has_unmerged_pr:
            parts.append(f"unmerged PR #{self.pr_number} ({self.pr_status})")
        return ", ".join(parts)


def parse_repo_identifiers(
    repos: tuple[str, ...], project_dir: Path, org: str | None
) -> list[RepoToRemove]:
    """Parse repository identifiers into removal targets.

    Supports four identifier formats:
    1. Integer strings → 1-based indices
    2. Full URLs → Match by URL
    3. org/repo format → Match by org and repo
    4. repo name only → Use org from config

    Args:
        repos: Tuple of repository identifiers
        project_dir: Path to project directory
        org: Default organization from config

    Returns:
        List of RepoToRemove objects

    Raises:
        click.ClickException: If identifier not found or ambiguous
    """
    from ..pyproject_utils import read_pyproject
    from ..repo_utils import parse_repo_url

    # Load all repos from pyproject.toml
    pyproject = read_pyproject(project_dir)
    all_repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

    if not all_repos:
        raise click.ClickException("No repositories in project")

    to_remove: list[RepoToRemove] = []

    for identifier in repos:
        identifier = identifier.strip()

        # Format 1: Integer index (1-based)
        if identifier.isdigit():
            idx = int(identifier)
            if idx < 1 or idx > len(all_repos):
                raise click.ClickException(
                    f"Index {idx} out of range. Valid indices: 1-{len(all_repos)}"
                )

            repo_entry = all_repos[idx - 1]
            to_remove.append(
                RepoToRemove(
                    index=idx,
                    url=repo_entry["url"],
                    branch=repo_entry.get("branch", "main"),
                    path=repo_entry["path"],
                    repo_entry=repo_entry,
                )
            )
            continue

        # Parse as URL/org/repo/name
        try:
            parsed = parse_repo_url(identifier, org)
            target_url = parsed["url"]

            # Find matching repo(s)
            matches = []
            for i, repo_entry in enumerate(all_repos, start=1):
                if repo_entry["url"] == target_url:
                    matches.append((i, repo_entry))

            if not matches:
                raise click.ClickException(f"Repository not found: {identifier}")

            if len(matches) > 1:
                # Multiple branches - need user to specify index or URL+branch
                branches = [r[1].get("branch", "main") for r in matches]
                raise click.ClickException(
                    f"Multiple branches found for {identifier}: {', '.join(branches)}\n"
                    f"Specify index or URL with branch"
                )

            idx, repo_entry = matches[0]
            to_remove.append(
                RepoToRemove(
                    index=idx,
                    url=repo_entry["url"],
                    branch=repo_entry.get("branch", "main"),
                    path=repo_entry["path"],
                    repo_entry=repo_entry,
                )
            )

        except click.ClickException:
            raise
        except Exception as e:
            raise click.ClickException(f"Cannot parse identifier '{identifier}': {e}") from e

    return to_remove


def check_repo_safety(repo_path: Path, repo_entry: dict[str, Any]) -> SafetyCheck:
    """Perform safety checks on a repository before removal.

    Checks:
    1. Unpushed commits - git rev-list @{upstream}..HEAD
    2. Uncommitted changes - git status --porcelain
    3. Unmerged PRs - pr_status field != "merged"

    Args:
        repo_path: Path to repository directory
        repo_entry: Repository entry from pyproject.toml

    Returns:
        SafetyCheck object with all check results
    """
    from ..git_utils import get_repo_status, get_sync_status

    url = repo_entry["url"]
    branch = repo_entry.get("branch", "main")

    check = SafetyCheck(repo_url=url, repo_branch=branch)

    # If repo doesn't exist on disk, skip git checks
    if not repo_path.exists():
        return check

    # Check 1: Unpushed commits
    try:
        sync = get_sync_status(repo_path, fetch=False)
        if sync.has_upstream and sync.ahead > 0:
            check.has_unpushed = True
            check.unpushed_count = sync.ahead
    except Exception:
        # If we can't check, be conservative and don't flag
        pass

    # Check 2: Uncommitted changes
    try:
        status = get_repo_status(repo_path, fetch=False)
        uncommitted = []
        if status.modified:
            uncommitted.extend(status.modified)
        if status.staged:
            uncommitted.extend(status.staged)
        if status.untracked:
            uncommitted.extend(status.untracked)

        if uncommitted:
            check.has_uncommitted = True
            check.uncommitted_files = uncommitted
    except Exception:
        # If we can't check, be conservative and don't flag
        pass

    # Check 3: Unmerged PR
    pr_status = repo_entry.get("pr_status")
    pr_number = repo_entry.get("pr")

    if pr_status and pr_status != "merged" and pr_number:
        check.has_unmerged_pr = True
        check.pr_number = pr_number
        check.pr_status = pr_status

    return check


def confirm_removal(
    repos_to_remove: list[RepoToRemove],
    safety_checks: dict[tuple[str, str], SafetyCheck],
    project_dir: Path,
    force: bool,
    yes: bool,
    verbose: bool,
) -> bool:
    """Confirm removal with user, showing safety warnings.

    Args:
        repos_to_remove: List of repositories to remove
        safety_checks: Map of (url, branch) to SafetyCheck
        project_dir: Path to project directory
        force: Skip safety checks
        yes: Auto-confirm without prompt
        verbose: Show detailed file lists

    Returns:
        True if user confirms removal
    """
    # Build summary
    count = len(repos_to_remove)
    repo_word = "repository" if count == 1 else "repositories"

    click.echo(f"Will remove {count} {repo_word}:")
    click.echo()

    has_warnings = False
    for repo in repos_to_remove:
        key = (repo.url, repo.branch)
        check = safety_checks.get(key)

        click.echo(f"[{repo.index}] {repo.url} ({repo.branch})")
        click.echo(f"    Path: {repo.path}")

        if force:
            click.echo("    (skipped safety checks due to --force)")
        elif check and not check.is_safe():
            has_warnings = True
            warning = check.warning_message()
            click.echo(f"    ⚠️  {warning}")

            # Show file details if verbose
            if verbose and check.has_uncommitted and check.uncommitted_files:
                click.echo("        Uncommitted files:")
                for f in check.uncommitted_files[:5]:
                    click.echo(f"        - {f}")
                if len(check.uncommitted_files) > 5:
                    remaining = len(check.uncommitted_files) - 5
                    click.echo(f"        ... and {remaining} more")
        else:
            click.echo("    ✓ Safe to remove")

        click.echo()

    # Show warning if unsafe
    if has_warnings and not force:
        click.echo("⚠️  Some repositories have uncommitted/unpushed work that will be lost!")
        click.echo()

    # Auto-confirm with --yes
    if yes:
        return True

    # Prompt user
    prompt = f"Remove {'this' if count == 1 else 'these'} {repo_word}?"
    return click.confirm(prompt, default=False)


def remove_repository(
    repo: RepoToRemove, project_dir: Path, verbose: bool = False
) -> tuple[bool, str | None]:
    """Remove repository from config and filesystem.

    Steps:
    1. Remove entry from pyproject.toml via remove_repo_from_pyproject()
    2. Remove repository directory via shutil.rmtree()
    3. Handle errors gracefully (log but continue)

    Args:
        repo: Repository to remove
        project_dir: Project directory
        verbose: Enable verbose output

    Returns:
        Tuple of (success, error_message)
        - (True, None) if fully successful
        - (True, "warning") if config removed but directory failed
        - (False, "error") if config removal failed
    """
    from ..pyproject_utils import PyProjectUpdateError, remove_repo_from_pyproject

    # Step 1: Remove from pyproject.toml (CRITICAL - must succeed)
    try:
        removed_path = remove_repo_from_pyproject(project_dir, repo.url, repo.branch)
        if verbose:
            click.echo(f"Removed from config: {repo.url} ({repo.branch})")
    except PyProjectUpdateError as e:
        return (False, f"Failed to update config: {e}")

    # Step 2: Remove directory (NON-CRITICAL - warn on failure)
    if removed_path:
        repo_path = project_dir / removed_path

        if repo_path.exists():
            try:
                shutil.rmtree(repo_path)
                if verbose:
                    click.echo(f"Removed directory: {repo_path}")
            except OSError as e:
                return (True, f"Could not delete directory {repo_path}: {e}")
        else:
            if verbose:
                click.echo(f"Directory already removed: {repo_path}")

    return (True, None)


def update_workspace_after_removal(
    project_dir: Path, current_project: str, no_workspace: bool, verbose: bool
) -> None:
    """Regenerate workspace files after repository removal.

    Args:
        project_dir: Project directory
        current_project: Current project name
        no_workspace: Skip workspace regeneration
        verbose: Enable verbose output
    """
    if no_workspace:
        if verbose:
            click.echo("Skipping workspace regeneration (--no-workspace)")
        return

    try:
        from ..pyproject_utils import read_pyproject
        from .workspace import create_workspace_files

        if verbose:
            click.echo("Regenerating workspace files...")

        # Read updated repos from pyproject.toml
        pyproject = read_pyproject(project_dir)
        repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

        # Regenerate workspace files
        created_files = create_workspace_files(
            project_dir, repos, current_project, editor="all", verbose=verbose
        )

        if verbose:
            for _editor_name, file_path in created_files.items():
                rel_path = file_path.relative_to(project_dir)
                click.echo(f"  Updated: {rel_path}")
    except Exception as e:
        # Non-fatal: workspace regeneration is a convenience feature
        click.echo(f"Warning: Could not regenerate workspace files: {e}", err=True)


@click.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--force", "-f", is_flag=True, help="Force removal without safety checks")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm all prompts")
@click.option("--no-workspace", is_flag=True, help="Skip workspace file regeneration")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.pass_context
def rm(
    ctx: click.Context,
    repos: tuple[str, ...],
    force: bool,
    yes: bool,
    no_workspace: bool,
    verbose: bool,
) -> None:
    """Remove repositories from the current project.

    REPOS can be:

    \b
    - Repository indices (1-based): qen rm 1 3 5
    - Repository URLs: qen rm https://github.com/org/repo
    - Repository org/name: qen rm org/repo
    - Repository name: qen rm repo (requires org in config)

    \b
    Safety checks:
    - Warns about unpushed commits (ahead of remote)
    - Warns about uncommitted changes (modified/staged/untracked)
    - Warns about unmerged PRs (PR status != merged)

    Use --force to skip all safety checks.
    Use --yes to auto-confirm prompts.
    """
    from ..config import QenConfigError
    from ..init_utils import ensure_correct_branch, ensure_initialized

    # Get config overrides from context
    overrides = ctx.obj.get("config_overrides", {})

    # Load configuration (auto-initialize if needed)
    config = ensure_initialized(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
        verbose=verbose,
    )
    ensure_correct_branch(config, verbose=verbose, yes=yes)

    # Get current project
    main_config = config.read_main_config()
    current_project = main_config.get("current_project")
    if not current_project:
        raise click.ClickException(
            "No active project. Create a project with 'qen init <project-name>' first."
        )

    # Get project directory
    try:
        project_config = config.read_project_config(current_project)

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
        project_dir = per_project_meta / project_config["folder"]
        org = main_config.get("org")
    except QenConfigError as e:
        raise click.ClickException(f"Error reading configuration: {e}") from e

    # Phase 1: Parse identifiers
    try:
        repos_to_remove = parse_repo_identifiers(repos, project_dir, org)
    except click.ClickException:
        raise

    # Phase 2: Run safety checks (unless --force)
    safety_checks: dict[tuple[str, str], SafetyCheck] = {}
    if not force:
        for repo in repos_to_remove:
            repo_path = project_dir / repo.path
            check = check_repo_safety(repo_path, repo.repo_entry)
            safety_checks[(repo.url, repo.branch)] = check

    # Phase 3: Confirm with user
    if not confirm_removal(repos_to_remove, safety_checks, project_dir, force, yes, verbose):
        click.echo("Aborted. No repositories were removed.")
        raise click.Abort()

    # Phase 4: Execute removal
    click.echo()
    success_count = 0
    warnings = []
    errors = []

    for repo in repos_to_remove:
        success, error = remove_repository(repo, project_dir, verbose)

        if success:
            success_count += 1
            click.echo(f"✓ Removed [{repo.index}]: {repo.url}")
            if error:
                warnings.append(error)
        else:
            errors.append(f"[{repo.index}] {repo.url}: {error}")

    # Phase 5: Update workspace files
    click.echo()
    update_workspace_after_removal(project_dir, current_project, no_workspace, verbose)

    # Summary
    click.echo()
    if errors:
        click.echo("Errors occurred during removal:", err=True)
        for error in errors:
            click.echo(f"  ✗ {error}", err=True)
        raise click.ClickException("Some repositories could not be removed")

    if warnings:
        click.echo("Warnings:")
        for warning in warnings:
            click.echo(f"  ⚠️  {warning}")

    repo_word = "repository" if success_count == 1 else "repositories"
    click.echo(f"Successfully removed {success_count} {repo_word}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  - Review changes: git status")
    commit_msg = f"Remove {success_count} {'repository' if success_count == 1 else 'repositories'}"
    click.echo(f"  - Commit changes: git add pyproject.toml && git commit -m '{commit_msg}'")
