"""Delete qen projects with safety checks.

This module implements the `qen del` command which safely deletes qen projects by:

1. Safety checks - Detect uncommitted changes and unpushed commits
2. Config cleanup - Remove project configuration from XDG directory
3. Filesystem cleanup - Remove per-project meta repository directory
4. Remote cleanup - Optionally delete remote branch with --remote flag

The command provides multiple deletion modes:
- Default: Delete both config and local repo
- --config-only: Delete only config, preserve repo
- --repo-only: Delete only repo, preserve config
- --remote: Also delete remote branch (requires explicit confirmation)
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click


@dataclass
class ProjectDeletionPlan:
    """Plan for project deletion."""

    project_name: str
    config_path: Path | None
    repo_path: Path | None
    remote_branch: str | None
    delete_config: bool
    delete_repo: bool
    delete_remote: bool
    uncommitted_count: int = 0
    unpushed_count: int = 0

    def has_warnings(self) -> bool:
        """Check if there are any safety warnings."""
        return self.uncommitted_count > 0 or self.unpushed_count > 0

    def warning_message(self) -> str:
        """Generate warning message for unsafe deletion."""
        parts = []
        if self.uncommitted_count > 0:
            file_word = "file" if self.uncommitted_count == 1 else "files"
            parts.append(f"{self.uncommitted_count} uncommitted {file_word}")
        if self.unpushed_count > 0:
            commit_word = "commit" if self.unpushed_count == 1 else "commits"
            parts.append(f"{self.unpushed_count} unpushed {commit_word}")
        return " • " + "\n • ".join(parts)


def check_uncommitted_changes(repo_path: Path) -> int:
    """Check for uncommitted changes in repository.

    Args:
        repo_path: Path to git repository

    Returns:
        Count of uncommitted files (staged + modified + untracked)
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        # Count non-empty lines
        lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
        return len(lines)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If git command fails, assume no changes
        return 0


