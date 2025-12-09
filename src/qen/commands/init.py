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

    # Extract organization from remotes
    if verbose:
        click.echo("Extracting organization from git remotes...")

    try:
        org = extract_org_from_remotes(meta_path)
    except AmbiguousOrgError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e
    except GitError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    if verbose:
        click.echo(f"Organization: {org}")

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
    # Warn if project name is too long (breaks some services)
    if len(project_name) > 20:
        click.echo(
            f"Warning: Project name '{project_name}' is {len(project_name)} characters long.",
            err=True,
        )
        click.echo(
            "  Project names longer than 20 characters may break some services.",
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

    # Read main config to get meta_path
    try:
        main_config = config.read_main_config()
        meta_path = Path(main_config["meta_path"])
        github_org = main_config.get("org")  # Get org from config
    except QenConfigError as e:
        click.echo(f"Error reading configuration: {e}", err=True)
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

            # Get existing project config to find branch and folder
            try:
                old_config = config.read_project_config(project_name)
                old_branch = old_config.get("branch")
                old_folder = old_config.get("folder")

                # Delete old branch if it exists
                if old_branch:
                    import subprocess

                    try:
                        # Check if branch exists
                        branch_check = subprocess.run(
                            ["git", "rev-parse", "--verify", old_branch],
                            cwd=meta_path,
                            capture_output=True,
                            check=False,
                        )
                        if branch_check.returncode == 0:
                            # Get current branch
                            current_branch_result = subprocess.run(
                                ["git", "branch", "--show-current"],
                                cwd=meta_path,
                                capture_output=True,
                                text=True,
                                check=True,
                            )
                            current_branch = current_branch_result.stdout.strip()

                            # If we're on the branch to be deleted, switch away first
                            if current_branch == old_branch:
                                # Get all branches
                                branches_result = subprocess.run(
                                    ["git", "branch"],
                                    cwd=meta_path,
                                    capture_output=True,
                                    text=True,
                                    check=True,
                                )
                                branches = [
                                    b.strip().lstrip("* ").strip()
                                    for b in branches_result.stdout.split("\n")
                                    if b.strip()
                                ]

                                # Find a branch to switch to (prefer main/master, or any other branch)
                                target_branch = None
                                for preferred in ["main", "master"]:
                                    if preferred in branches and preferred != old_branch:
                                        target_branch = preferred
                                        break

                                if not target_branch:
                                    # Use any branch that's not the one we're deleting
                                    for branch in branches:
                                        if branch != old_branch:
                                            target_branch = branch
                                            break

                                if target_branch:
                                    # Checkout the target branch
                                    subprocess.run(
                                        ["git", "checkout", target_branch],
                                        cwd=meta_path,
                                        capture_output=True,
                                        check=True,
                                    )
                                else:
                                    # No other branch exists, create a temporary one
                                    subprocess.run(
                                        ["git", "checkout", "-b", "tmp-qen-delete"],
                                        cwd=meta_path,
                                        capture_output=True,
                                        check=True,
                                    )

                            # Now delete the branch
                            delete_result = subprocess.run(
                                ["git", "branch", "-D", old_branch],
                                cwd=meta_path,
                                capture_output=True,
                                text=True,
                                check=False,
                            )
                            if delete_result.returncode == 0:
                                if verbose:
                                    click.echo(f"  Deleted branch: {old_branch}")
                            else:
                                if verbose:
                                    click.echo(
                                        f"  Warning: Could not delete branch {old_branch}: {delete_result.stderr}"
                                    )
                    except subprocess.CalledProcessError as e:
                        # Ignore errors deleting branch but log them in verbose mode
                        if verbose:
                            click.echo(f"  Warning: Could not delete branch {old_branch}: {e}")

                # Delete old folder if it exists
                if old_folder:
                    import shutil

                    old_folder_path = meta_path / old_folder
                    if old_folder_path.exists():
                        shutil.rmtree(old_folder_path)
                        if verbose:
                            click.echo(f"  Deleted folder: {old_folder_path}")

            except QenConfigError:
                # If can't read old config, just continue
                pass

            # Delete the config file
            config.delete_project_config(project_name)
            if verbose:
                click.echo(f"  Deleted config for project '{project_name}'")

    if verbose:
        click.echo(f"Creating project: {project_name}")
        click.echo(f"Meta repository: {meta_path}")

    # Create project
    # Use UTC for ISO8601 timestamps (machine-facing)
    # But branch names will use local time (user-facing)
    now = datetime.now(UTC)

    try:
        branch_name, folder_path = create_project(
            meta_path,
            project_name,
            date=None,  # Let create_project use local time for branch names
            github_org=github_org,  # Pass org to create_project
        )
    except ProjectError as e:
        click.echo(f"Error creating project: {e}", err=True)
        raise click.Abort() from e

    if verbose:
        click.echo(f"Created branch: {branch_name}")
        click.echo(f"Created directory: {folder_path}")

    # Create project configuration
    try:
        config.write_project_config(
            project_name=project_name,
            branch=branch_name,
            folder=folder_path,
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
    click.echo(f"  Directory: {meta_path / folder_path}")
    click.echo(f"  Config: {config.get_project_config_path(project_name)}")
    click.echo()

    # Push the branch to remote first (required for PR creation)
    import subprocess

    try:
        if verbose:
            click.echo(f"Pushing branch {branch_name} to remote...")

        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            cwd=meta_path,
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
                    # Get the base branch (typically main or master)
                    result = subprocess.run(
                        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
                        cwd=meta_path,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if result.returncode == 0:
                        # Extract base branch from refs/remotes/origin/HEAD
                        base_branch = result.stdout.strip().split("/")[-1]
                    else:
                        # Fallback to main
                        base_branch = "main"

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
                        cwd=meta_path,
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
    click.echo(f"  cd {meta_path / folder_path}")
    click.echo("  # Add repositories with: qen add <repo-url>")
