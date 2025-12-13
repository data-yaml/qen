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
from platformdirs import user_config_dir

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

    # Check if config exists
    if not config.main_config_exists():
        # Config doesn't exist - attempt auto-initialization
        if verbose:
            click.echo("Configuration not found. Auto-initializing...")

        try:
            # Import here to avoid circular dependency
            from .commands.init import init_qen
            from .context.runtime import RuntimeContext

            # Create RuntimeContext for initialization
            runtime_ctx = RuntimeContext(
                config_dir=Path(config_dir) if config_dir else Path(user_config_dir("qen")),
                current_project_override=current_project_override,
                meta_path_override=Path(meta_path_override) if meta_path_override else None,
            )

            # Call existing init logic
            init_qen(
                ctx=runtime_ctx,
                verbose=False,  # Suppress init_qen's own output
            )

            if verbose:
                click.echo("✓ Auto-initialized qen configuration")

            return config

        except (NotAGitRepoError, MetaRepoNotFoundError) as e:
            # Cannot auto-init - not in a git repo or can't find meta repo
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
            click.echo("Error: Cannot auto-initialize qen.", err=True)
            click.echo(f"Reason: {e}", err=True)
            click.echo(err=True)
            click.echo("Please run 'qen init' manually to configure.", err=True)
            raise click.Abort() from e

        except GitError as e:
            # Cannot auto-init - general git error
            click.echo("Error: Cannot auto-initialize qen.", err=True)
            click.echo(f"Reason: {e}", err=True)
            click.echo(err=True)
            click.echo("Please run 'qen init' manually to configure.", err=True)
            raise click.Abort() from e

    # Config exists - check for missing fields and auto-upgrade if needed
    main_config = config.read_main_config()

    # Check if we need to upgrade
    needs_upgrade = (
        "meta_remote" not in main_config
        or "meta_parent" not in main_config
        or "meta_default_branch" not in main_config
    )

    if not needs_upgrade:
        return config  # Config is up to date

    # Need to upgrade - extract missing fields
    if verbose:
        click.echo("Upgrading configuration to new format...")

    try:
        import os

        from .commands.init import extract_remote_and_org
        from .git_utils import get_default_branch_from_remote

        # Get meta_path
        meta_path = Path(main_config["meta_path"])

        # Resolve symlinks and validate
        if meta_path.is_symlink():
            meta_path = meta_path.resolve()

        if not meta_path.exists():
            click.echo(
                f"Error: Meta path no longer exists: {meta_path}\nPlease reinitialize: qen init",
                err=True,
            )
            raise click.Abort()

        # Extract remote URL and org
        remote_url, org = extract_remote_and_org(meta_path)

        # Get parent directory
        meta_parent = meta_path.parent
        if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
            click.echo(
                f"Error: Parent directory not writable: {meta_parent}\n"
                f"Cannot auto-upgrade configuration.",
                err=True,
            )
            raise click.Abort()

        # Detect default branch
        default_branch = get_default_branch_from_remote(remote_url)

        # Update config with new fields
        config.write_main_config(
            meta_path=str(meta_path),
            meta_remote=remote_url,
            meta_parent=str(meta_parent),
            meta_default_branch=default_branch,
            org=org,
            current_project=main_config.get("current_project"),
        )

        if verbose:
            click.echo("✓ Configuration upgraded successfully")

        return config

    except (GitError, KeyError) as e:
        click.echo(
            f"Error: Cannot auto-upgrade configuration: {e}\nPlease reinitialize: qen init",
            err=True,
        )
        raise click.Abort() from e


def ensure_correct_branch(
    config: QenConfig,
    verbose: bool = False,
    yes: bool = False,
) -> None:
    """Ensure meta repository is on the correct project branch.

    Similar to ensure_initialized(), this function validates that the user is on
    the expected project branch before executing commands.

    If on wrong branch:
    - Clean meta repo: Prompts to switch with [Y/n] (or auto-confirms with --yes)
    - Dirty meta repo: Errors and tells user to commit/stash first

    Args:
        config: Loaded QenConfig instance
        verbose: Enable verbose output
        yes: Auto-confirm branch switch without prompting

    Raises:
        click.Abort: If on wrong branch and user declines to switch, or has uncommitted changes

    Example:
        >>> config = ensure_initialized(...)
        >>> ensure_correct_branch(config, verbose=verbose, yes=yes)
        >>> # Now guaranteed to be on correct branch (or user accepted switch)
    """
    # Import here to avoid circular dependency
    from .git_utils import checkout_branch, get_current_branch, has_uncommitted_changes

    # 1. Get expected branch from config
    main_config = config.read_main_config()
    current_project = main_config.get("current_project")

    if not current_project:
        # No active project - nothing to check
        return

    # Read the stored branch name from project config (don't regenerate it)
    project_config = config.read_project_config(current_project)
    expected_branch = project_config["branch"]

    # 2. Check current branch in per-project meta (not meta prime)
    # Use 'repo' field if available (per-project meta), otherwise fall back to meta_path
    if "repo" in project_config:
        # New per-project meta architecture
        meta_path = Path(project_config["repo"])
    else:
        # Old architecture or tests - use meta_path from main config
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

    # 4. Clean repo - offer to switch (or auto-confirm with --yes)
    if not yes:
        click.echo(
            f"Warning: Not on project branch '{expected_branch}' (currently on '{current_branch}')"
        )

    if yes or click.confirm("Switch to correct branch?", default=True):
        if verbose:
            click.echo(f"Switching to '{expected_branch}'...")
        checkout_branch(meta_path, expected_branch)
        if verbose:
            click.echo(f"Switched to branch '{expected_branch}'")
    else:
        click.echo("Aborted.", err=True)
        raise click.Abort()
