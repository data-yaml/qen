"""Auto-initialization utilities for qen commands.

This module provides the ensure_initialized() helper function that automatically
initializes qen configuration when it doesn't exist, enabling a seamless first-run
experience for users.

Key behaviors:
- Returns immediately if config already exists (zero overhead)
- Auto-initializes silently by default (verbose mode shows progress)
- Provides helpful error messages when auto-init cannot proceed
- Works seamlessly with runtime overrides (--meta, --project)
"""

from pathlib import Path

import click

from qenvy.base import QenvyBase

from .config import QenConfig
from .git_utils import (
    AmbiguousOrgError,
    GitError,
    MetaRepoNotFoundError,
    NotAGitRepoError,
)


def ensure_initialized(
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
    verbose: bool = False,
) -> QenConfig:
    """Ensure qen is initialized, auto-initializing if possible.

    This function guarantees that a valid QenConfig instance is returned with
    the main configuration file present. If the main config doesn't exist, it
    attempts to auto-initialize by:

    1. Detecting the meta repository (searching upward or using override)
    2. Extracting the GitHub organization from git remotes
    3. Creating the configuration silently

    If auto-initialization cannot proceed (e.g., not in a git repo, multiple
    organizations detected), it provides helpful error messages with actionable
    guidance for the user.

    Args:
        config_dir: Override configuration directory (for testing)
        storage: Override storage backend (for testing with in-memory storage)
        meta_path_override: Runtime override for meta repository path
        current_project_override: Runtime override for current project name
        verbose: Enable verbose output (shows auto-init progress)

    Returns:
        QenConfig instance with guaranteed main configuration

    Raises:
        click.Abort: If auto-initialization fails with helpful error message

    Example:
        >>> # In any command implementation:
        >>> config = ensure_initialized(
        ...     config_dir=config_dir,
        ...     storage=storage,
        ...     meta_path_override=meta_path_override,
        ...     current_project_override=current_project_override,
        ...     verbose=verbose,
        ... )
        >>> # Config is now guaranteed to exist
        >>> main_config = config.read_main_config()
    """
    # Create QenConfig instance
    config = QenConfig(
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Check if config exists - if yes, return immediately (fast path)
    if config.main_config_exists():
        return config

    # Config doesn't exist - attempt auto-initialization
    if verbose:
        click.echo("Configuration not found. Auto-initializing...")

    try:
        # Import here to avoid circular dependency
        # (commands.init imports config, which would import this if at top level)
        from .commands.init import init_qen

        # Call existing init logic
        # Note: init_qen() will call click.Abort() on its own errors,
        # but we catch and enhance specific error types below
        init_qen(
            verbose=False,  # Suppress init_qen's own output (we handle messaging)
            storage=storage,
            config_dir=config_dir,
            meta_path_override=meta_path_override,
            current_project_override=current_project_override,
        )

        if verbose:
            click.echo("✓ Auto-initialized qen configuration")

        return config

    except (NotAGitRepoError, MetaRepoNotFoundError) as e:
        # Cannot auto-init - not in a git repo or can't find meta repo
        # Provide actionable guidance for the user
        click.echo("Error: qen is not initialized.", err=True)
        click.echo(f"Reason: {e}", err=True)
        click.echo(err=True)
        click.echo("To initialize qen:", err=True)
        click.echo("  1. Navigate to your meta repository", err=True)
        click.echo("  2. Run: qen init", err=True)
        click.echo(err=True)
        click.echo("Or specify meta repo explicitly:", err=True)
        click.echo("  qen --meta /path/to/meta <command>", err=True)
        raise click.Abort() from e

    except AmbiguousOrgError as e:
        # Cannot auto-init - ambiguous organization
        # User must manually run qen init to select which org to use
        click.echo("Error: Cannot auto-initialize qen.", err=True)
        click.echo(f"Reason: {e}", err=True)
        click.echo(err=True)
        click.echo("Please run 'qen init' manually to configure.", err=True)
        raise click.Abort() from e

    except GitError as e:
        # Cannot auto-init - general git error
        # User should manually run qen init
        click.echo("Error: Cannot auto-initialize qen.", err=True)
        click.echo(f"Reason: {e}", err=True)
        click.echo(err=True)
        click.echo("Please run 'qen init' manually to configure.", err=True)
        raise click.Abort() from e


def ensure_correct_branch(
    config: QenConfig,
    verbose: bool = False,
) -> None:
    """Ensure meta repository is on the correct project branch.

    Similar to ensure_initialized(), this function validates that the user is on
    the expected project branch before executing commands.

    If on wrong branch:
    - Clean meta repo: Prompts to switch with [Y/n]
    - Dirty meta repo: Errors and tells user to commit/stash first

    Args:
        config: Loaded QenConfig instance
        verbose: Enable verbose output

    Raises:
        click.Abort: If on wrong branch and user declines to switch, or has uncommitted changes

    Example:
        >>> config = ensure_initialized(...)
        >>> ensure_correct_branch(config, verbose=verbose)
        >>> # Now guaranteed to be on correct branch (or user accepted switch)
    """
    # Import here to avoid circular dependency
    from .git_utils import checkout_branch, get_current_branch, has_uncommitted_changes
    from .project import generate_branch_name

    # 1. Get expected branch from config
    main_config = config.read_main_config()
    current_project = main_config.get("current_project")

    if not current_project:
        # No active project - nothing to check
        return

    expected_branch = generate_branch_name(current_project)

    # 2. Check current branch
    meta_path = Path(main_config["meta_path"])
    current_branch = get_current_branch(meta_path)

    if current_branch == expected_branch:
        # On correct branch - fast path
        return

    # 3. Wrong branch - check for uncommitted changes
    if has_uncommitted_changes(meta_path):
        click.echo(
            f"Error: Not on project branch '{expected_branch}' (currently on '{current_branch}')",
            err=True,
        )
        click.echo("You have uncommitted changes in the meta repository.", err=True)
        click.echo("Please commit or stash them first.", err=True)
        click.echo(f"\nThen run: qen config {current_project}", err=True)
        raise click.Abort()

    # 4. Clean repo - offer to switch
    click.echo(
        f"Warning: Not on project branch '{expected_branch}' (currently on '{current_branch}')"
    )
    if click.confirm("Switch to correct branch?", default=True):
        if verbose:
            click.echo(f"Switching to '{expected_branch}'...")
        checkout_branch(meta_path, expected_branch)
        click.echo(f"Switched to branch '{expected_branch}'")
    else:
        click.echo("Aborted.", err=True)
        raise click.Abort()
