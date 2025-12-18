"""Utilities for reading and updating pyproject.toml files.

This module provides functions for managing the [tool.qen.repos] section
in pyproject.toml files, which tracks sub-repositories in a qen project.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qenvy.formats import TOMLHandler


class PyProjectNotFoundError(Exception):
    """Raised when pyproject.toml cannot be found."""

    pass


class PyProjectUpdateError(Exception):
    """Raised when updating pyproject.toml fails."""

    pass


@dataclass
class RepoConfig:
    """Configuration for a repository in pyproject.toml."""

    url: str
    branch: str
    path: str
    default_branch: str = "main"  # Default branch of the remote repository

    def local_path(self, project_dir: Path) -> Path:
        """Get absolute path to repository.

        Args:
            project_dir: Path to project directory

        Returns:
            Absolute path to repository
        """
        return project_dir / self.path


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


def load_repos_from_pyproject(project_dir: Path) -> list[RepoConfig]:
    """Load repository configurations from pyproject.toml.

    Args:
        project_dir: Path to project directory

    Returns:
        List of RepoConfig objects

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If parsing fails
    """
    try:
        config = read_pyproject(project_dir)
    except PyProjectNotFoundError:
        raise
    except PyProjectUpdateError:
        raise

    # Navigate to [tool.qen.repos]
    if "tool" not in config:
        return []
    if "qen" not in config["tool"]:
        return []
    if "repos" not in config["tool"]["qen"]:
        return []

    repos_data = config["tool"]["qen"]["repos"]
    if not isinstance(repos_data, list):
        return []

    # Convert to RepoConfig objects
    repos: list[RepoConfig] = []
    for repo in repos_data:
        if not isinstance(repo, dict):
            continue

        url = repo.get("url")
        branch = repo.get("branch", "main")
        path = repo.get("path")
        default_branch = repo.get("default_branch", "main")

        if not url or not path:
            # Skip invalid entries
            continue

        repos.append(RepoConfig(url=url, branch=branch, path=path, default_branch=default_branch))

    return repos


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


def add_repo_to_pyproject(
    project_dir: Path, url: str, branch: str, path: str, default_branch: str = "main"
) -> None:
    """Add a repository entry to pyproject.toml.

    Updates the [[tool.qen.repos]] section with a new repository.
    Creates the section if it doesn't exist.

    Args:
        project_dir: Path to project directory
        url: Repository URL
        branch: Branch to track
        path: Local path for the repository (relative to project dir)
        default_branch: Default branch of the remote repository

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
        "default_branch": default_branch,
    }
    config["tool"]["qen"]["repos"].append(repo_entry)

    # Write back to file
    try:
        handler.write(pyproject_path, config)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to write pyproject.toml: {e}") from e


def remove_repo_from_pyproject(project_dir: Path, url: str, branch: str) -> str | None:
    """Remove a repository entry from pyproject.toml.

    Args:
        project_dir: Path to project directory
        url: Repository URL to remove
        branch: Branch name to remove

    Returns:
        The path of the removed repository (for cleanup), or None if not found

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

    # Navigate to [tool.qen.repos]
    if "tool" not in config or "qen" not in config["tool"] or "repos" not in config["tool"]["qen"]:
        return None

    repos = config["tool"]["qen"]["repos"]
    if not isinstance(repos, list):
        return None

    # Find and remove matching repo
    removed_path: str | None = None
    new_repos = []
    for repo in repos:
        if isinstance(repo, dict):
            if repo.get("url") == url and repo.get("branch") == branch:
                path = repo.get("path")
                if isinstance(path, str):
                    removed_path = path
            else:
                new_repos.append(repo)

    if removed_path is None:
        return None  # Repo not found

    # Update config
    config["tool"]["qen"]["repos"] = new_repos

    # Write back to file
    try:
        handler.write(pyproject_path, config)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to write pyproject.toml: {e}") from e

    return removed_path
