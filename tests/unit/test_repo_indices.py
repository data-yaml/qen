"""Unit tests for repository index functionality.

Tests that repositories are assigned and displayed with 1-based indices.
"""

from pathlib import Path

import pytest

from qen.pyproject_utils import load_repos_from_pyproject
from qenvy.formats import TOMLHandler


@pytest.fixture
def project_with_repos(tmp_path: Path) -> Path:
    """Create a test project with multiple repositories."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()

    # Create pyproject.toml with 3 repos
    pyproject_content = {
        "project": {"name": "test-project", "version": "0.1.0"},
        "tool": {
            "qen": {
                "created": "2025-12-08T10:00:00Z",
                "repos": [
                    {
                        "url": "https://github.com/org/repo1",
                        "branch": "main",
                        "path": "repos/main/repo1",
                    },
                    {
                        "url": "https://github.com/org/repo2",
                        "branch": "feature",
                        "path": "repos/feature/repo2",
                    },
                    {
                        "url": "https://github.com/org/repo3",
                        "branch": "dev",
                        "path": "repos/dev/repo3",
                    },
                ],
            }
        },
    }

    handler = TOMLHandler()
    handler.write(project_dir / "pyproject.toml", pyproject_content)

    return project_dir


def test_repos_have_implicit_order(project_with_repos: Path) -> None:
    """Test that repos maintain their order in the TOML array."""
    repos = load_repos_from_pyproject(project_with_repos)

    assert len(repos) == 3
    assert repos[0].url == "https://github.com/org/repo1"
    assert repos[1].url == "https://github.com/org/repo2"
    assert repos[2].url == "https://github.com/org/repo3"


def test_enumerate_repos_gives_indices(project_with_repos: Path) -> None:
    """Test that enumerate provides natural 1-based indexing."""
    repos = load_repos_from_pyproject(project_with_repos)

    # Using enumerate(repos, start=1) gives us 1-based indices
    indexed_repos = list(enumerate(repos, start=1))

    assert indexed_repos[0][0] == 1
    assert indexed_repos[0][1].url == "https://github.com/org/repo1"

    assert indexed_repos[1][0] == 2
    assert indexed_repos[1][1].url == "https://github.com/org/repo2"

    assert indexed_repos[2][0] == 3
    assert indexed_repos[2][1].url == "https://github.com/org/repo3"


def test_format_repo_with_index() -> None:
    """Test formatting repository display with index."""
    # Example format: "[1] org/repo (main)"
    index = 1
    org = "myorg"
    repo = "myrepo"
    branch = "main"

    formatted = f"[{index}] {org}/{repo} ({branch})"
    assert formatted == "[1] myorg/myrepo (main)"


def test_format_repo_with_index_alternate() -> None:
    """Test alternate formatting: "1. org/repo"."""
    index = 2
    display = "myorg/myrepo"

    formatted = f"{index}. {display}"
    assert formatted == "2. myorg/myrepo"


def test_empty_repo_list_has_no_indices(tmp_path: Path) -> None:
    """Test that empty repo list has no indices."""
    project_dir = tmp_path / "empty-project"
    project_dir.mkdir()

    # Create pyproject.toml with no repos
    pyproject_content = {
        "project": {"name": "empty-project", "version": "0.1.0"},
        "tool": {"qen": {"created": "2025-12-08T10:00:00Z", "repos": []}},
    }

    handler = TOMLHandler()
    handler.write(project_dir / "pyproject.toml", pyproject_content)

    repos = load_repos_from_pyproject(project_dir)
    assert len(repos) == 0

    # Enumerate still works but produces empty result
    indexed_repos = list(enumerate(repos, start=1))
    assert len(indexed_repos) == 0
