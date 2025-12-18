"""Implementation of qen add command.

Add a repository to the current project by:
1. Parsing the repository URL
2. Cloning the repository
3. Updating pyproject.toml with the repository entry
"""

import shutil
from pathlib import Path
from typing import Any

import click

from ..config import QenConfigError
from ..context.runtime import RuntimeContext
from ..git_utils import GitError, get_current_branch, get_default_branch
from ..init_utils import ensure_correct_branch, ensure_initialized
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
    no_commit: bool = False,
    runtime_ctx: RuntimeContext | None = None,
    # Legacy parameters for backward compatibility with tests
    config_dir: Path | str | None = None,
    storage: Any | None = None,
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
        no_commit: Skip automatic git commit
        runtime_ctx: Runtime context with CLI overrides (preferred, for production use)
        config_dir: [DEPRECATED] Override config directory (for testing, use runtime_ctx instead)
        storage: [DEPRECATED] Override storage backend (for testing)
        meta_path_override: [DEPRECATED] Override meta repository path (use runtime_ctx instead)
        current_project_override: [DEPRECATED] Override current project (use runtime_ctx instead)

    Raises:
        NoActiveProjectError: If no project is currently active
        RepoUrlParseError: If repository URL cannot be parsed
        RepositoryAlreadyExistsError: If repository already exists
        GitError: If clone operation fails
        PyProjectUpdateError: If pyproject.toml update fails
        QenConfigError: If configuration cannot be read
    """
    # 1. Handle runtime context - support both new and legacy parameter styles
    if runtime_ctx is None:
        # Legacy mode: construct runtime context from individual parameters
        if config_dir is None:
            from platformdirs import user_config_path

            config_dir = user_config_path("qen")

        runtime_ctx = RuntimeContext(
            config_dir=Path(config_dir) if not isinstance(config_dir, Path) else config_dir,
            current_project_override=current_project_override,
            meta_path_override=Path(meta_path_override) if meta_path_override else None,
        )

    # 2. Ensure initialized and get config service
    config = ensure_initialized(
        config_dir=runtime_ctx.config_dir,
        storage=storage,  # Use storage if provided (for testing)
        meta_path_override=runtime_ctx.meta_path_override,
        current_project_override=runtime_ctx.current_project_override,
        verbose=verbose,
    )

    # Ensure we're on the correct branch
    ensure_correct_branch(config, verbose=verbose, yes=yes)

    # 3. Get current project
    main_config = config.read_main_config()
    current_project = main_config.get("current_project")
    if not current_project:
        click.echo(
            "Error: No active project. Create a project with 'qen init <project-name>' first.",
            err=True,
        )
        raise click.Abort()

    if verbose:
        click.echo(f"Current project: {current_project}")

    # 4. Get project directory
    try:
        project_config = config.read_project_config(current_project)
    except QenConfigError as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    # Check for per-project meta repo field
    if "repo" not in project_config:
        click.echo(
            f"Error: Project '{current_project}' uses old configuration format.\n"
            f"This version requires per-project meta clones.\n"
            f"To migrate: qen init --force {current_project}",
            err=True,
        )
        raise click.Abort()

    per_project_meta = Path(project_config["repo"])
    folder = project_config["folder"]
    project_dir = per_project_meta / folder

    if verbose:
        click.echo(f"Project directory: {project_dir}")

    # 5. Parse repository URL
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

    # 6. Apply defaults for branch and path
    if branch is None:
        # Default to the current branch of the per-project meta repo
        try:
            branch = get_current_branch(per_project_meta)
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

    # 7. Check if repository already exists in pyproject.toml
    try:
        repo_in_config = repo_exists_in_pyproject(project_dir, url, branch)
        if repo_in_config:
            if force:
                # With --force, remove and re-add without asking
                if verbose:
                    click.echo("Repository exists. Removing and re-adding with --force...")
                remove_existing_repo(project_dir, url, branch, verbose)
            elif yes:
                # With --yes, remove and re-add without asking
                if verbose:
                    click.echo("Repository exists. Removing and re-adding with --yes...")
                remove_existing_repo(project_dir, url, branch, verbose)
            else:
                # No flags - prompt user
                click.echo("\nRepository already exists in project:")
                click.echo(f"  URL: {url}")
                click.echo(f"  Branch: {branch}")
                click.echo("\nOptions:")
                click.echo("  [y] Remove and re-add (re-clone from scratch)")
                click.echo("  [n] Reuse (pull to update) - default")
                if click.confirm("\nRemove and re-add?", default=False):
                    if verbose:
                        click.echo("Removing existing repository...")
                    remove_existing_repo(project_dir, url, branch, verbose)
                else:
                    click.echo("Reusing existing entry, will update metadata")
                    # Don't abort - continue to update metadata
    except PyProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    # 8. Clone the repository (or prompt if it exists)
    clone_path = project_dir / path
    skip_clone = False

    if clone_path.exists():
        # Check if it's a valid git repository
        from ..git_utils import is_git_repo

        if not is_git_repo(clone_path):
            # Directory exists but is not a git repo - this is an error state
            click.echo(
                f"Error: Directory exists but is not a git repository: {clone_path}", err=True
            )
            click.echo("Options:", err=True)
            click.echo("  1. Remove the directory manually and try again", err=True)
            click.echo("  2. Use --force to automatically remove and re-clone", err=True)
            raise click.Abort()

        # Valid git repo exists on disk
        if force:
            # With --force, remove and re-clone without asking
            if verbose:
                click.echo(f"Removing existing clone directory at {clone_path}")
            shutil.rmtree(clone_path)
        elif yes:
            # With --yes, skip cloning and just update metadata
            if verbose:
                click.echo(f"Clone already exists at {clone_path}, skipping clone")
            click.echo(f"Repository already exists at {clone_path}")
            click.echo("Skipping clone, will update metadata only")
            skip_clone = True
        else:
            # Prompt user for action
            click.echo(f"\nRepository already exists at {clone_path}")
            click.echo("Options:")
            click.echo("  [y] Remove and re-clone from scratch")
            click.echo("  [n] Reuse existing clone and pull latest (default)")
            if click.confirm("\nRemove and re-clone?", default=False):
                if verbose:
                    click.echo(f"Removing existing clone directory at {clone_path}")
                shutil.rmtree(clone_path)
            else:
                click.echo("Reusing existing clone, will pull latest and update metadata")
                skip_clone = True

    if not skip_clone:
        if verbose:
            click.echo(f"Cloning to: {clone_path}")

        try:
            clone_repository(url, clone_path, branch, verbose, yes=yes)
        except GitError as e:
            click.echo(f"Error cloning repository: {e}", err=True)
            raise click.Abort() from e

    # 9. Detect default branch from the cloned repository
    try:
        default_branch = get_default_branch(clone_path)
        if verbose:
            click.echo(f"Detected default branch: {default_branch}")
    except GitError:
        # Fall back to 'main' if detection fails
        default_branch = "main"
        if verbose:
            click.echo("Could not detect default branch, using 'main'")

    # 10. Add initial metadata to pyproject.toml
    if verbose:
        click.echo("Adding initial metadata to pyproject.toml...")

    try:
        add_repo_to_pyproject(project_dir, url, branch, path, default_branch)
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

    # 11. Initialize metadata and detect PR/issue associations via pull
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
        # save_metadata=True by default, so metadata is automatically saved
        gh_available = check_gh_installed()
        result = pull_repository(
            repo_entry=repo_entry,
            project_dir=project_dir,
            fetch_only=False,
            gh_available=gh_available,
            verbose=verbose,
            save_metadata=True,  # Auto-save metadata to pyproject.toml
        )

        # Check pull result
        if not result["success"]:
            # Pull failed - this is a critical error
            error_msg = result.get("message", "Unknown error")
            click.echo(f"Error: Failed to pull repository: {error_msg}", err=True)
            click.echo(
                "The repository was added to pyproject.toml but could not be synchronized.",
                err=True,
            )
            raise click.Abort()

        # Check for metadata save errors (non-fatal)
        if result.get("metadata_save_error"):
            click.echo(
                f"Warning: Metadata collected but not saved: {result['metadata_save_error']}",
                err=True,
            )
        elif verbose:
            click.echo("Repository metadata initialized and saved successfully")
    except click.Abort:
        # Re-raise Abort to exit cleanly
        raise
    except Exception as e:
        # Other errors are non-fatal: repository is added but metadata might be incomplete
        click.echo(f"Warning: Could not initialize metadata: {e}", err=True)
        if verbose:
            click.echo("Repository was added successfully but metadata may be incomplete.")

    # 12. Regenerate workspace files (unless --no-workspace)
    if not no_workspace:
        if verbose:
            click.echo("\nRegenerating workspace files...")
        try:
            # Read all repos from pyproject.toml
            from ..pyproject_utils import read_pyproject
            from .workspace import create_workspace_files

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

    # 13. Auto-commit (unless --no-commit)
    if not no_commit:
        if verbose:
            click.echo("\nCommitting changes...")
        try:
            import subprocess

            # Stage pyproject.toml
            subprocess.run(
                ["git", "add", "pyproject.toml"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )

            # Stage workspace files if they were generated
            if not no_workspace:
                subprocess.run(
                    ["git", "add", "*.code-workspace", "*.sublime-project"],
                    cwd=project_dir,
                    check=False,  # Don't fail if no workspace files exist
                    capture_output=True,
                )

            # Commit
            commit_msg = f"Add {repo_name} (branch: {branch})"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )

            if verbose:
                click.echo(f"Committed: {commit_msg}")
        except subprocess.CalledProcessError as e:
            # Non-fatal: commit failed but repo was added
            click.echo(f"Warning: Could not auto-commit: {e}", err=True)
            if verbose:
                click.echo(
                    f"You can manually commit with: git add pyproject.toml && "
                    f"git commit -m 'Add {repo_name} (branch: {branch})'"
                )

    # 14. Success message
    click.echo()
    click.echo(f"✓ Added repository: {url}")
    click.echo(f"  Branch: {branch}")
    click.echo(f"  Path: {clone_path}")
    if not no_workspace:
        click.echo("  Workspace files: updated")
    if not no_commit:
        click.echo("  Changes: committed")
    else:
        click.echo()
        click.echo("Next steps:")
        click.echo("  - Review the cloned repository")
        click.echo(
            f"  - Commit changes: git add pyproject.toml && "
            f"git commit -m 'Add {repo_name} (branch: {branch})'"
        )
