"""Push command implementation for qen.

Pushes local commits across all sub-repositories within a QEN project.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ..config import QenConfigError
from ..git_utils import GitError, run_git_command
from ..init_utils import ensure_correct_branch, ensure_initialized
from ..pyproject_utils import PyProjectNotFoundError, load_repos_from_pyproject


class PushError(Exception):
    """Base exception for push command errors."""

    pass


@dataclass
class PushResult:
    """Result of pushing a repository."""

    success: bool
    commits_pushed: int
    nothing_to_push: bool
    skipped: bool = False
    error_message: str | None = None


def has_uncommitted_changes(repo_path: Path) -> bool:
    """Check if repository has uncommitted changes.

    Args:
        repo_path: Path to repository

    Returns:
        True if there are uncommitted changes
    """
    if not repo_path.exists():
        return False

    try:
        status = run_git_command(["status", "--porcelain"], cwd=repo_path)
        return bool(status.strip())
    except GitError:
        return False


def is_detached_head(repo_path: Path) -> bool:
    """Check if repository is in detached HEAD state.

    Args:
        repo_path: Path to repository

    Returns:
        True if in detached HEAD state
    """
    try:
        branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)
        return branch.strip() == "HEAD"
    except GitError:
        return True


def count_commits_to_push(repo_path: Path) -> int | None:
    """Count commits ahead of remote.

    Args:
        repo_path: Path to repository

    Returns:
        Number of commits ahead, or None if no upstream
    """
    try:
        count = run_git_command(
            ["rev-list", "--count", "@{upstream}..HEAD"],
            cwd=repo_path,
        )
        return int(count.strip())
    except GitError:
        return None


def has_upstream_branch(repo_path: Path) -> bool:
    """Check if branch has upstream configured.

    Args:
        repo_path: Path to repository

    Returns:
        True if upstream is configured
    """
    try:
        run_git_command(["rev-parse", "@{upstream}"], cwd=repo_path)
        return True
    except GitError:
        return False


def parse_push_error(error: GitError) -> str:
    """Parse git push error and return user-friendly message.

    Args:
        error: GitError exception

    Returns:
        User-friendly error message
    """
    stderr = str(error).lower()

    if "rejected" in stderr and ("non-fast-forward" in stderr or "would be overwritten" in stderr):
        return "Remote has commits you don't have. Run 'qen pull' first."

    if "no upstream" in stderr or "does not track" in stderr:
        return "No upstream branch configured. Use --set-upstream."

    if "could not resolve host" in stderr or "failed to connect" in stderr:
        return "Network error: Cannot reach remote."

    if "authentication failed" in stderr or "permission denied" in stderr:
        return "Authentication failed. Check credentials."

    if "protected branch" in stderr:
        return "Branch is protected. Check repository settings."

    return f"Push failed: {error}"


def push_repo(
    repo_path: Path,
    branch: str,
    force_with_lease: bool = False,
    force: bool = False,
    set_upstream: bool = False,
    allow_dirty: bool = False,
    verbose: bool = False,
) -> PushResult:
    """Push local commits to remote branch.

    Args:
        repo_path: Path to repository
        branch: Branch name
        force_with_lease: If True, force push with lease
        force: If True, force push (dangerous)
        set_upstream: If True, set upstream tracking
        allow_dirty: If True, allow push with uncommitted changes
        verbose: If True, show detailed output

    Returns:
        PushResult object
    """
    # Check for uncommitted changes
    if not allow_dirty and has_uncommitted_changes(repo_path):
        return PushResult(
            success=False,
            commits_pushed=0,
            nothing_to_push=False,
            error_message="Uncommitted changes detected. Commit changes or use --allow-dirty.",
        )

    # Check if there's anything to push
    commits_to_push = count_commits_to_push(repo_path)

    if commits_to_push is None:
        # No upstream branch
        if not set_upstream:
            return PushResult(
                success=False,
                commits_pushed=0,
                nothing_to_push=False,
                error_message="No upstream branch configured. Use --set-upstream.",
            )
        # Will set upstream during push, count local commits
        try:
            result = run_git_command(["rev-list", "--count", "HEAD"], cwd=repo_path)
            commits_to_push = int(result.strip())
        except GitError:
            commits_to_push = 0

    if commits_to_push == 0:
        return PushResult(
            success=True,
            commits_pushed=0,
            nothing_to_push=True,
        )

    # Build push command
    cmd = ["push"]

    if force:
        cmd.append("--force")
    elif force_with_lease:
        cmd.append("--force-with-lease")

    if set_upstream:
        cmd.extend(["-u", "origin", branch])
    else:
        cmd.extend(["origin", branch])

    # Push with appropriate flags
    try:
        output = run_git_command(cmd, cwd=repo_path)
        if verbose:
            click.echo(f"   Git output: {output}")

        return PushResult(
            success=True,
            commits_pushed=commits_to_push,
            nothing_to_push=False,
        )

    except GitError as e:
        error_msg = parse_push_error(e)
        return PushResult(
            success=False,
            commits_pushed=0,
            nothing_to_push=False,
            error_message=error_msg,
        )


def push_project(
    project_name: str | None = None,
    dry_run: bool = False,
    force_with_lease: bool = False,
    force: bool = False,
    set_upstream: bool = False,
    allow_dirty: bool = False,
    specific_repo: str | None = None,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> None:
    """Push all repositories in a project.

    Args:
        project_name: Name of project (None = use current)
        dry_run: If True, show what would be pushed
        force_with_lease: If True, force push with lease
        force: If True, force push (dangerous)
        set_upstream: If True, set upstream for new branches
        allow_dirty: If True, allow push with uncommitted changes
        specific_repo: If set, only push this repository
        verbose: If True, show detailed output
        config_overrides: Dictionary of config overrides (config_dir, meta_path, current_project)

    Raises:
        click.ClickException: If push fails
    """
    # Confirm force push if requested
    if force and not dry_run:
        confirm = input("⚠️  Force push will overwrite remote. Continue? [y/N] ")
        if confirm.lower() != "y":
            click.echo("Push cancelled.")
            return

    # Load configuration (auto-initialize if needed)
    overrides = config_overrides or {}
    config = ensure_initialized(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
        verbose=False,
    )

    # Ensure the correct project branch is checked out
    ensure_correct_branch(config, verbose=verbose)

    # Config is guaranteed to exist after ensure_initialized
    main_config = config.read_main_config()

    # Determine which project to use
    if project_name:
        target_project = project_name
    else:
        target_project_raw = main_config.get("current_project")
        if not target_project_raw:
            raise click.ClickException(
                "No active project. Create a project with 'qen init <project-name>' first."
            )
        target_project = str(target_project_raw)

    # Load project configuration
    try:
        project_config = config.read_project_config(target_project)
    except QenConfigError as e:
        raise click.ClickException(f"Failed to load project configuration: {e}") from e

    # Check for per-project meta (new format)
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

    # Load repositories
    try:
        repos = load_repos_from_pyproject(project_dir)
    except (PyProjectNotFoundError, Exception) as e:
        raise click.ClickException(f"Failed to load repositories: {e}") from e

    results: list[tuple[str, PushResult]] = []

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Pushing project: {target_project}\n")

    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Skip if specific repo requested and this isn't it
        if specific_repo and repo_name != specific_repo:
            continue

        click.echo(f"📦 {repo_name} ({repo_config.branch})")

        # Check if repo exists
        if not repo_path.exists():
            click.echo("   ⚠ Repository not cloned. Skipping.")
            results.append(
                (
                    repo_name,
                    PushResult(
                        success=False,
                        commits_pushed=0,
                        nothing_to_push=False,
                        skipped=True,
                    ),
                )
            )
            continue

        # Check for detached HEAD
        if is_detached_head(repo_path):
            click.echo("   ✗ Cannot push from detached HEAD")
            click.echo("   Suggestion: Checkout a branch first")
            results.append(
                (
                    repo_name,
                    PushResult(
                        success=False,
                        commits_pushed=0,
                        nothing_to_push=False,
                        error_message="Detached HEAD",
                    ),
                )
            )
            continue

        # Check for uncommitted changes
        if has_uncommitted_changes(repo_path) and not allow_dirty:
            click.echo("   ✗ Uncommitted changes detected")
            click.echo()
            click.echo("    Modified files:")

            try:
                status = run_git_command(["status", "--short"], cwd=repo_path)
                for line in status.strip().split("\n")[:5]:
                    if line:
                        click.echo(f"      - {line}")
                if len(status.strip().split("\n")) > 5:
                    click.echo("      ... and more")
            except GitError:
                pass

            click.echo()
            click.echo("    Options:")
            click.echo('      1. Commit changes: qen commit -m "your message"')
            click.echo("      2. Stash changes:  git stash")
            click.echo("      3. Allow anyway:   qen push --allow-dirty")

            results.append(
                (
                    repo_name,
                    PushResult(
                        success=False,
                        commits_pushed=0,
                        nothing_to_push=False,
                        error_message="Uncommitted changes",
                    ),
                )
            )
            continue

        if has_uncommitted_changes(repo_path) and allow_dirty:
            click.echo("   ⚠ Uncommitted changes (will not be pushed)")

        # Count commits to push
        commits = count_commits_to_push(repo_path)

        if commits is None and not set_upstream:
            click.echo("   ✗ No upstream branch configured")
            click.echo("   Suggestion: Use --set-upstream to set upstream tracking")
            results.append(
                (
                    repo_name,
                    PushResult(
                        success=False,
                        commits_pushed=0,
                        nothing_to_push=False,
                        error_message="No upstream",
                    ),
                )
            )
            continue

        if commits == 0:
            click.echo("   • Already up-to-date (0 commits to push)")
            results.append(
                (
                    repo_name,
                    PushResult(
                        success=True,
                        commits_pushed=0,
                        nothing_to_push=True,
                    ),
                )
            )
            continue

        if dry_run:
            # Show what would be pushed
            commit_word = "commit" if commits == 1 else "commits"
            click.echo(f"   Would push: {commits} {commit_word} to origin/{repo_config.branch}")
            results.append(
                (
                    repo_name,
                    PushResult(
                        success=True,
                        commits_pushed=commits or 0,
                        nothing_to_push=False,
                    ),
                )
            )
        else:
            # Actually push
            result = push_repo(
                repo_path,
                repo_config.branch,
                force_with_lease=force_with_lease,
                force=force,
                set_upstream=set_upstream,
                allow_dirty=allow_dirty,
                verbose=verbose,
            )

            if result.success:
                if not result.nothing_to_push:
                    commit_word = "commit" if result.commits_pushed == 1 else "commits"
                    click.echo(
                        f"   ✓ Pushed {result.commits_pushed} {commit_word} to origin/{repo_config.branch}"
                    )
            else:
                click.echo(f"   ✗ {result.error_message}")

            results.append((repo_name, result))

    # Print summary
    summary = print_push_summary(results, dry_run=dry_run)

    if summary["failed"] > 0:
        sys.exit(1)


def print_push_summary(
    results: list[tuple[str, PushResult]], dry_run: bool = False
) -> dict[str, int]:
    """Print summary of push operations.

    Args:
        results: List of (repo_name, PushResult) tuples
        dry_run: If True, prefix with dry run indicator

    Returns:
        Dictionary with summary counts
    """
    prefix = "[DRY RUN] " if dry_run else ""

    pushed = sum(1 for _, r in results if r.success and not r.nothing_to_push and not r.skipped)
    up_to_date = sum(1 for _, r in results if r.nothing_to_push)
    failed = sum(1 for _, r in results if not r.success and not r.skipped)
    skipped = sum(1 for _, r in results if r.skipped)

    total_commits = sum(r.commits_pushed for _, r in results if r.success)

    click.echo(f"\n{prefix}Summary:")
    click.echo(f"  {len(results)} repositories processed")

    if pushed > 0:
        commit_word = "commit" if total_commits == 1 else "commits"
        if dry_run:
            click.echo(f"  Would push {pushed} repositories ({total_commits} {commit_word})")
        else:
            click.echo(f"  {pushed} repositories pushed ({total_commits} {commit_word})")

    if up_to_date > 0:
        click.echo(f"  {up_to_date} repositories up-to-date")

    if skipped > 0:
        click.echo(f"  {skipped} repositories skipped (not cloned)")

    if failed > 0:
        click.echo(f"  {failed} repositories failed")

    if failed > 0 and not dry_run:
        click.echo()
        click.echo("Push failed: Some repositories could not be pushed")

    if failed > 0 and any("Uncommitted changes" in (r.error_message or "") for _, r in results):
        click.echo()
        click.echo("⚠ Reminder: Repositories with uncommitted changes were not pushed")
        click.echo("   Run 'qen commit' to commit changes first, or use --allow-dirty")

    return {
        "pushed": pushed,
        "up_to_date": up_to_date,
        "failed": failed,
        "skipped": skipped,
        "total_commits": total_commits,
    }


@click.command("push")
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without pushing")
@click.option("--allow-dirty", is_flag=True, help="Allow push even with uncommitted changes")
@click.option("--force-with-lease", is_flag=True, help="Force push with lease (safer than --force)")
@click.option("--force", is_flag=True, help="Force push (dangerous, overwrites remote)")
@click.option("--set-upstream", is_flag=True, help="Set upstream for branches without tracking")
@click.option("--repo", help="Push only specific repository")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed git output")
@click.option("--project", help="Project name (default: current project)")
@click.pass_context
def push_command(
    ctx: click.Context,
    dry_run: bool,
    allow_dirty: bool,
    force_with_lease: bool,
    force: bool,
    set_upstream: bool,
    repo: str | None,
    verbose: bool,
    project: str | None,
) -> None:
    """Push local commits across all repositories in the current project.

    By default, pushes all repositories with unpushed commits. Repositories
    that are already up-to-date are skipped. Uncommitted changes block push
    by default to avoid confusion about what is being pushed.

    Examples:

    \b
        # Push all repos with unpushed commits
        $ qen push

    \b
        # Show what would be pushed
        $ qen push --dry-run

    \b
        # Push with uncommitted changes
        $ qen push --allow-dirty

    \b
        # Force push with lease (safer)
        $ qen push --force-with-lease

    \b
        # Set upstream for new branches
        $ qen push --set-upstream

    \b
        # Push specific repository
        $ qen push --repo repos/api
    """
    try:
        overrides = ctx.obj.get("config_overrides", {})
        push_project(
            project_name=project,
            dry_run=dry_run,
            force_with_lease=force_with_lease,
            force=force,
            set_upstream=set_upstream,
            allow_dirty=allow_dirty,
            specific_repo=repo,
            verbose=verbose,
            config_overrides=overrides,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
