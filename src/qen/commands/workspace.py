"""Implementation of qen workspace command.

Generate editor workspace files for multi-repo projects:
1. Load configuration and find current project
2. Read repositories from pyproject.toml
3. Generate workspace files for various editors (VS Code, Sublime Text, etc.)
4. Save to workspaces/ directory in project root
"""

import json
from pathlib import Path
from typing import Any

import click

from qenvy.base import QenvyBase

from ..config import QenConfigError
from ..init_utils import ensure_correct_branch, ensure_initialized
from ..pyproject_utils import PyProjectNotFoundError, read_pyproject


class WorkspaceError(Exception):
    """Base exception for workspace command errors."""

    pass


class NoActiveProjectError(WorkspaceError):
    """Raised when no active project is set."""

    pass


def generate_vscode_workspace(
    project_dir: Path, repos: list[dict[str, Any]], project_name: str
) -> dict[str, Any]:
    """Generate VS Code workspace configuration.

    Args:
        project_dir: Path to project directory
        repos: List of repository entries from pyproject.toml
        project_name: Name of the project

    Returns:
        VS Code workspace configuration dictionary
    """
    folders = []

    # Add project root first
    folders.append({"path": str(project_dir), "name": f"📁 {project_name} (project root)"})

    # Add each repository
    for repo_entry in repos:
        if not isinstance(repo_entry, dict):
            continue

        path = repo_entry.get("path", "")
        if not path:
            continue

        repo_path = project_dir / path
        if not repo_path.exists():
            continue

        # Extract repo name and branch for display
        repo_name = Path(path).name
        branch = repo_entry.get("branch", "main")

        # Add PR info if available
        pr_num = repo_entry.get("pr")
        folder_name = f"📦 {repo_name} ({branch})"
        if pr_num:
            folder_name += f" [PR #{pr_num}]"

        folders.append({"path": str(repo_path), "name": folder_name})

    workspace = {
        "folders": folders,
        "settings": {
            "files.exclude": {
                "**/.git": True,
                "**/__pycache__": True,
                "**/*.pyc": True,
                "**/.pytest_cache": True,
                "**/.mypy_cache": True,
                "**/.ruff_cache": True,
            }
        },
    }

    return workspace


def generate_sublime_workspace(
    project_dir: Path, repos: list[dict[str, Any]], project_name: str
) -> dict[str, Any]:
    """Generate Sublime Text workspace configuration.

    Args:
        project_dir: Path to project directory
        repos: List of repository entries from pyproject.toml
        project_name: Name of the project

    Returns:
        Sublime Text workspace configuration dictionary
    """
    folders = []

    # Add project root first
    folders.append({"path": str(project_dir), "name": f"{project_name} (root)"})

    # Add each repository
    for repo_entry in repos:
        if not isinstance(repo_entry, dict):
            continue

        path = repo_entry.get("path", "")
        if not path:
            continue

        repo_path = project_dir / path
        if not repo_path.exists():
            continue

        repo_name = Path(path).name
        branch = repo_entry.get("branch", "main")

        folder_name = f"{repo_name} ({branch})"
        folders.append({"path": str(repo_path), "name": folder_name})

    workspace = {
        "folders": folders,
        "settings": {
            "file_exclude_patterns": ["*.pyc", "*.pyo"],
            "folder_exclude_patterns": [
                ".git",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ],
        },
    }

    return workspace


