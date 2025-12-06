"""
Shared pytest fixtures and configuration for all tests.
"""

import subprocess
from pathlib import Path

import pytest

from tests.helpers.qenvy_test import QenvyTest


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """
    Create a temporary git repository for testing.

    Returns path to the repository root.
    """
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user (required for commits)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


@pytest.fixture
def test_storage() -> QenvyTest:
    """Provide clean in-memory storage for each test.

    Returns:
        Fresh QenvyTest instance that will be cleaned up after test
    """
    storage = QenvyTest()
    yield storage
    storage.clear()


@pytest.fixture
def test_config(test_storage: QenvyTest, tmp_path: Path) -> tuple[QenvyTest, Path]:
    """Provide test storage and temp directory with initialized config.

    Returns:
        Tuple of (storage, meta_repo_path)
    """
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize with test data
    test_storage.write_profile(
        "main",
        {
            "meta_path": str(meta_repo),
            "org": "testorg",
            "current_project": None,
        },
    )

    return test_storage, meta_repo


@pytest.fixture
def meta_repo(temp_git_repo: Path) -> Path:
    """
    Create a meta repository with initial commit.

    Returns path to the meta repository.
    """
    # Create meta.toml
    meta_toml = temp_git_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')

    # Initial commit
    subprocess.run(
        ["git", "add", "meta.toml"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    return temp_git_repo


@pytest.fixture
def child_repo(tmp_path: Path) -> Path:
    """
    Create a child git repository for testing.

    Returns path to the child repository.
    """
    child_dir = tmp_path / "child_repo"
    child_dir.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    # Create initial file and commit
    readme = child_dir / "README.md"
    readme.write_text("# Child Repo\n")

    subprocess.run(
        ["git", "add", "README.md"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=child_dir,
        check=True,
        capture_output=True,
    )

    return child_dir
