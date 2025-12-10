"""Commit command implementation for qen.

Commits changes across all sub-repositories within a QEN project.
"""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ..config import QenConfig, QenConfigError
from ..git_utils import GitError, run_git_command
from ..init_utils import ensure_correct_branch, ensure_initialized
from ..pyproject_utils import PyProjectNotFoundError, load_repos_from_pyproject


class CommitError(Exception):
    """Base exception for commit command errors."""

    pass


@dataclass
class CommitResult:
    """Result of committing a repository."""

    success: bool
    files_changed: int
    message: str
    skipped: bool = False
    error_message: str | None = None
    no_changes: bool = False


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
        # Check for any changes (modified, staged, untracked)
        status = run_git_command(["status", "--porcelain"], cwd=repo_path)
        return bool(status.strip())
    except GitError:
        return False


def is_merge_in_progress(repo_path: Path) -> bool:
    """Check if merge is in progress.

    Args:
        repo_path: Path to repository

    Returns:
        True if merge is in progress
    """
    return (repo_path / ".git" / "MERGE_HEAD").exists()


def is_rebase_in_progress(repo_path: Path) -> bool:
    """Check if rebase is in progress.

    Args:
        repo_path: Path to repository

    Returns:
        True if rebase is in progress
    """
    git_dir = repo_path / ".git"
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


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


def count_files_changed(repo_path: Path) -> tuple[int, int, int]:
    """Count files changed (modified, staged, untracked).

    Args:
        repo_path: Path to repository

    Returns:
        Tuple of (modified_count, staged_count, untracked_count)
    """
    try:
        status = run_git_command(["status", "--porcelain"], cwd=repo_path)
        lines = status.strip().split("\n")

        modified = 0
        staged = 0
        untracked = 0

        for line in lines:
            if not line:
                continue

            if len(line) < 2:
                continue

            status_code = line[:2]

            # Staged changes (index)
            if status_code[0] not in (" ", "?"):
                staged += 1

            # Unstaged changes (working tree)
            if status_code[1] not in (" ", "?"):
                modified += 1

            # Untracked files
            if status_code == "??":
                untracked += 1

        return (modified, staged, untracked)
    except GitError:
        return (0, 0, 0)


def commit_repo(
    repo_path: Path,
    message: str,
    amend: bool = False,
    no_add: bool = False,
    allow_empty: bool = False,
    verbose: bool = False,
) -> CommitResult:
    """Commit changes in a repository.

    Args:
        repo_path: Path to repository
        message: Commit message
        amend: If True, amend previous commit
        no_add: If True, don't auto-stage changes
        allow_empty: If True, allow empty commits
        verbose: If True, show detailed output

    Returns:
        CommitResult object
    """
    # Check for special git states
    if is_merge_in_progress(repo_path):
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Merge in progress. Complete or abort merge first (git merge --abort).",
        )

    if is_rebase_in_progress(repo_path):
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Rebase in progress. Complete or abort rebase first (git rebase --abort).",
        )

    # Check for detached HEAD
    if is_detached_head(repo_path):
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Detached HEAD. Checkout a branch first (git checkout main).",
        )

    # Stage changes if auto-add enabled
    if not no_add:
        try:
            run_git_command(["add", "-A"], cwd=repo_path)
            if verbose:
                click.echo("   Staged all changes")
        except GitError as e:
            return CommitResult(
                success=False,
                files_changed=0,
                message="",
                error_message=f"Failed to stage changes: {e}",
            )

    # Check if there are changes to commit
    try:
        status = run_git_command(["status", "--porcelain", "--untracked-files=no"], cwd=repo_path)
        if not status.strip() and not allow_empty:
            return CommitResult(
                success=True,
                files_changed=0,
                message="",
                no_changes=True,
            )
    except GitError:
        pass  # Continue anyway

    # Count files changed
    modified, staged, untracked = count_files_changed(repo_path)
    total_files = modified + staged + untracked

    # Build commit command
    cmd = ["commit", "-m", message]
    if amend:
        cmd.append("--amend")
    if allow_empty:
        cmd.append("--allow-empty")

    # Commit
    try:
        result = run_git_command(cmd, cwd=repo_path)
        if verbose:
            click.echo(f"   Git output: {result}")

        return CommitResult(
            success=True,
            files_changed=total_files,
            message=message,
        )

    except GitError as e:
        # Check if it's a hook failure
        error_str = str(e)
        if "hook" in error_str.lower():
            error_msg = f"Pre-commit hook failed:\n{error_str}"
        else:
            error_msg = f"Commit failed: {error_str}"

        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message=error_msg,
        )