def create_workspace_files(
    project_dir: Path,
    repos: list[dict[str, Any]],
    project_name: str,
    editor: str = "all",
    verbose: bool = False,
) -> dict[str, Path]:
    """Create workspace files for specified editors.

    Args:
        project_dir: Path to project directory
        repos: List of repository entries from pyproject.toml
        project_name: Name of the project
        editor: Editor type ('vscode', 'sublime', 'all')
        verbose: Enable verbose output

    Returns:
        Dictionary mapping editor name to created file path

    Raises:
        WorkspaceError: If workspace creation fails
    """
    workspaces_dir = project_dir / "workspaces"
    workspaces_dir.mkdir(exist_ok=True)

    created_files: dict[str, Path] = {}

    # Generate VS Code workspace
    if editor in ("vscode", "all"):
        vscode_config = generate_vscode_workspace(project_dir, repos, project_name)
        vscode_file = workspaces_dir / "vscode.code-workspace"

        try:
            with open(vscode_file, "w") as f:
                json.dump(vscode_config, f, indent=2)
            created_files["vscode"] = vscode_file

            if verbose:
                click.echo(f"Created VS Code workspace: {vscode_file}")
        except Exception as e:
            raise WorkspaceError(f"Failed to create VS Code workspace: {e}") from e

    # Generate Sublime Text workspace
    if editor in ("sublime", "all"):
        sublime_config = generate_sublime_workspace(project_dir, repos, project_name)
        sublime_file = workspaces_dir / "sublime.sublime-project"

        try:
            with open(sublime_file, "w") as f:
                json.dump(sublime_config, f, indent=2)
            created_files["sublime"] = sublime_file

            if verbose:
                click.echo(f"Created Sublime Text workspace: {sublime_file}")
        except Exception as e:
            raise WorkspaceError(f"Failed to create Sublime Text workspace: {e}") from e

    return created_files


def workspace_command(
    editor: str = "all",
    verbose: bool = False,
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
) -> None:
    """Generate editor workspace files for the current project.

    Args:
        editor: Editor type ('vscode', 'sublime', 'all')
        verbose: Enable verbose output
        config_dir: Override config directory (for testing)
        storage: Override storage backend (for testing)
        meta_path_override: Runtime override for meta_path
        current_project_override: Runtime override for current_project

    Raises:
        NoActiveProjectError: If no project is currently active
        QenConfigError: If configuration cannot be read
        PyProjectNotFoundError: If pyproject.toml not found
        WorkspaceError: If workspace creation fails
    """
    # Load configuration
    config = ensure_initialized(
        config_dir=config_dir,
        storage=storage,
        meta_path_override=meta_path_override,
        current_project_override=current_project_override,
        verbose=verbose,
    )

    # Ensure we are on the correct branch for the current project
    ensure_correct_branch(config, verbose=verbose)

    # Config is now guaranteed to exist
    main_config = config.read_main_config()

    # Get current project
    current_project = main_config.get("current_project")
    if not current_project:
        click.echo(
            "Error: No active project. Create a project with 'qen init <project-name>' first.",
            err=True,
        )
        raise click.Abort()

    if verbose:
        click.echo(f"Current project: {current_project}")

    # Get project directory
    try:
        project_config = config.read_project_config(current_project)
    except QenConfigError as e:
        click.echo(f"Error reading project configuration: {e}", err=True)
        raise click.Abort() from e

    # Check for per-project meta (new format)
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

    if not project_dir.exists():
        click.echo(f"Error: Project directory not found: {project_dir}", err=True)
        raise click.Abort()

    # Read repositories from pyproject.toml
    try:
        pyproject = read_pyproject(project_dir)
    except PyProjectNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    repos = pyproject.get("tool", {}).get("qen", {}).get("repos", [])

    if not repos:
        click.echo("Warning: No repositories found in project.", err=True)
        click.echo("Add repositories with: qen add <repo>")
        # Continue anyway - still create workspace with just project root

    # Create workspace files
    try:
        created_files = create_workspace_files(project_dir, repos, current_project, editor, verbose)
    except WorkspaceError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    # Display summary
    click.echo(f"\n✓ Created workspace files for project: {current_project}")
    click.echo(f"  Project directory: {project_dir}")
    click.echo(f"  Repositories: {len(repos)}")
    click.echo("\nGenerated workspaces:")

    for editor_name, file_path in created_files.items():
        rel_path = file_path.relative_to(project_dir)
        click.echo(f"  • {editor_name}: {rel_path}")

    click.echo("\nTo open:")
    if "vscode" in created_files:
        vscode_file = created_files["vscode"]
        click.echo(f"  code {vscode_file}")
        click.echo(f"  cursor {vscode_file}")
    if "sublime" in created_files:
        sublime_file = created_files["sublime"]
        click.echo(f"  subl --project {sublime_file}")