def check_unpushed_commits(repo_path: Path, branch: str) -> int:
    """Check for unpushed commits in repository.

    Args:
        repo_path: Path to git repository
        branch: Branch name to check

    Returns:
        Count of unpushed commits (commits ahead of remote)
    """
    try:
        # Check if branch has an upstream
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        # Count commits ahead of upstream
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{branch}@{{upstream}}..{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        # If upstream doesn't exist or command fails, assume no unpushed commits
        return 0


def remote_branch_exists(repo_path: Path, branch: str) -> bool:
    """Check if remote branch exists.

    Args:
        repo_path: Path to git repository
        branch: Branch name to check

    Returns:
        True if remote branch exists
    """
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def delete_remote_branch(repo_path: Path, branch: str) -> tuple[bool, str | None]:
    """Delete remote branch.

    Args:
        repo_path: Path to git repository
        branch: Branch name to delete

    Returns:
        Tuple of (success, error_message)
    """
    try:
        subprocess.run(
            ["git", "push", "--delete", "origin", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return (True, None)
    except subprocess.CalledProcessError as e:
        return (False, e.stderr.strip() if e.stderr else str(e))
    except FileNotFoundError:
        return (False, "Git is not installed or not in PATH")


def create_deletion_plan(
    project_name: str,
    config_path: Path | None,
    repo_path: Path | None,
    branch: str | None,
    config_only: bool,
    repo_only: bool,
    remote: bool,
) -> ProjectDeletionPlan:
    """Create a deletion plan with safety checks.

    Args:
        project_name: Name of project
        config_path: Path to config file (or None if doesn't exist)
        repo_path: Path to repo directory (or None if doesn't exist)
        branch: Branch name (or None if unknown)
        config_only: Delete only config
        repo_only: Delete only repo
        remote: Also delete remote branch

    Returns:
        ProjectDeletionPlan with all details
    """
    # Determine what to delete based on flags
    if config_only:
        delete_config = True
        delete_repo = False
    elif repo_only:
        delete_config = False
        delete_repo = True
    else:
        delete_config = True
        delete_repo = True

    delete_remote = remote

    # Run safety checks on repo if it exists and will be deleted
    uncommitted_count = 0
    unpushed_count = 0

    if delete_repo and repo_path and repo_path.exists():
        uncommitted_count = check_uncommitted_changes(repo_path)
        if branch:
            unpushed_count = check_unpushed_commits(repo_path, branch)

    # Determine remote branch (only if repo exists and branch is known)
    remote_branch = None
    if repo_path and branch and remote_branch_exists(repo_path, branch):
        remote_branch = branch

    return ProjectDeletionPlan(
        project_name=project_name,
        config_path=config_path,
        repo_path=repo_path,
        remote_branch=remote_branch,
        delete_config=delete_config,
        delete_repo=delete_repo,
        delete_remote=delete_remote,
        uncommitted_count=uncommitted_count,
        unpushed_count=unpushed_count,
    )


def display_deletion_plan(plan: ProjectDeletionPlan) -> None:
    """Display what will be deleted to the user.

    Args:
        plan: Deletion plan to display
    """
    click.echo(f"Delete project '{plan.project_name}':")

    # Show config status
    if plan.config_path:
        status = "✓" if plan.delete_config else "✗"
        action = "" if plan.delete_config else " (will NOT be deleted)"
        click.echo(f"  {status} Config: {plan.config_path}{action}")
    else:
        click.echo("  ✗ Config: Not found")

    # Show repo status
    if plan.repo_path:
        status = "✓" if plan.delete_repo else "✗"
        action = "" if plan.delete_repo else " (will NOT be deleted)"
        branch_info = f" (branch: {plan.remote_branch})" if plan.remote_branch else ""
        click.echo(f"  {status} Repo: {plan.repo_path}{branch_info}{action}")
    else:
        click.echo("  ✗ Repo: Not found")

    # Show remote status
    if plan.remote_branch:
        status = "✓" if plan.delete_remote else "✗"
        action = "" if plan.delete_remote else " (will NOT be deleted)"
        click.echo(f"  {status} Remote: origin/{plan.remote_branch}{action}")
    else:
        click.echo("  ✗ Remote: Not found or not tracked")

    # Show warnings
    if plan.has_warnings():
        click.echo()
        click.echo("⚠️  Warning: Uncommitted changes:")
        click.echo(plan.warning_message())


def confirm_deletion(plan: ProjectDeletionPlan, yes: bool) -> bool:
    """Confirm deletion with user.

    Args:
        plan: Deletion plan
        yes: Auto-confirm without prompting

    Returns:
        True if user confirms deletion
    """
    # Display plan
    click.echo()
    display_deletion_plan(plan)
    click.echo()

    # Extra warning for remote deletion
    if plan.delete_remote and plan.remote_branch:
        click.echo("⚠️  WARNING: This will delete the remote branch! This action cannot be undone.")
        click.echo()

    # Auto-confirm with --yes
    if yes:
        return True

    # Build prompt message
    parts = []
    if plan.delete_config:
        parts.append("config")
    if plan.delete_repo:
        parts.append("repo")
    if plan.delete_remote:
        parts.append("remote")

    if not parts:
        click.echo("Nothing to delete.")
        return False

    prompt = f"Delete {' and '.join(parts)}? [y/N]"
    return click.confirm(prompt, default=False)


def execute_deletion(plan: ProjectDeletionPlan, verbose: bool = False) -> tuple[bool, list[str]]:
    """Execute the deletion plan.

    Args:
        plan: Deletion plan to execute
        verbose: Enable verbose output

    Returns:
        Tuple of (success, errors)
    """
    errors = []

    # Delete config
    if plan.delete_config and plan.config_path:
        try:
            plan.config_path.unlink()
            if verbose:
                click.echo(f"✓ Deleted config: {plan.config_path}")
        except OSError as e:
            errors.append(f"Failed to delete config: {e}")

    # Delete remote branch
    if plan.delete_remote and plan.repo_path and plan.remote_branch:
        if verbose:
            click.echo(f"Deleting remote branch: origin/{plan.remote_branch}...")
        success, error = delete_remote_branch(plan.repo_path, plan.remote_branch)
        if success:
            if verbose:
                click.echo(f"✓ Deleted remote branch: origin/{plan.remote_branch}")
        else:
            errors.append(f"Failed to delete remote branch: {error}")

    # Delete repo (must be last in case remote deletion needs it)
    if plan.delete_repo and plan.repo_path:
        try:
            if plan.repo_path.exists():
                shutil.rmtree(plan.repo_path)
                if verbose:
                    click.echo(f"✓ Deleted repo: {plan.repo_path}")
        except OSError as e:
            errors.append(f"Failed to delete repo: {e}")

    return (len(errors) == 0, errors)


@click.command("del")
@click.argument("project_name")
@click.option(
    "--config-only",
    is_flag=True,
    help="Delete only config, leave repo",
)
@click.option(
    "--repo-only",
    is_flag=True,
    help="Delete only repo, leave config",
)
@click.option(
    "--remote",
    is_flag=True,
    help="Also delete remote branch (WARNING: cannot be undone)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.pass_context
def del_command(
    ctx: click.Context,
    project_name: str,
    config_only: bool,
    repo_only: bool,
    remote: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """Delete a qen project.

    By default, deletes both config and local repository.
    Use --config-only or --repo-only to delete selectively.
    Use --remote to also delete the remote branch (requires confirmation).

    Examples:

    \b
        # Delete project (config + repo)
        $ qen del myproject

    \b
        # Delete only config
        $ qen del myproject --config-only

    \b
        # Delete only repo
        $ qen del myproject --repo-only

    \b
        # Delete everything including remote
        $ qen del myproject --remote

    \b
        # Skip confirmation
        $ qen del myproject --yes
    """
    from ..config import QenConfig, QenConfigError

    # Validate flags
    if config_only and repo_only:
        raise click.ClickException("Cannot use both --config-only and --repo-only")

    # Get config overrides from context
    overrides = ctx.obj.get("config_overrides", {})

    # Load configuration
    config = QenConfig(
        config_dir=overrides.get("config_dir"),
        storage=None,
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )

    # Check if project exists
    if not config.project_config_exists(project_name):
        raise click.ClickException(
            f"Project '{project_name}' not found.\n"
            f"Run 'qen config --list' to see available projects."
        )

    # Load project config
    try:
        project_config = config.read_project_config(project_name)
        config_path = config.get_project_config_path(project_name)
        repo_path = Path(project_config["repo"]) if "repo" in project_config else None
        branch = project_config.get("branch")
    except QenConfigError as e:
        raise click.ClickException(f"Error reading project config: {e}") from e

    # Handle missing repo path (legacy config)
    if not repo_path:
        click.echo(
            f"Warning: Project '{project_name}' uses old configuration format.\n"
            f"Only config can be deleted (no per-project meta clone found).",
            err=True,
        )
        if not config_only:
            if not yes and not click.confirm(
                "Delete config only?",
                default=False,
            ):
                raise click.Abort()
            config_only = True

    # Create deletion plan with safety checks
    plan = create_deletion_plan(
        project_name=project_name,
        config_path=config_path if config_path.exists() else None,
        repo_path=repo_path if repo_path and repo_path.exists() else None,
        branch=branch,
        config_only=config_only,
        repo_only=repo_only,
        remote=remote,
    )

    # Confirm with user
    if not confirm_deletion(plan, yes):
        click.echo("Aborted. Nothing was deleted.")
        raise click.Abort()

    # Execute deletion
    click.echo()
    if verbose:
        click.echo("Executing deletion...")
    success, errors = execute_deletion(plan, verbose=verbose)

    # Report results
    click.echo()
    if errors:
        click.echo("Errors occurred during deletion:", err=True)
        for error in errors:
            click.echo(f"  ✗ {error}", err=True)
        raise click.ClickException("Project deletion incomplete")

    click.echo(f"✓ Successfully deleted project '{project_name}'")

    # Update current_project if needed
    try:
        main_config = config.read_main_config()
        if main_config.get("current_project") == project_name:
            config.update_current_project(None)
            if verbose:
                click.echo("✓ Cleared current project from config")
    except QenConfigError:
        # Non-fatal: config might not exist or be accessible
        pass