def show_changes_summary(repo_path: Path, verbose: bool = False) -> None:
    """Show summary of changes in repository.

    Args:
        repo_path: Path to repository
        verbose: If True, show file list
    """
    try:
        status = run_git_command(["status", "--short"], cwd=repo_path)
        lines = [line for line in status.strip().split("\n") if line]

        if not lines:
            click.echo("   No changes")
            return

        modified, staged, untracked = count_files_changed(repo_path)

        parts = []
        if modified > 0:
            parts.append(f"{modified} modified")
        if staged > 0:
            parts.append(f"{staged} staged")
        if untracked > 0:
            parts.append(f"{untracked} untracked")

        click.echo(f"   {len(lines)} files changed: {', '.join(parts)}")

        if verbose:
            for line in lines[:10]:  # Show first 10 files
                click.echo(f"     {line}")
            if len(lines) > 10:
                click.echo(f"     ... and {len(lines) - 10} more")

    except GitError:
        click.echo("   (Cannot determine changes)")


def get_message_from_editor(default: str | None = None) -> str:
    """Open editor to get commit message.

    Args:
        default: Default message to pre-fill

    Returns:
        Commit message from editor
    """
    import os
    import tempfile

    # Create temp file with default message
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        if default:
            f.write(default + "\n")
        f.write("\n# Enter commit message above\n")
        f.write("# Lines starting with '#' will be ignored\n")
        temp_path = f.name

    try:
        # Open editor
        editor = os.environ.get("GIT_EDITOR") or os.environ.get("EDITOR", "vi")
        subprocess.run([editor, temp_path], check=True)

        # Read message
        with open(temp_path) as f:
            lines = [line for line in f.readlines() if not line.startswith("#")]
            message = "".join(lines).strip()

        return message
    finally:
        os.unlink(temp_path)


