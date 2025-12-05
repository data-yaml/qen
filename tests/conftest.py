"""
Shared pytest fixtures and configuration for all tests.
"""

import subprocess
from pathlib import Path

import pytest


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
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Isolate XDG_CONFIG_HOME to a temporary directory.

    This ensures tests don't interfere with real user configuration.
    Returns the isolated config directory.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_dir))

    # Clear platformdirs cache if it exists
    try:
        import platformdirs
        if hasattr(platformdirs, "_cache"):
            platformdirs._cache.clear()
    except ImportError:
        pass

    return config_dir


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
