"""Tests for qen workspace command."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from qen.commands.workspace import (
    create_workspace_files,
    generate_sublime_workspace,
    generate_vscode_workspace,
    workspace_command,
)
from tests.unit.helpers.qenvy_test import QenvyTest


@pytest.fixture
def mock_config(tmp_path: Path, test_storage: QenvyTest) -> tuple[Path, QenvyTest]:
    """Create mock configuration for testing.

    Returns:
        Tuple of (meta_path, storage)
    """
    meta_path = tmp_path / "meta"
    meta_path.mkdir()

    # Main config
    test_storage.write_profile(
        "main",
        {
            "meta_path": str(meta_path),
            "meta_remote": "https://github.com/testorg/meta",
            "meta_parent": str(meta_path.parent),
            "meta_default_branch": "main",
            "github_org": "testorg",
            "current_project": "test-project",
        },
    )

    # Project config
    test_storage.write_profile(
        "test-project",
        {
            "name": "test-project",
            "branch": "2025-12-08-test-project",
            "folder": "proj/2025-12-08-test-project",
            "repo": str(meta_path),
            "created": "2025-12-08T10:00:00Z",
        },
    )

    return meta_path, test_storage


@pytest.fixture
def project_with_repos(mock_config: tuple[Path, QenvyTest]) -> Path:
    """Create a test project with repositories.

    Returns:
        Path to project directory
    """
    meta_path, _ = mock_config
    project_dir = meta_path / "proj" / "2025-12-08-test-project"
    project_dir.mkdir(parents=True)

    # Create pyproject.toml with repos
    pyproject_content = """
[tool.qen]
created = "2025-12-08T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo1"
branch = "main"
path = "repos/repo1"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo2"
branch = "feature-branch"
path = "repos/repo2"
pr = 123
"""
    pyproject_path = project_dir / "pyproject.toml"
    pyproject_path.write_text(pyproject_content)

    # Create repo directories
    (project_dir / "repos" / "repo1").mkdir(parents=True)
    (project_dir / "repos" / "repo2").mkdir(parents=True)

    return project_dir


def test_generate_vscode_workspace_basic(project_with_repos: Path) -> None:
    """Test VS Code workspace generation with basic repos."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
        {
            "url": "https://github.com/testorg/repo2",
            "branch": "feature-branch",
            "path": "repos/repo2",
        },
    ]

    workspace = generate_vscode_workspace(project_with_repos, repos, "test-project")

    assert "folders" in workspace
    assert "settings" in workspace
    assert len(workspace["folders"]) == 3  # project root + 2 repos

    # Check project root
    assert workspace["folders"][0]["path"] == str(project_with_repos)
    assert "project root" in workspace["folders"][0]["name"]

    # Check repos
    assert "repo1" in workspace["folders"][1]["name"]
    assert "(main)" in workspace["folders"][1]["name"]
    assert "repo2" in workspace["folders"][2]["name"]
    assert "(feature-branch)" in workspace["folders"][2]["name"]


def test_generate_vscode_workspace_with_pr(project_with_repos: Path) -> None:
    """Test VS Code workspace generation includes PR info."""
    repos = [
        {
            "url": "https://github.com/testorg/repo1",
            "branch": "feature",
            "path": "repos/repo1",
            "pr": 456,
        },
    ]

    workspace = generate_vscode_workspace(project_with_repos, repos, "test-project")

    # Check that PR is included in folder name
    repo_folder = workspace["folders"][1]
    assert "[PR #456]" in repo_folder["name"]


def test_generate_vscode_workspace_skips_missing_repos(project_with_repos: Path) -> None:
    """Test VS Code workspace generation skips repos that don't exist on disk."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
        {
            "url": "https://github.com/testorg/missing",
            "branch": "main",
            "path": "repos/missing",
        },  # Doesn't exist
    ]

    workspace = generate_vscode_workspace(project_with_repos, repos, "test-project")

    # Should only have project root + repo1 (missing repo skipped)
    assert len(workspace["folders"]) == 2


def test_generate_sublime_workspace_basic(project_with_repos: Path) -> None:
    """Test Sublime Text workspace generation with basic repos."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
        {
            "url": "https://github.com/testorg/repo2",
            "branch": "develop",
            "path": "repos/repo2",
        },
    ]

    workspace = generate_sublime_workspace(project_with_repos, repos, "test-project")

    assert "folders" in workspace
    assert "settings" in workspace
    assert len(workspace["folders"]) == 3  # project root + 2 repos

    # Check project root
    assert workspace["folders"][0]["path"] == str(project_with_repos)
    assert "(root)" in workspace["folders"][0]["name"]

    # Check repos
    assert "repo1" in workspace["folders"][1]["name"]
    assert "(main)" in workspace["folders"][1]["name"]


