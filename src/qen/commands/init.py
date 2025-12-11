"""Implementation of qen init command.

Two modes:
1. qen init - Initialize qen tooling
2. qen init <proj-name> - Create new project
"""

from datetime import UTC, datetime
from pathlib import Path

import click

from qenvy.base import QenvyBase

from ..config import ProjectAlreadyExistsError, QenConfig, QenConfigError
from ..git_utils import (
    AmbiguousOrgError,
    GitError,
    MetaRepoNotFoundError,
    NotAGitRepoError,
    extract_org_from_remotes,
    find_meta_repo,
)
from ..project import ProjectError, create_project


def extract_remote_and_org(meta_path: Path) -> tuple[str, str]:
    """Extract remote URL and organization from meta repository.

    Args:
        meta_path: Path to meta repository

    Returns:
        Tuple of (remote_url, org)

    Raises:
        GitError: If remote cannot be extracted
        AmbiguousOrgError: If multiple organizations detected
    """
    from ..git_utils import get_remote_url

    # Get remote URL
    remote_url = get_remote_url(meta_path)

    # Extract org
    org = extract_org_from_remotes(meta_path)

    return remote_url, org


def init_qen(
    verbose: bool = False,
    storage: QenvyBase | None = None,
    config_dir: Path | str | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Initialize qen tooling.

    Behavior:
    1. Search for meta repo (current dir -> parent dirs)
    2. Extract org from git remote URL
    3. Create $XDG_CONFIG_HOME/qen/main/config.toml

    Args:
        verbose: Enable verbose output
        storage: Optional storage backend for testing
        config_dir: Override configuration directory
        meta_path_override: Override meta repository path
        current_project_override: Override current project name

    Raises:
        MetaRepoNotFoundError: If meta repository cannot be found
        NotAGitRepoError: If not in a git repository
        AmbiguousOrgError: If multiple organizations detected
        GitError: If git operations fail
        QenConfigError: If config operations fail
    """
    # Find meta repository
    # Use override if provided (for testing or explicit specification)
    if meta_path_override:
        meta_path = Path(meta_path_override)
        if verbose:
            click.echo(f"Using meta repository from override: {meta_path}")
    else:
        if verbose:
            click.echo("Searching for meta repository...")

        try:
            meta_path = find_meta_repo()
        except NotAGitRepoError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort() from e
        except MetaRepoNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise click.Abort() from e

        if verbose:
            click.echo(f"Found meta repository: {meta_path}")

    # Resolve symlinks and validate meta_path
    if meta_path.is_symlink():
        meta_path = meta_path.resolve()

    if not meta_path.exists():
        click.echo(f"Error: Meta path does not exist: {meta_path}", err=True)
        raise click.Abort()

    # Extract remote URL and organization
    if verbose:
        click.echo("Extracting metadata from git remotes...")

    try:
        remote_url, org = extract_remote_and_org(meta_path)
    except AmbiguousOrgError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e
    except GitError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    if verbose:
        click.echo(f"Remote URL: {remote_url}")
        click.echo(f"Organization: {org}")

    # Get parent directory for per-project meta clones
    import os

    meta_parent = meta_path.parent

    if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
        click.echo(f"Error: Parent directory not writable: {meta_parent}", err=True)
        raise click.Abort()

    if verbose:
        click.echo(f"Meta parent directory: {meta_parent}")

    # Detect default branch from remote
    from ..git_utils import get_default_branch_from_remote

    if verbose:
        click.echo("Detecting default branch from remote...")

    default_branch = get_default_branch_from_remote(remote_url)

    if verbose:
        click.echo(f"Default branch: {default_branch}")

    # Create configuration
    config = QenConfig(
        storage=storage,
        config_dir=config_dir,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    try:
        config.write_main_config(
            meta_path=str(meta_path),
            meta_remote=remote_url,
            meta_parent=str(meta_parent),
            meta_default_branch=default_branch,
            org=org,
            current_project=None,
        )
    except QenConfigError as e:
        click.echo(f"Error creating configuration: {e}", err=True)
        raise click.Abort() from e

    # Success message
    config_path = config.get_main_config_path()
    click.echo(f"Initialized qen configuration at: {config_path}")
    click.echo(f"  meta_path: {meta_path}")
    click.echo(f"  meta_remote: {remote_url}")
    click.echo(f"  meta_parent: {meta_parent}")
    click.echo(f"  meta_default_branch: {default_branch}")
    click.echo(f"  org: {org}")
    click.echo()
    click.echo("You can now create projects with: qen init <project-name>")


def init_project(
    project_name: str,
    verbose: bool = False,
    yes: bool = False,
    force: bool = False,
    storage: QenvyBase | None = None,
    config_dir: Path | str | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Create a new project in the meta repository.

    Behavior:
    1. Check if project config already exists (error if yes, unless --force)
    2. Create branch YYMMDD-<proj-name> in meta repo
    3. Create directory proj/YYMMDD-<proj-name>/ with:
       - README.md (stub)
       - meta.toml (empty repos list)
       - repos/ (gitignored)
    4. Create project config
    5. Update main config: set current_project
    6. Prompt to create PR (unless --yes is specified)

    Args:
        project_name: Name of the project
        verbose: Enable verbose output
        yes: Auto-confirm prompts (skip PR creation prompt)
        force: Force recreate if project already exists
        storage: Optional storage backend for testing
        config_dir: Override configuration directory
        meta_path_override: Override meta repository path
        current_project_override: Override current project name

    Raises:
        ProjectAlreadyExistsError: If project already exists and force is False
        QenConfigError: If config operations fail
        ProjectError: If project creation fails
    """
    MAX_PROJECT_NAME_LENGTH = 12
    # Warn if project name is too long (breaks some services)
    if len(project_name) > MAX_PROJECT_NAME_LENGTH:
        click.echo(
            f"Warning: Project name '{project_name}' is {len(project_name)} characters long.",
            err=True,
        )
        click.echo(
            f"  Project names longer than {MAX_PROJECT_NAME_LENGTH} characters may break some services.",
            err=True,
        )
        click.echo(
            "  Consider using a shorter name.",
            err=True,
        )
        click.echo()

    # Load configuration
    config = QenConfig(
        storage=storage,
        config_dir=config_dir,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Auto-initialize if main config doesn't exist
    # This allows commands like `qen --meta <path> init <project>` to work
    # without requiring a separate `qen init` call first
    if not config.main_config_exists():
        if verbose:
            click.echo("Auto-initializing qen configuration...")
        # Silently initialize (verbose=False to avoid cluttering output)
        init_qen(
            verbose=False,
            storage=storage,
            config_dir=config_dir,
            meta_path_override=meta_path_override,
            current_project_override=current_project_override,
        )

    # Read main config to get meta repository metadata
    try:
        main_config = config.read_main_config()
        meta_remote = main_config["meta_remote"]
        meta_parent = Path(main_config["meta_parent"])
        meta_default_branch = main_config["meta_default_branch"]
        github_org = main_config.get("org")  # Get org from config
    except QenConfigError as e:
        click.echo(f"Error reading configuration: {e}", err=True)
        raise click.Abort() from e
    except KeyError as e:
        click.echo(
            f"Error: Configuration is missing required field: {e}\n"
            f"Please reinitialize with: qen init",
            err=True,
        )
        raise click.Abort() from e

    # Check if project already exists
    if config.project_config_exists(project_name):
        if not force:
            project_config_path = config.get_project_config_path(project_name)
            click.echo(
                f"Error: Project '{project_name}' already exists at {project_config_path}.",
                err=True,
            )
            raise click.Abort()
        else:
            # Force mode: clean up existing project artifacts
            if verbose:
                click.echo(f"Force mode: Cleaning up existing project '{project_name}'")

            # Get existing project config to find per-project meta path
            try:
                import shutil
                import subprocess

                old_config = config.read_project_config(project_name)
                per_project_meta = Path(old_config["repo"])
                old_branch = old_config.get("branch")

                if not per_project_meta.exists():
                    # Directory already gone, just delete config
                    if verbose:
                        click.echo(f"  Per-project meta already deleted: {per_project_meta}")
                    config.delete_project_config(project_name)
                else:
                    # Check for uncommitted changes
                    result = subprocess.run(
                        ["git", "status", "--porcelain"],
                        cwd=per_project_meta,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    uncommitted_files = [line for line in result.stdout.split("\n") if line.strip()]

                    # Check for unpushed commits
                    unpushed_commits: list[str] = []
                    if old_branch:
                        result = subprocess.run(
                            ["git", "log", f"origin/{old_branch}..{old_branch}", "--oneline"],
                            cwd=per_project_meta,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        unpushed_commits = [
                            line for line in result.stdout.split("\n") if line.strip()
                        ]

                    # Display warnings
                    warnings = []
                    if uncommitted_files:
                        warnings.append(f"  • {len(uncommitted_files)} uncommitted file(s)")
                    if unpushed_commits:
                        warnings.append(f"  • {len(unpushed_commits)} unpushed commit(s)")

                    if warnings:
                        click.echo("⚠️  Warning: The following will be lost:", err=True)
                        for warning in warnings:
                            click.echo(warning, err=True)
                        click.echo()

                    # Confirm deletion (unless --yes flag)
                    if not yes:
                        click.echo(f"This will permanently delete: {per_project_meta}")
                        if not click.confirm("Continue?", default=False):
                            click.echo("Aborted.")
                            raise click.Abort()

                    # Delete directory
                    shutil.rmtree(per_project_meta)
                    if verbose:
                        click.echo(f"  Deleted per-project meta: {per_project_meta}")

                    # Delete the config file
                    config.delete_project_config(project_name)
                    if verbose:
                        click.echo(f"  Deleted config for project '{project_name}'")

                    # Note: Leave remote branch alone (user can delete manually)
                    if old_branch and verbose:
                        click.echo(
                            f"  Note: Remote branch '{old_branch}' was not deleted (delete manually if needed)"
                        )

            except QenConfigError:
                # If can't read old config, just continue
                pass

    if verbose:
        click.echo(f"Creating project: {project_name}")
        click.echo(f"Cloning from remote: {meta_remote}")

    # Clone from remote to create per-project meta
    from ..git_utils import clone_per_project_meta

    try:
        per_project_meta = clone_per_project_meta(
            meta_remote,
            project_name,
            meta_parent,
            meta_default_branch,
        )
        if verbose:
            click.echo(f"Created per-project meta: {per_project_meta}")
    except GitError as e:
        click.echo(f"Error cloning per-project meta: {e}", err=True)
        raise click.Abort() from e

    # Create project in the clone
    # Use UTC for ISO8601 timestamps (machine-facing)
    # But branch names will use local time (user-facing)
    now = datetime.now(UTC)

    try:
        branch_name, folder_path = create_project(
            per_project_meta,  # Use per-project meta, not meta prime
            project_name,
            date=None,  # Let create_project use local time for branch names
            github_org=github_org,  # Pass org to create_project
        )
    except ProjectError as e:
        click.echo(f"Error creating project: {e}", err=True)
        # Cleanup: delete the per-project meta clone
        import shutil

        if per_project_meta.exists():
            shutil.rmtree(per_project_meta)
        raise click.Abort() from e

    if verbose:
        click.echo(f"Created branch: {branch_name}")
        click.echo(f"Created directory: {folder_path}")

    # Push branch to remote
    import subprocess

    try:
        if verbose:
            click.echo(f"Pushing branch {branch_name} to remote...")

        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )

        if verbose:
            click.echo("Branch pushed successfully")
    except subprocess.CalledProcessError as e:
        click.echo(f"\nWarning: Failed to push branch: {e.stderr}", err=True)
        if verbose:
            click.echo(f"Error details: {e}", err=True)
        # Continue anyway - user can push manually later
    except Exception as e:
        click.echo(f"\nWarning: Failed to push branch: {e}", err=True)
        # Continue anyway

    # Create project configuration with per-project meta path
    try:
        config.write_project_config(
            project_name=project_name,
            branch=branch_name,
            folder=folder_path,
            repo=str(per_project_meta),  # Store per-project meta path
            created=now.isoformat(),
        )
    except ProjectAlreadyExistsError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e
    except QenConfigError as e:
        click.echo(f"Error creating project configuration: {e}", err=True)
        raise click.Abort() from e

    if verbose:
        project_config_path = config.get_project_config_path(project_name)
        click.echo(f"Created project config: {project_config_path}")

    # Update main config to set current_project
    try:
        config.update_current_project(project_name)
    except QenConfigError as e:
        click.echo(f"Warning: Failed to update current_project: {e}", err=True)
        # Don't abort - project was created successfully

    # Success message
    click.echo(f"\nProject '{project_name}' created successfully!")
    click.echo(f"  Branch: {branch_name}")
    click.echo(f"  Directory: {per_project_meta / folder_path}")
    click.echo(f"  Config: {config.get_project_config_path(project_name)}")
    click.echo()

    # Prompt to create PR unless --yes was specified
    if not yes:
        # Check if gh CLI is available
        try:
            subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            gh_available = True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            gh_available = False

        if gh_available:
            create_pr = click.confirm("Would you like to create a pull request for this project?")
            if create_pr:
                try:
                    # Use the default branch from config
                    base_branch = meta_default_branch

                    if verbose:
                        click.echo(f"Creating PR with base branch: {base_branch}")

                    # Create PR with gh CLI
                    pr_title = f"Project: {project_name}"
                    pr_body = (
                        f"Initialize project {project_name}\n\n"
                        f"This PR creates the project structure for {project_name}."
                    )

                    result = subprocess.run(
                        [
                            "gh",
                            "pr",
                            "create",
                            "--base",
                            base_branch,
                            "--head",
                            branch_name,
                            "--title",
                            pr_title,
                            "--body",
                            pr_body,
                        ],
                        cwd=per_project_meta,
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    pr_url = result.stdout.strip()
                    click.echo(f"\n✓ Pull request created: {pr_url}")
                except subprocess.CalledProcessError as e:
                    click.echo(f"\nWarning: Failed to create PR: {e.stderr}", err=True)
                    if verbose:
                        click.echo(f"Error details: {e}", err=True)
                except Exception as e:
                    click.echo(f"\nWarning: Failed to create PR: {e}", err=True)
        else:
            if verbose:
                click.echo("gh CLI not available, skipping PR creation prompt")

    click.echo()
    click.echo("Next steps:")
    click.echo(f"  cd {per_project_meta / folder_path}")
    click.echo("  # Add repositories with: qen add <repo-url>")
