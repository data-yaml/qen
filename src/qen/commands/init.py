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
    storage: QenvyBase | None = None,
    config_dir: Path | str | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Create a new project in the meta repository.

    Behavior:
    1. Check if project config already exists (error if yes)
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
        storage: Optional storage backend for testing
        config_dir: Override configuration directory
        meta_path_override: Override meta repository path
        current_project_override: Override current project name

    Raises:
        ProjectAlreadyExistsError: If project already exists
        QenConfigError: If config operations fail
        ProjectError: If project creation fails
    """
    # Load configuration
    config = QenConfig(
        storage=storage,
        config_dir=config_dir,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Check if main config exists
    if not config.main_config_exists():
        click.echo("Error: qen is not initialized. Run 'qen init' first.", err=True)
        raise click.Abort()

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
        project_config_path = config.get_project_config_path(project_name)
        click.echo(
            f"Error: Project '{project_name}' already exists at {project_config_path}.",
            err=True,
        )
        raise click.Abort()

    if verbose:
        click.echo(f"Creating project: {project_name}")
        click.echo(f"Meta repository: {meta_path}")

    # Create project with current timestamp
    now = datetime.now(UTC)

    try:
        branch_name, folder_path = create_project(
            meta_path,
            project_name,
            date=now,
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

    # Prompt to create PR unless --yes was specified
    if not yes:
        # Check if gh CLI is available
        import subprocess

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
