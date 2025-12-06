"""Utilities for reading and updating pyproject.toml files.

This module provides functions for managing the [tool.qen.repos] section
in pyproject.toml files, which tracks sub-repositories in a qen project.
"""

from pathlib import Path
from typing import Any

from qenvy.formats import TOMLHandler


class PyProjectNotFoundError(Exception):
    """Raised when pyproject.toml cannot be found."""

    pass


class PyProjectUpdateError(Exception):
    """Raised when updating pyproject.toml fails."""

    pass


def read_pyproject(project_dir: Path) -> dict[str, Any]:
    """Read pyproject.toml from a project directory.

    Args:
        project_dir: Path to project directory containing pyproject.toml

    Returns:
        Parsed pyproject.toml content

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If parsing fails
    """
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise PyProjectNotFoundError(f"pyproject.toml not found in {project_dir}")

    handler = TOMLHandler()
    try:
        return handler.read(pyproject_path)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to read pyproject.toml: {e}") from e


def repo_exists_in_pyproject(project_dir: Path, url: str, branch: str) -> bool:
    """Check if a repository with given URL and branch already exists.

    Args:
        project_dir: Path to project directory
        url: Repository URL to check
        branch: Branch name to check

    Returns:
        True if (url, branch) combination exists in [[tool.qen.repos]]

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If parsing fails
    """
    try:
        config = read_pyproject(project_dir)
    except PyProjectNotFoundError:
        return False

    # Navigate to [tool.qen.repos]
    if "tool" not in config:
        return False
    if "qen" not in config["tool"]:
        return False
    if "repos" not in config["tool"]["qen"]:
        return False

    repos = config["tool"]["qen"]["repos"]
    if not isinstance(repos, list):
        return False

    # Check if (url, branch) tuple exists
    for repo in repos:
        if isinstance(repo, dict):
            if repo.get("url") == url and repo.get("branch") == branch:
                return True

    return False


def add_repo_to_pyproject(project_dir: Path, url: str, branch: str, path: str) -> None:
    """Add a repository entry to pyproject.toml.

    Updates the [[tool.qen.repos]] section with a new repository.
    Creates the section if it doesn't exist.

    Args:
        project_dir: Path to project directory
        url: Repository URL
        branch: Branch to track
        path: Local path for the repository (relative to project dir)

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If update fails
    """
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise PyProjectNotFoundError(f"pyproject.toml not found in {project_dir}")

    handler = TOMLHandler()

    try:
        config = handler.read(pyproject_path)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to read pyproject.toml: {e}") from e

    # Ensure [tool] section exists
    if "tool" not in config:
        config["tool"] = {}

    # Ensure [tool.qen] section exists
    if "qen" not in config["tool"]:
        config["tool"]["qen"] = {}

    # Ensure [[tool.qen.repos]] array exists
    if "repos" not in config["tool"]["qen"]:
        config["tool"]["qen"]["repos"] = []

    # Add new repository entry
    repo_entry = {
        "url": url,
        "branch": branch,
        "path": path,
    }
    config["tool"]["qen"]["repos"].append(repo_entry)

    # Write back to file
    try:
        handler.write(pyproject_path, config)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to write pyproject.toml: {e}") from e
