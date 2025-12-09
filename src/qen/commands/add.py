"""Implementation of qen add command.

Add a repository to the current project by:
1. Parsing the repository URL
2. Cloning the repository
3. Updating pyproject.toml with the repository entry
"""

import shutil
from pathlib import Path

import click

from qenvy.base import QenvyBase

from ..config import QenConfig, QenConfigError
from ..git_utils import GitError, get_current_branch
from ..pyproject_utils import (
    PyProjectNotFoundError,
    PyProjectUpdateError,
    add_repo_to_pyproject,
    remove_repo_from_pyproject,
    repo_exists_in_pyproject,
)
from ..repo_utils import (
    RepoUrlParseError,
    clone_repository,
    infer_repo_path,
    parse_repo_url,
)


class AddCommandError(Exception):
    """Base exception for add command errors."""

    pass


class NoActiveProjectError(AddCommandError):
    """Raised when no active project is set."""

    pass


class RepositoryAlreadyExistsError(AddCommandError):
    """Raised when repository already exists in project."""

    pass


def remove_existing_repo(project_dir: Path, url: str, branch: str, verbose: bool = False) -> None:
    """Remove existing repository from both config and filesystem.

    Args:
        project_dir: Path to project directory
        url: Repository URL to remove
        branch: Branch to remove
        verbose: Enable verbose output

    Raises:
        PyProjectUpdateError: If removal from pyproject.toml fails
    """
    # Get the stored path from config and remove entry
    repo_path_str = remove_repo_from_pyproject(project_dir, url, branch)

    if repo_path_str:
        # Convert relative path to absolute
        repo_path = project_dir / repo_path_str

        # Remove clone directory if it exists
        if repo_path.exists():
            if verbose:
                click.echo(f"Removing existing clone at {repo_path}")
            shutil.rmtree(repo_path)
        elif verbose:
            click.echo(f"Clone directory not found: {repo_path} (already removed)")
    elif verbose:
        click.echo("Repository entry not found in pyproject.toml (already removed)")


