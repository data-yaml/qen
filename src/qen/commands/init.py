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


def init_qen(verbose: bool = False, storage: QenvyBase | None = None) -> None:
    """Initialize qen tooling.

    Behavior:
    1. Search for meta repo (current dir -> parent dirs)
    2. Extract org from git remote URL
    3. Create $XDG_CONFIG_HOME/qen/main/config.toml

    Args:
        verbose: Enable verbose output

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
    config = QenConfig(storage=storage)

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


def init_project(project_name: str, verbose: bool = False, storage: QenvyBase | None = None) -> None:
    """Create a new project in the meta repository.

    Behavior:
    1. Check if project config already exists (error if yes)
    2. Create branch YYYY-MM-DD-<proj-name> in meta repo
    3. Create directory proj/YYYY-MM-DD-<proj-name>/ with:
       - README.md (stub)
       - meta.toml (empty repos list)
       - repos/ (gitignored)
    4. Create project config
    5. Update main config: set current_project

    Args:
        project_name: Name of the project
        verbose: Enable verbose output
        storage: Optional storage backend for testing

    Raises:
        ProjectAlreadyExistsError: If project already exists
        QenConfigError: If config operations fail
        ProjectError: If project creation fails
    """
    # Load configuration
    config = QenConfig(storage=storage)

    # Check if main config exists
    if not config.main_config_exists():
        click.echo("Error: qen is not initialized. Run 'qen init' first.", err=True)
        raise click.Abort()

    # Read main config to get meta_path
    try:
        main_config = config.read_main_config()
        meta_path = Path(main_config["meta_path"])
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
        branch_name, folder_path = create_project(meta_path, project_name, date=now)
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
    click.echo("Next steps:")
    click.echo(f"  cd {meta_path / folder_path}")
    click.echo("  # Add repositories with: qen add <repo-url>")
