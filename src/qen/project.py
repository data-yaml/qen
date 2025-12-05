"""Project initialization and management for qen.

This module provides functionality for creating and managing qen projects
within a meta repository. It handles:
- Project directory structure creation
- Branch creation
- Stub file generation (README.md, meta.toml)
- .gitignore management
"""

from datetime import UTC, datetime
from pathlib import Path

from .git_utils import create_branch, run_git_command


class ProjectError(Exception):
    """Base exception for project-related errors."""

    pass


def generate_branch_name(project_name: str, date: datetime | None = None) -> str:
    """Generate a branch name with date prefix.

    Format: YYYY-MM-DD-<project-name>

    Args:
        project_name: Name of the project
        date: Date to use (default: current date)

    Returns:
        Branch name with date prefix
    """
    if date is None:
        date = datetime.now(UTC)

    date_prefix = date.strftime("%Y-%m-%d")
    return f"{date_prefix}-{project_name}"


def generate_folder_path(project_name: str, date: datetime | None = None) -> str:
    """Generate a folder path with date prefix.

    Format: proj/YYYY-MM-DD-<project-name>

    Args:
        project_name: Name of the project
        date: Date to use (default: current date)

    Returns:
        Folder path relative to meta repo root
    """
    if date is None:
        date = datetime.now(UTC)

    date_prefix = date.strftime("%Y-%m-%d")
    return f"proj/{date_prefix}-{project_name}"


def create_project_structure(
    meta_path: Path, project_name: str, branch_name: str, folder_path: str
) -> None:
    """Create project directory structure in meta repository.

    Creates:
    - proj/YYYY-MM-DD-<project-name>/
    - proj/YYYY-MM-DD-<project-name>/README.md (stub)
    - proj/YYYY-MM-DD-<project-name>/meta.toml (empty repos list)
    - proj/YYYY-MM-DD-<project-name>/repos/ (directory)

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        branch_name: Git branch name
        folder_path: Project folder path (relative to meta repo)

    Raises:
        ProjectError: If directory creation fails
    """
    # Create the project directory
    project_dir = meta_path / folder_path
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise ProjectError(f"Project directory already exists: {project_dir}") from None
    except Exception as e:
        raise ProjectError(f"Failed to create project directory: {e}") from e

    # Create README.md stub
    readme_path = project_dir / "README.md"
    readme_content = f"""# {project_name}

Project created on {datetime.now(UTC).strftime("%Y-%m-%d")}

## Overview

(Add project description here)

## Repositories

See `meta.toml` for the list of repositories in this project.

## Getting Started

```bash
# Clone all repositories
qen clone

# Pull latest changes
qen pull

# Check status
qen status
```
"""
    try:
        readme_path.write_text(readme_content)
    except Exception as e:
        raise ProjectError(f"Failed to create README.md: {e}") from e

    # Create meta.toml stub
    meta_toml_path = project_dir / "meta.toml"
    meta_toml_content = """# Repository configuration for this project
# Add repositories using: qen add <repo-url>

[[repos]]
# Example:
# url = "https://github.com/org/repo"
# branch = "main"
# path = "repos/repo"
"""
    try:
        meta_toml_path.write_text(meta_toml_content)
    except Exception as e:
        raise ProjectError(f"Failed to create meta.toml: {e}") from e

    # Create repos/ directory
    repos_dir = project_dir / "repos"
    try:
        repos_dir.mkdir(exist_ok=False)
    except Exception as e:
        raise ProjectError(f"Failed to create repos/ directory: {e}") from e


def add_gitignore_entry(meta_path: Path, folder_path: str) -> None:
    """Add repos/ directory to .gitignore in project folder.

    Args:
        meta_path: Path to meta repository
        folder_path: Project folder path (relative to meta repo)

    Raises:
        ProjectError: If .gitignore update fails
    """
    project_dir = meta_path / folder_path
    gitignore_path = project_dir / ".gitignore"

    # Entry to add (relative to project directory)
    entry = "repos/\n"

    try:
        # Read existing .gitignore if it exists
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            # Check if entry already exists
            if "repos/" in content:
                return  # Already exists
            # Append to existing content
            if not content.endswith("\n"):
                content += "\n"
            content += entry
        else:
            # Create new .gitignore
            content = entry

        gitignore_path.write_text(content)
    except Exception as e:
        raise ProjectError(f"Failed to update .gitignore: {e}") from e


def stage_project_files(meta_path: Path, folder_path: str) -> None:
    """Stage project files for commit.

    Args:
        meta_path: Path to meta repository
        folder_path: Project folder path (relative to meta repo)

    Raises:
        ProjectError: If staging fails
    """
    try:
        # Stage the entire project directory
        run_git_command(["add", folder_path], cwd=meta_path)
    except Exception as e:
        raise ProjectError(f"Failed to stage project files: {e}") from e


def create_project(
    meta_path: Path,
    project_name: str,
    date: datetime | None = None,
) -> tuple[str, str]:
    """Create a new project in the meta repository.

    This function:
    1. Creates a new branch with date prefix
    2. Creates project directory structure
    3. Creates stub files (README.md, meta.toml)
    4. Creates repos/ directory
    5. Adds .gitignore entry for repos/
    6. Stages files for commit (but does not commit)

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        date: Date to use for prefixes (default: current date)

    Returns:
        Tuple of (branch_name, folder_path)

    Raises:
        ProjectError: If project creation fails
    """
    if date is None:
        date = datetime.now(UTC)

    # Generate branch and folder names
    branch_name = generate_branch_name(project_name, date)
    folder_path = generate_folder_path(project_name, date)

    # Create branch
    try:
        create_branch(meta_path, branch_name, switch=True)
    except Exception as e:
        raise ProjectError(f"Failed to create branch: {e}") from e

    # Create project structure
    try:
        create_project_structure(meta_path, project_name, branch_name, folder_path)
    except Exception as e:
        # Try to cleanup: switch back to previous branch
        # (but don't fail if this cleanup fails)
        raise e

    # Add .gitignore entry
    try:
        add_gitignore_entry(meta_path, folder_path)
    except Exception as e:
        raise e

    # Stage files
    try:
        stage_project_files(meta_path, folder_path)
    except Exception as e:
        raise e

    return branch_name, folder_path