def add_repository(
    repo: str,
    branch: str | None = None,
    path: str | None = None,
    verbose: bool = False,
    force: bool = False,
    yes: bool = False,
    no_workspace: bool = False,
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Add a repository to the current project.

    Args:
        repo: Repository identifier (full URL, org/repo, or repo name)
        branch: Branch to track (default: current meta repo branch)
        path: Local path for repository (default: repos/<name>)
        verbose: Enable verbose output
        force: Force re-add even if repository exists (removes and re-clones)
        yes: Auto-confirm prompts (create local branch without asking)
        no_workspace: Skip automatic workspace file regeneration
        config_dir: Override config directory (for testing)
        storage: Override storage backend (for testing with in-memory storage)
        meta_path_override: Override meta repository path
        current_project_override: Override current project name

    Raises:
        NoActiveProjectError: If no project is currently active
        RepoUrlParseError: If repository URL cannot be parsed
        RepositoryAlreadyExistsError: If repository already exists
        GitError: If clone operation fails
        PyProjectUpdateError: If pyproject.toml update fails
        QenConfigError: If configuration cannot be read
    """
    # 1. Load configuration and get current project
    config = QenConfig(
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
    )

    # Try to read main config
    # If it doesn't exist and we have overrides, that's OK - we'll create it
    # If it doesn't exist and we don't have overrides, we'll fail when trying to read it
    try:
        main_config = config.read_main_config()
    except QenConfigError as e:
        click.echo(f"Error reading configuration: {e}", err=True)
        click.echo("Hint: Run 'qen init' first to initialize qen.", err=True)
        raise click.Abort() from e

    current_project = main_config.get("current_project")
    if not current_project:
        click.echo(
            "Error: No active project. Create a project with 'qen init <project-name>' first.",
            err=True,
        )
        raise click.Abort()

    if verbose:
        click.echo(f"Current project: {current_project}")

    # 2. Get project folder and construct project directory path
    try:
        project_config = config.read_project_config(current_project)
    except QenConfigError as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    meta_path = Path(main_config["meta_path"])
    folder = project_config["folder"]
    project_dir = meta_path / folder

    if verbose:
        click.echo(f"Project directory: {project_dir}")

    # 3. Parse repository URL
    org = main_config.get("org")

    try:
        parsed = parse_repo_url(repo, org)
    except RepoUrlParseError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    url = parsed["url"]
    repo_name = parsed["repo"]

    if verbose:
        click.echo(f"Parsed URL: {url}")
        click.echo(f"Repository name: {repo_name}")
        click.echo(f"Organization: {parsed['org']}")

    # 4. Apply defaults for branch and path
    if branch is None:
        # Default to the current branch of the meta repo
        try:
            branch = get_current_branch(meta_path)
            if verbose:
                click.echo(f"Using meta branch: {branch}")
        except GitError as e:
            click.echo(f"Error getting current branch: {e}", err=True)
            raise click.Abort() from e

    if path is None:
        path = infer_repo_path(repo_name, branch, project_dir)

    if verbose:
        click.echo(f"Branch: {branch}")
        click.echo(f"Path: {path}")

    # 5. Check if repository already exists in pyproject.toml
    try:
        if repo_exists_in_pyproject(project_dir, url, branch):
            if not force:
                # Existing behavior - block and abort
                click.echo(
                    f"Error: Repository already exists in project: {url} (branch: {branch})",
                    err=True,
                )
                raise click.Abort()
            else:
                # New behavior - remove existing entry and re-add
                if verbose:
                    click.echo("Repository exists. Removing and re-adding with --force...")
                remove_existing_repo(project_dir, url, branch, verbose)
    except PyProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    # 6. Clone the repository
    clone_path = project_dir / path

    if verbose:
        click.echo(f"Cloning to: {clone_path}")

    # With --force, ensure clean slate by removing any existing directory
    # This handles cases where directory exists but isn't in config
    if force and clone_path.exists():
        if verbose:
            click.echo(f"Removing existing clone directory at {clone_path}")
        shutil.rmtree(clone_path)

    try:
        clone_repository(url, clone_path, branch, verbose, yes=yes)
    except GitError as e:
        click.echo(f"Error cloning repository: {e}", err=True)
        raise click.Abort() from e

    # 7. Add initial metadata to pyproject.toml
    if verbose:
        click.echo("Adding initial metadata to pyproject.toml...")

    try:
        add_repo_to_pyproject(project_dir, url, branch, path)
    except PyProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        # Clean up the cloned repository
        if clone_path.exists():
            shutil.rmtree(clone_path)
        raise click.Abort() from e
    except PyProjectUpdateError as e:
        click.echo(f"Error updating pyproject.toml: {e}", err=True)
        # Clean up the cloned repository
        if clone_path.exists():
            shutil.rmtree(clone_path)
        raise click.Abort() from e

    # 8. Initialize metadata and detect PR/issue associations via pull
    if verbose:
        click.echo("Initializing repository metadata...")

    try:
        # Import here to avoid circular dependency
        # Read the repo entry we just added from pyproject.toml
        from ..pyproject_utils import read_pyproject
        from .pull import check_gh_installed, pull_repository

        pyproject = read_pyproject(project_dir)
        repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

        # Find the repo entry we just added (repos is a list, not a dict)
        repo_entry = None
        for repo in repos:
            if isinstance(repo, dict):
                # Match by URL and branch since we just added it
                if repo.get("url") == url and repo.get("branch") == branch:
                    repo_entry = repo
                    break

        if not repo_entry:
            if verbose:
                click.echo("Warning: Could not find repo entry for metadata initialization")
            # Skip metadata initialization if we can't find the entry
            raise ValueError(f"Repository entry not found after add: {url}")

        # Call pull_repository to update metadata and detect PR/issue info
        gh_available = check_gh_installed()
        pull_repository(
            repo_entry=repo_entry,
            project_dir=project_dir,
            fetch_only=False,
            gh_available=gh_available,
            verbose=verbose,
        )
    except Exception as e:
        # Non-fatal: repository is added but metadata might be incomplete
        click.echo(f"Warning: Could not initialize metadata: {e}", err=True)
        if verbose:
            click.echo("Repository was added successfully but metadata may be incomplete.")

    # 9. Regenerate workspace files (unless --no-workspace)
    if not no_workspace:
        if verbose:
            click.echo("\nRegenerating workspace files...")
        try:
            from .workspace import create_workspace_files

            # Get current project name for workspace generation
            config = QenConfig(
                config_dir=config_dir,
                storage=storage,
                meta_path_override=meta_path_override,
                current_project_override=current_project_override,
            )
            main_config = config.read_main_config()
            current_project = main_config.get("current_project", "project")

            # Read all repos from pyproject.toml
            from ..pyproject_utils import read_pyproject

            pyproject = read_pyproject(project_dir)
            repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

            # Regenerate workspace files
            created_files = create_workspace_files(
                project_dir, repos, current_project, editor="all", verbose=verbose
            )

            if verbose:
                click.echo("Updated workspace files:")
                for editor_name, file_path in created_files.items():
                    rel_path = file_path.relative_to(project_dir)
                    click.echo(f"  • {editor_name}: {rel_path}")
        except Exception as e:
            # Non-fatal: workspace regeneration is a convenience feature
            click.echo(f"Warning: Could not regenerate workspace files: {e}", err=True)
            if verbose:
                click.echo("You can manually regenerate with: qen workspace")

    # 10. Success message
    click.echo()
    click.echo(f"✓ Added repository: {url}")
    click.echo(f"  Branch: {branch}")
    click.echo(f"  Path: {clone_path}")
    if not no_workspace:
        click.echo("  Workspace files: updated")
    click.echo()
    click.echo("Next steps:")
    click.echo("  - Review the cloned repository")
    click.echo(
        f"  - Commit changes: git add pyproject.toml && "
        f"git commit -m 'Add {repo_name} (branch: {branch})'"
    )