def commit_interactive(
    project_name: str,
    config: QenConfig,
    default_message: str | None = None,
    amend: bool = False,
    no_add: bool = False,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Commit repositories interactively.

    Args:
        project_name: Name of project
        config: QenConfig instance
        default_message: Default commit message
        amend: If True, amend previous commits
        no_add: If True, don't auto-stage changes
        verbose: If True, show detailed output
        config_overrides: Dictionary of config overrides (config_dir, meta_path, current_project)

    Returns:
        Dictionary with summary counts
    """
    # Load project configuration
    try:
        main_config = config.read_main_config()
        project_config = config.read_project_config(project_name)
        meta_path = Path(main_config["meta_path"])
    except QenConfigError as e:
        raise CommitError(f"Failed to load configuration: {e}") from e

    project_dir = meta_path / project_config["folder"]

    # Load repositories
    try:
        repos = load_repos_from_pyproject(project_dir)
    except (PyProjectNotFoundError, Exception) as e:
        raise CommitError(f"Failed to load repositories: {e}") from e

    results: list[tuple[str, CommitResult]] = []

    # Check if any repositories have changes before starting interactive mode
    repos_with_changes = []
    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        if has_uncommitted_changes(repo_path):
            repos_with_changes.append(repo_config)

    if not repos_with_changes:
        click.echo(f"Project: {project_name}")
        click.echo("\nNo repositories have uncommitted changes.")
        return {"committed": 0, "clean": len(repos), "skipped": 0, "failed": 0, "total_files": 0}

    click.echo(f"Committing project: {project_name} (interactive mode)\n")

    for repo_config in repos_with_changes:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        click.echo(f"\n📦 {repo_name} ({repo_config.branch})")

        # Show changes
        show_changes_summary(repo_path, verbose=verbose)

        # Prompt user
        choice = input("\n   Commit this repository? [Y/n/e/s] ").strip().lower()

        if choice == "n":
            click.echo("   Skipped")
            results.append(
                (
                    repo_name,
                    CommitResult(
                        success=True,
                        files_changed=0,
                        message="",
                        skipped=True,
                    ),
                )
            )
            continue

        if choice == "s":
            # Show detailed diff
            try:
                diff = run_git_command(["diff", "HEAD"], cwd=repo_path)
                click.echo("\n" + diff)
            except GitError:
                click.echo("   (Cannot show diff)")

            choice = input("\n   Commit this repository? [Y/n/e] ").strip().lower()
            if choice == "n":
                click.echo("   Skipped")
                results.append(
                    (
                        repo_name,
                        CommitResult(
                            success=True,
                            files_changed=0,
                            message="",
                            skipped=True,
                        ),
                    )
                )
                continue

        # Get commit message
        if choice == "e":
            message = get_message_from_editor(default_message)
        elif default_message:
            use_default = input("   Use default message? [Y/n] ").strip().lower()
            if use_default != "n":
                message = default_message
            else:
                message = input("   Commit message: ").strip()
        else:
            message = input("   Commit message: ").strip()

        if not message:
            click.echo("   ✗ No commit message provided. Skipped.")
            results.append(
                (
                    repo_name,
                    CommitResult(
                        success=False,
                        files_changed=0,
                        message="",
                        error_message="No message provided",
                    ),
                )
            )
            continue

        # Commit
        result = commit_repo(repo_path, message, amend=amend, no_add=no_add, verbose=verbose)

        if result.success:
            click.echo(f'   ✓ Committed: "{message}"')
        else:
            click.echo(f"   ✗ {result.error_message}")

        results.append((repo_name, result))

    # Print summary
    return print_commit_summary(results)


def commit_project(
    project_name: str | None = None,
    message: str | None = None,
    interactive: bool = False,
    amend: bool = False,
    no_add: bool = False,
    allow_empty: bool = False,
    specific_repo: str | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> None:
    """Commit all repositories in a project.

    Args:
        project_name: Name of project (None = use current)
        message: Commit message
        interactive: If True, prompt for each repo
        amend: If True, amend previous commits
        no_add: If True, don't auto-stage changes
        allow_empty: If True, allow empty commits
        specific_repo: If set, only commit this repository
        dry_run: If True, show what would be committed
        verbose: If True, show detailed output
        config_overrides: Dictionary of config overrides (config_dir, meta_path, current_project)

    Raises:
        click.ClickException: If commit fails
    """
    # Default to interactive mode if no message provided
    if not message and not interactive:
        interactive = True

    # Load configuration (auto-initialize if needed)
    overrides = config_overrides or {}
    config = ensure_initialized(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
        verbose=False,
    )

    # Ensure correct project branch after initialization
    ensure_correct_branch(config, verbose=False)

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

    # Interactive mode
    if interactive:
        try:
            summary = commit_interactive(
                target_project,
                config,
                default_message=message,
                amend=amend,
                no_add=no_add,
                verbose=verbose,
                config_overrides=overrides,
            )
            click.echo("\nSummary:")
            click.echo(f"  {summary['committed']} repositories committed")
            if summary["skipped"] > 0:
                click.echo(f"  {summary['skipped']} repositories skipped")
            if summary["failed"] > 0:
                click.echo(f"  {summary['failed']} repositories failed")
            return
        except CommitError as e:
            raise click.ClickException(str(e)) from e

    # Non-interactive mode
    try:
        project_config = config.read_project_config(target_project)
        meta_path = Path(main_config["meta_path"])
    except QenConfigError as e:
        raise click.ClickException(f"Failed to load project configuration: {e}") from e

    project_dir = meta_path / project_config["folder"]

    # Load repositories
    try:
        repos = load_repos_from_pyproject(project_dir)
    except (PyProjectNotFoundError, Exception) as e:
        raise click.ClickException(f"Failed to load repositories: {e}") from e

    results: list[tuple[str, CommitResult]] = []

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Committing project: {target_project}\n")

    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Skip if specific repo requested and this isn't it
        if specific_repo and repo_name != specific_repo:
            continue

        click.echo(f"📦 {repo_name} ({repo_config.branch})")

        # Check if repo has changes
        if not has_uncommitted_changes(repo_path):
            click.echo("   • No changes to commit (clean)")
            results.append(
                (
                    repo_name,
                    CommitResult(
                        success=True,
                        files_changed=0,
                        message="",
                        no_changes=True,
                    ),
                )
            )
            continue

        if dry_run:
            # Show what would be committed
            show_changes_summary(repo_path, verbose=verbose)
            click.echo(f'   Would commit: "{message}"')
            modified, staged, untracked = count_files_changed(repo_path)
            results.append(
                (
                    repo_name,
                    CommitResult(
                        success=True,
                        files_changed=modified + staged + untracked,
                        message=message or "",
                    ),
                )
            )
        else:
            # Actually commit
            result = commit_repo(
                repo_path,
                message or "",
                amend=amend,
                no_add=no_add,
                allow_empty=allow_empty,
                verbose=verbose,
            )

            if result.success and not result.no_changes:
                show_changes_summary(repo_path, verbose=verbose)
                click.echo(f'   ✓ Committed: "{message}"')
            elif result.no_changes:
                click.echo("   • No changes to commit (clean)")
            else:
                click.echo(f"   ✗ {result.error_message}")

            results.append((repo_name, result))

    # Print summary
    summary = print_commit_summary(results, dry_run=dry_run)

    if summary["failed"] > 0:
        sys.exit(1)


def print_commit_summary(
    results: list[tuple[str, CommitResult]], dry_run: bool = False
) -> dict[str, int]:
    """Print summary of commit operations.

    Args:
        results: List of (repo_name, CommitResult) tuples
        dry_run: If True, prefix with dry run indicator

    Returns:
        Dictionary with summary counts
    """
    prefix = "[DRY RUN] " if dry_run else ""

    committed = sum(1 for _, r in results if r.success and not r.no_changes and not r.skipped)
    clean = sum(1 for _, r in results if r.no_changes)
    skipped = sum(1 for _, r in results if r.skipped)
    failed = sum(1 for _, r in results if not r.success)

    total_files = sum(r.files_changed for _, r in results if r.success)

    click.echo(f"\n{prefix}Summary:")
    click.echo(f"  {len(results)} repositories processed")

    if committed > 0:
        file_word = "file" if total_files == 1 else "files"
        click.echo(f"  {committed} repositories committed ({total_files} {file_word} total)")

    if clean > 0:
        click.echo(f"  {clean} repositories clean")

    if skipped > 0:
        click.echo(f"  {skipped} repositories skipped")

    if failed > 0:
        click.echo(f"  {failed} repositories failed")

    return {
        "committed": committed,
        "clean": clean,
        "skipped": skipped,
        "failed": failed,
        "total_files": total_files,
    }


@click.command("commit")
@click.option("-m", "--message", help="Commit message for all repos")
@click.option("-i", "--interactive", is_flag=True, help="Interactive mode (prompt per repo)")
@click.option("--amend", is_flag=True, help="Amend previous commit in each repo")
@click.option("--no-add", is_flag=True, help="Don't auto-stage changes (commit staged only)")
@click.option("--allow-empty", is_flag=True, help="Allow empty commits")
@click.option("--repo", help="Commit only specific repository")
@click.option("--dry-run", is_flag=True, help="Show what would be committed")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
@click.option("--project", help="Project name (default: current project)")
@click.pass_context
def commit_command(
    ctx: click.Context,
    message: str | None,
    interactive: bool,
    amend: bool,
    no_add: bool,
    allow_empty: bool,
    repo: str | None,
    dry_run: bool,
    verbose: bool,
    project: str | None,
) -> None:
    """Commit changes across all repositories in the current project.

    By default, commits all repositories with uncommitted changes using
    the same commit message. Clean repositories are automatically skipped.

    Examples:

    \b
        # Commit all dirty repos
        $ qen commit -m "Fix authentication bug"

    \b
        # Interactive mode (customize per repo)
        $ qen commit --interactive

    \b
        # Commit specific repo
        $ qen commit -m "Update docs" --repo repos/api

    \b
        # Amend previous commits
        $ qen commit --amend -m "Fix bug (include tests)"

    \b
        # Show what would be committed
        $ qen commit -m "Test" --dry-run
    """
    try:
        overrides = ctx.obj.get("config_overrides", {})
        commit_project(
            project_name=project,
            message=message,
            interactive=interactive,
            amend=amend,
            no_add=no_add,
            allow_empty=allow_empty,
            specific_repo=repo,
            dry_run=dry_run,
            verbose=verbose,
            config_overrides=overrides,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