def test_create_workspace_files_all_editors(project_with_repos: Path) -> None:
    """Test creating workspace files for all editors."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
    ]

    created = create_workspace_files(project_with_repos, repos, "test-project", editor="all")

    assert "vscode" in created
    assert "sublime" in created

    # Check files were created
    vscode_file = project_with_repos / "workspaces" / "vscode.code-workspace"
    sublime_file = project_with_repos / "workspaces" / "sublime.sublime-project"

    assert vscode_file.exists()
    assert sublime_file.exists()

    # Verify JSON is valid
    with open(vscode_file) as f:
        vscode_data = json.load(f)
        assert "folders" in vscode_data

    with open(sublime_file) as f:
        sublime_data = json.load(f)
        assert "folders" in sublime_data


def test_create_workspace_files_vscode_only(project_with_repos: Path) -> None:
    """Test creating workspace files for VS Code only."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
    ]

    created = create_workspace_files(project_with_repos, repos, "test-project", editor="vscode")

    assert "vscode" in created
    assert "sublime" not in created

    vscode_file = project_with_repos / "workspaces" / "vscode.code-workspace"
    sublime_file = project_with_repos / "workspaces" / "sublime.sublime-project"

    assert vscode_file.exists()
    assert not sublime_file.exists()


def test_create_workspace_files_sublime_only(project_with_repos: Path) -> None:
    """Test creating workspace files for Sublime Text only."""
    repos = [
        {"url": "https://github.com/testorg/repo1", "branch": "main", "path": "repos/repo1"},
    ]

    created = create_workspace_files(project_with_repos, repos, "test-project", editor="sublime")

    assert "sublime" in created
    assert "vscode" not in created

    vscode_file = project_with_repos / "workspaces" / "vscode.code-workspace"
    sublime_file = project_with_repos / "workspaces" / "sublime.sublime-project"

    assert not vscode_file.exists()
    assert sublime_file.exists()


def test_workspace_command_integration(mock_config: tuple[Path, QenvyTest]) -> None:
    """Test workspace command integration with config."""
    meta_path, storage = mock_config
    project_dir = meta_path / "proj" / "2025-12-08-test-project"
    project_dir.mkdir(parents=True)

    # Create pyproject.toml
    pyproject_content = """
[tool.qen]
created = "2025-12-08T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo1"
branch = "main"
path = "repos/repo1"
"""
    (project_dir / "pyproject.toml").write_text(pyproject_content)

    # Create repo directory
    (project_dir / "repos" / "repo1").mkdir(parents=True)

    # Run workspace command
    with (
        patch("qen.init_utils.ensure_initialized"),
        patch("qen.commands.workspace.ensure_correct_branch"),
        patch("qen.git_utils.get_current_branch", return_value="2025-12-08-test-project"),
        patch("qen.git_utils.has_uncommitted_changes", return_value=False),
        patch("qen.git_utils.checkout_branch"),
    ):
        workspace_command(
            editor="vscode",
            verbose=False,
            storage=storage,
            meta_path_override=meta_path,
            current_project_override="test-project",
        )

    # Verify workspace was created
    workspace_file = project_dir / "workspaces" / "vscode.code-workspace"
    assert workspace_file.exists()

    # Verify content
    with open(workspace_file) as f:
        data = json.load(f)
        assert "folders" in data
        assert len(data["folders"]) == 2  # project root + 1 repo


def test_workspace_command_no_repos(mock_config: tuple[Path, QenvyTest]) -> None:
    """Test workspace command with no repositories."""
    meta_path, storage = mock_config
    project_dir = meta_path / "proj" / "2025-12-08-test-project"
    project_dir.mkdir(parents=True)

    # Create pyproject.toml with no repos
    pyproject_content = """
[tool.qen]
created = "2025-12-08T10:00:00Z"
"""
    (project_dir / "pyproject.toml").write_text(pyproject_content)

    # Should not raise error, just create workspace with project root only
    with (
        patch("qen.init_utils.ensure_initialized"),
        patch("qen.commands.workspace.ensure_correct_branch"),
        patch("qen.git_utils.get_current_branch", return_value="2025-12-08-test-project"),
        patch("qen.git_utils.has_uncommitted_changes", return_value=False),
        patch("qen.git_utils.checkout_branch"),
    ):
        workspace_command(
            editor="vscode",
            verbose=False,
            storage=storage,
            meta_path_override=meta_path,
            current_project_override="test-project",
        )

    workspace_file = project_dir / "workspaces" / "vscode.code-workspace"
    assert workspace_file.exists()

    with open(workspace_file) as f:
        data = json.load(f)
        assert len(data["folders"]) == 1  # Only project root
