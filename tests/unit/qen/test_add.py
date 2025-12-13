"""Tests for qen add command and related utilities."""

import subprocess
from pathlib import Path

import pytest

from qen.commands.add import add_repository
from qen.git_utils import GitError
from qen.pyproject_utils import (
    PyProjectNotFoundError,
    add_repo_to_pyproject,
    read_pyproject,
    remove_repo_from_pyproject,
    repo_exists_in_pyproject,
)
from qen.repo_utils import (
    RepoUrlParseError,
    check_remote_branch_exists,
    clone_repository,
    infer_repo_path,
    parse_repo_url,
)
from tests.unit.helpers.qenvy_test import QenvyTest

# ==============================================================================
# Test URL Parsing
# ==============================================================================


class TestRepoUrlParsing:
    """Tests for parse_repo_url function."""

    def test_parse_https_url(self) -> None:
        """Test parsing full HTTPS URL."""
        result = parse_repo_url("https://github.com/myorg/myrepo")
        assert result == {
            "url": "https://github.com/myorg/myrepo",
            "host": "github.com",
            "org": "myorg",
            "repo": "myrepo",
        }

    def test_parse_https_url_with_git_extension(self) -> None:
        """Test parsing HTTPS URL with .git extension."""
        result = parse_repo_url("https://github.com/myorg/myrepo.git")
        assert result == {
            "url": "https://github.com/myorg/myrepo",
            "host": "github.com",
            "org": "myorg",
            "repo": "myrepo",
        }

    def test_parse_ssh_url(self) -> None:
        """Test parsing SSH URL."""
        result = parse_repo_url("git@github.com:myorg/myrepo.git")
        assert result == {
            "url": "https://github.com/myorg/myrepo",
            "host": "github.com",
            "org": "myorg",
            "repo": "myrepo",
        }

    def test_parse_org_slash_repo(self) -> None:
        """Test parsing org/repo format."""
        result = parse_repo_url("myorg/myrepo")
        assert result == {
            "url": "https://github.com/myorg/myrepo",
            "host": "github.com",
            "org": "myorg",
            "repo": "myrepo",
        }

    def test_parse_repo_only_with_org(self) -> None:
        """Test parsing repo-only format with org parameter."""
        result = parse_repo_url("myrepo", org="myorg")
        assert result == {
            "url": "https://github.com/myorg/myrepo",
            "host": "github.com",
            "org": "myorg",
            "repo": "myrepo",
        }

    def test_parse_repo_only_without_org_fails(self) -> None:
        """Test that repo-only format fails without org parameter."""
        with pytest.raises(RepoUrlParseError, match="Cannot parse repository"):
            parse_repo_url("myrepo")

    def test_parse_invalid_org_slash_repo(self) -> None:
        """Test that invalid org/repo format fails."""
        with pytest.raises(RepoUrlParseError, match="Invalid org/repo format"):
            parse_repo_url("myorg/myrepo/extra")

    def test_parse_empty_org_or_repo(self) -> None:
        """Test that empty org or repo fails."""
        # Empty repo
        with pytest.raises(RepoUrlParseError, match="Both parts must be non-empty"):
            parse_repo_url("myorg/")


class TestRepoPath:
    """Tests for infer_repo_path function."""

    def test_infer_repo_path(self) -> None:
        """Test inferring repository path with branch organization."""
        assert infer_repo_path("myrepo", "main") == "repos/main/myrepo"
        assert infer_repo_path("another-repo", "feature-x") == "repos/feature-x/another-repo"
        assert (
            infer_repo_path("deployment", "feature/add-support")
            == "repos/feature/add-support/deployment"
        )

        # Test that branch is required
        with pytest.raises(ValueError):
            infer_repo_path("myrepo")


# ==============================================================================
# Test Repository Cloning
# ==============================================================================


class TestCheckRemoteBranch:
    """Tests for check_remote_branch_exists function."""

    def test_check_remote_branch_exists_true(self, child_repo: Path) -> None:
        """Test that check_remote_branch_exists returns True for existing branch."""
        # Create a test branch in child_repo
        subprocess.run(
            ["git", "checkout", "-b", "test-branch"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Go back to main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Clone the repo
        dest = child_repo.parent / "cloned"
        clone_repository(str(child_repo), dest)

        # Check if test-branch exists on remote
        assert check_remote_branch_exists(dest, "test-branch") is True

    def test_check_remote_branch_exists_false(self, child_repo: Path) -> None:
        """Test that check_remote_branch_exists returns False for non-existent branch."""
        # Clone the repo
        dest = child_repo.parent / "cloned"
        clone_repository(str(child_repo), dest)

        # Check if non-existent branch exists on remote
        assert check_remote_branch_exists(dest, "nonexistent-branch") is False

    def test_check_remote_branch_main(self, child_repo: Path) -> None:
        """Test that check_remote_branch_exists works for main branch."""
        # Clone the repo
        dest = child_repo.parent / "cloned"
        clone_repository(str(child_repo), dest)

        # Check if main exists on remote
        assert check_remote_branch_exists(dest, "main") is True


class TestRepoCloning:
    """Tests for clone_repository function."""

    def test_clone_local_repo(self, child_repo: Path, tmp_path: Path) -> None:
        """Test cloning a local repository."""
        dest = tmp_path / "cloned"
        clone_repository(str(child_repo), dest)

        assert dest.exists()
        assert (dest / ".git").exists()
        assert (dest / "README.md").exists()

    def test_clone_with_branch(self, child_repo: Path, tmp_path: Path) -> None:
        """Test cloning with specific branch."""
        # Create a branch in the child repo
        subprocess.run(
            ["git", "checkout", "-b", "develop"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Add a file on the develop branch
        test_file = child_repo / "develop.txt"
        test_file.write_text("develop branch")
        subprocess.run(
            ["git", "add", "develop.txt"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add develop file"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Go back to main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Clone and checkout develop
        dest = tmp_path / "cloned"
        clone_repository(str(child_repo), dest, branch="develop")

        assert dest.exists()
        assert (dest / "develop.txt").exists()

    def test_clone_with_nonexistent_branch_yes_flag(self, child_repo: Path, tmp_path: Path) -> None:
        """Test cloning with a branch that doesn't exist remotely with --yes flag."""
        # Clone with a branch that doesn't exist in the repo, auto-confirm with yes=True
        dest = tmp_path / "cloned"
        clone_repository(str(child_repo), dest, branch="new-feature", yes=True)

        assert dest.exists()
        assert (dest / ".git").exists()
        assert (dest / "README.md").exists()

        # Verify we're on the new branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=dest,
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "new-feature"

    def test_clone_with_nonexistent_branch_no_yes_flag(
        self, child_repo: Path, tmp_path: Path, mocker
    ) -> None:
        """Test cloning with a branch that doesn't exist remotely without --yes flag raises error."""
        # Mock click.confirm to return False (user declines)
        mock_confirm = mocker.patch("click.confirm", return_value=False)

        # Clone with a branch that doesn't exist in the repo should raise error
        dest = tmp_path / "cloned"
        with pytest.raises(GitError, match="does not exist on remote"):
            clone_repository(str(child_repo), dest, branch="new-feature", yes=False)

        # Verify confirm was called
        mock_confirm.assert_called_once()

    def test_clone_fails_if_dest_exists(self, child_repo: Path, tmp_path: Path) -> None:
        """Test that cloning fails if destination exists."""
        dest = tmp_path / "existing"
        dest.mkdir()

        with pytest.raises(GitError, match="Destination already exists"):
            clone_repository(str(child_repo), dest)

    def test_clone_creates_parent_dirs(self, child_repo: Path, tmp_path: Path) -> None:
        """Test that cloning creates parent directories."""
        dest = tmp_path / "nested" / "path" / "cloned"
        clone_repository(str(child_repo), dest)

        assert dest.exists()
        assert (dest / ".git").exists()


# ==============================================================================
# Test pyproject.toml Operations
# ==============================================================================


class TestPyProjectUpdates:
    """Tests for pyproject.toml read/write operations."""

    def test_read_pyproject(self, tmp_path: Path) -> None:
        """Test reading pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo"
branch = "main"
path = "repos/repo"
"""
        )

        result = read_pyproject(tmp_path)
        assert "tool" in result
        assert "qen" in result["tool"]
        assert result["tool"]["qen"]["created"] == "2025-12-05T10:00:00Z"

    def test_read_pyproject_not_found(self, tmp_path: Path) -> None:
        """Test reading non-existent pyproject.toml."""
        with pytest.raises(PyProjectNotFoundError, match="pyproject.toml not found"):
            read_pyproject(tmp_path)

    def test_add_repo_to_empty_pyproject(self, tmp_path: Path) -> None:
        """Test adding repo to pyproject.toml with no [tool.qen] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        add_repo_to_pyproject(
            tmp_path,
            "https://github.com/org/repo",
            "main",
            "repos/repo",
        )

        result = read_pyproject(tmp_path)
        assert "tool" in result
        assert "qen" in result["tool"]
        assert "repos" in result["tool"]["qen"]
        assert len(result["tool"]["qen"]["repos"]) == 1
        assert result["tool"]["qen"]["repos"][0] == {
            "url": "https://github.com/org/repo",
            "branch": "main",
            "path": "repos/repo",
        }

    def test_add_multiple_repos(self, tmp_path: Path) -> None:
        """Test adding multiple repositories."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        # Add first repo
        add_repo_to_pyproject(
            tmp_path,
            "https://github.com/org/repo1",
            "main",
            "repos/repo1",
        )

        # Add second repo
        add_repo_to_pyproject(
            tmp_path,
            "https://github.com/org/repo2",
            "develop",
            "repos/repo2",
        )

        result = read_pyproject(tmp_path)
        assert len(result["tool"]["qen"]["repos"]) == 2
        assert result["tool"]["qen"]["repos"][0]["url"] == "https://github.com/org/repo1"
        assert result["tool"]["qen"]["repos"][1]["url"] == "https://github.com/org/repo2"

    def test_repo_exists_in_pyproject(self, tmp_path: Path) -> None:
        """Test checking if repository exists in pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/repo1"
"""
        )

        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo1", "main") is True
        assert (
            repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo1", "develop") is False
        )
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo2", "main") is False

    def test_repo_exists_no_pyproject(self, tmp_path: Path) -> None:
        """Test checking repo existence when pyproject.toml doesn't exist."""
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo", "main") is False

    def test_add_repo_to_nonexistent_pyproject(self, tmp_path: Path) -> None:
        """Test that adding repo fails if pyproject.toml doesn't exist."""
        with pytest.raises(PyProjectNotFoundError):
            add_repo_to_pyproject(
                tmp_path,
                "https://github.com/org/repo",
                "main",
                "repos/repo",
            )

    def test_add_same_repo_different_branches(self, tmp_path: Path) -> None:
        """Test adding same repository with different branches."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        # Add first branch
        add_repo_to_pyproject(
            tmp_path,
            "https://github.com/org/repo",
            "feature-1",
            "repos/feature-1/repo",
        )

        # Add second branch - should succeed
        add_repo_to_pyproject(
            tmp_path,
            "https://github.com/org/repo",
            "feature-2",
            "repos/feature-2/repo",
        )

        # Check pyproject.toml has both entries
        result = read_pyproject(tmp_path)
        repos = result["tool"]["qen"]["repos"]
        assert len(repos) == 2
        assert repos[0]["url"] == "https://github.com/org/repo"
        assert repos[0]["branch"] == "feature-1"
        assert repos[0]["path"] == "repos/feature-1/repo"
        assert repos[1]["url"] == "https://github.com/org/repo"
        assert repos[1]["branch"] == "feature-2"
        assert repos[1]["path"] == "repos/feature-2/repo"

    def test_prevent_duplicate_url_branch(self, tmp_path: Path) -> None:
        """Test that duplicate (url, branch) combination is detected."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo"
branch = "main"
path = "repos/repo"
"""
        )

        # Same URL with same branch should be detected as duplicate
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo", "main") is True

        # Same URL with different branch should not be duplicate
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo", "develop") is False

    def test_infer_repo_path_branch_organization(self, tmp_path: Path) -> None:
        """Test that repos are always organized by branch to prevent collisions."""
        # All repos are organized by branch
        path_main = infer_repo_path("deployment", "main", tmp_path)
        assert path_main == "repos/main/deployment"

        path_feature = infer_repo_path("deployment", "feature-x", tmp_path)
        assert path_feature == "repos/feature-x/deployment"

        # Same repo, different branches get different paths
        assert path_main != path_feature

        # Branch with slashes creates nested directories
        path_nested = infer_repo_path("deployment", "feature/add-support", tmp_path)
        assert path_nested == "repos/feature/add-support/deployment"


# ==============================================================================
# Test add Command Integration
# ==============================================================================


class TestAddCommand:
    """Integration tests for the add command."""

    def test_add_repository_full_workflow(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test full workflow of adding a repository."""
        # Setup: Create a meta repo with remote
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-05-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        # Add a remote to meta repo
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Initialize qen with in-memory storage
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        # Create a project
        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        # Create project structure
        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        # Create project config
        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        # Update current project
        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add repository using in-memory storage
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=False,
            storage=test_storage,
        )

        # Verify: Repository was cloned to branch-organized path
        cloned_path = project_dir / "repos" / "main" / "child_repo"
        assert cloned_path.exists()
        assert (cloned_path / ".git").exists()
        assert (cloned_path / "README.md").exists()

        # Verify: pyproject.toml was updated
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 1
        assert result["tool"]["qen"]["repos"][0]["path"] == "repos/main/child_repo"
        assert result["tool"]["qen"]["repos"][0]["branch"] == "main"

    def test_add_repository_with_custom_options(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test adding repository with custom branch and path."""
        # Setup similar to previous test
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-05-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Create custom directory
        (project_dir / "custom").mkdir()

        # Test: Add with custom options
        add_repository(
            repo=str(child_repo),
            branch="main",
            path="custom/myrepo",
            verbose=False,
            storage=test_storage,
        )

        # Verify: Repository was cloned to custom path
        cloned_path = project_dir / "custom" / "myrepo"
        assert cloned_path.exists()

        # Verify: pyproject.toml has custom path
        result = read_pyproject(project_dir)
        assert result["tool"]["qen"]["repos"][0]["path"] == "custom/myrepo"

    def test_add_duplicate_repository_fails(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test that adding duplicate repository fails."""
        # Setup
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-05-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Add repository first time
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=False,
            storage=test_storage,
        )

        # Try to add same repository again - should fail
        import click

        with pytest.raises(click.exceptions.Abort):
            add_repository(
                repo=str(child_repo),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )

    def test_add_same_repo_different_branches_integration(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test adding same repository with different branches - full integration."""
        # Setup
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-05-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Create a feature branch in child_repo
        subprocess.run(
            ["git", "checkout", "-b", "feature-1"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        feature_file = child_repo / "feature1.txt"
        feature_file.write_text("feature 1")
        subprocess.run(
            ["git", "add", "feature1.txt"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add feature 1"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Add repository with main branch
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=False,
            storage=test_storage,
        )

        # Add same repository with feature-1 branch - should succeed
        add_repository(
            repo=str(child_repo),
            branch="feature-1",
            path=None,
            verbose=False,
            storage=test_storage,
        )

        # Verify: Both clones exist in branch-organized paths
        clone_main = project_dir / "repos" / "main" / "child_repo"
        clone_feature = project_dir / "repos" / "feature-1" / "child_repo"
        assert clone_main.exists()
        assert clone_feature.exists()
        assert (clone_main / "README.md").exists()
        assert (clone_feature / "feature1.txt").exists()
        assert not (clone_main / "feature1.txt").exists()  # Feature file not in main

        # Verify: pyproject.toml has both entries
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 2
        assert result["tool"]["qen"]["repos"][0]["branch"] == "main"
        assert result["tool"]["qen"]["repos"][0]["path"] == "repos/main/child_repo"
        assert result["tool"]["qen"]["repos"][1]["branch"] == "feature-1"
        assert result["tool"]["qen"]["repos"][1]["path"] == "repos/feature-1/child_repo"

        # Try to add main branch again - should fail
        import click

        with pytest.raises(click.exceptions.Abort):
            add_repository(
                repo=str(child_repo),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )

    def test_add_repository_uses_meta_branch_by_default(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test that add_repository defaults to meta repo's current branch."""
        # Setup: Create a meta repo with a feature branch
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="feature-branch")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Make an initial commit so HEAD exists
        (meta_repo / "README.md").write_text("# Meta repo\n")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Create and switch to a feature branch in meta repo
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "feature-branch"  # Project branch matches meta branch
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Create feature-branch in child_repo
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        feature_file = child_repo / "feature.txt"
        feature_file.write_text("feature content")
        subprocess.run(
            ["git", "add", "feature.txt"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add feature"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Test: Add repository without specifying branch
        # Should use meta repo's current branch (feature-branch)
        add_repository(
            repo=str(child_repo),
            branch=None,  # Don't specify branch - should default to meta branch
            path=None,
            verbose=False,
            storage=test_storage,
        )

        # Verify: Repository was cloned with feature-branch to branch-organized path
        cloned_path = project_dir / "repos" / "feature-branch" / "child_repo"
        assert cloned_path.exists()
        assert (cloned_path / ".git").exists()
        assert (cloned_path / "feature.txt").exists()  # Feature file should exist

        # Verify: pyproject.toml has feature-branch
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 1
        assert result["tool"]["qen"]["repos"][0]["branch"] == "feature-branch"
        assert result["tool"]["qen"]["repos"][0]["path"] == "repos/feature-branch/child_repo"


# ==============================================================================
# Test Repository Removal from pyproject.toml
# ==============================================================================


class TestRemoveRepoFromPyproject:
    """Tests for removing repositories from pyproject.toml."""

    def test_remove_existing_repo(self, tmp_path: Path) -> None:
        """Test removing an existing repository."""
        from qenvy.formats import TOMLHandler

        # Setup: Create pyproject.toml with two repos
        pyproject_path = tmp_path / "pyproject.toml"
        config = {
            "tool": {
                "qen": {
                    "repos": [
                        {
                            "url": "https://github.com/org/repo1",
                            "branch": "main",
                            "path": "repos/main/repo1",
                        },
                        {
                            "url": "https://github.com/org/repo2",
                            "branch": "dev",
                            "path": "repos/dev/repo2",
                        },
                    ]
                }
            }
        }
        handler = TOMLHandler()
        handler.write(pyproject_path, config)

        # Action: Remove one repo
        removed_path = remove_repo_from_pyproject(tmp_path, "https://github.com/org/repo1", "main")

        # Assert: Returns correct path and only remaining repo exists
        assert removed_path == "repos/main/repo1"
        updated_config = handler.read(pyproject_path)
        repos = updated_config["tool"]["qen"]["repos"]
        assert len(repos) == 1
        assert repos[0]["url"] == "https://github.com/org/repo2"

    def test_remove_nonexistent_repo(self, tmp_path: Path) -> None:
        """Test removing a repo that doesn't exist."""
        from qenvy.formats import TOMLHandler

        # Setup
        pyproject_path = tmp_path / "pyproject.toml"
        config = {
            "tool": {
                "qen": {
                    "repos": [
                        {
                            "url": "https://github.com/org/repo1",
                            "branch": "main",
                            "path": "repos/main/repo1",
                        }
                    ]
                }
            }
        }
        handler = TOMLHandler()
        handler.write(pyproject_path, config)

        # Action: Try to remove different repo
        removed_path = remove_repo_from_pyproject(tmp_path, "https://github.com/org/other", "main")

        # Assert: Returns None, original repo unchanged
        assert removed_path is None
        updated_config = handler.read(pyproject_path)
        repos = updated_config["tool"]["qen"]["repos"]
        assert len(repos) == 1

    def test_remove_repo_no_pyproject(self, tmp_path: Path) -> None:
        """Test removing repo when pyproject.toml doesn't exist."""
        # Action & Assert
        with pytest.raises(PyProjectNotFoundError):
            remove_repo_from_pyproject(tmp_path, "https://github.com/org/repo", "main")


# ==============================================================================
# Test --force Flag Integration
# ==============================================================================


class TestAddCommandForce:
    """Integration tests for the --force flag."""

    def test_add_duplicate_repository_fails_without_force(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test that adding duplicate repository fails WITHOUT --force flag."""
        import click

        # Setup: Create meta repo with project
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-07-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "2025-12-07-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-07T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-07T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # First add - should succeed
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=False,
            force=False,
            storage=test_storage,
        )

        # Second add WITHOUT force - should fail
        with pytest.raises(click.exceptions.Abort):
            add_repository(
                repo=str(child_repo),
                branch="main",
                path=None,
                verbose=False,
                force=False,
                storage=test_storage,
            )

    def test_add_duplicate_repository_with_force(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
        mocker,
    ) -> None:
        """Test that adding duplicate repository succeeds WITH --force flag."""
        from qenvy.formats import TOMLHandler

        # Setup: Create meta repo with project
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-12-07-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm to automatically proceed with branch switch if needed
        mocker.patch("click.confirm", return_value=True)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "test-project"
        branch = "2025-12-07-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-07T10:00:00Z"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-07T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # First add - should succeed
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=False,
            force=False,
            storage=test_storage,
        )

        # Create a marker file in the clone to verify it gets removed
        repos_dir = project_dir / "repos" / "main"
        repos_dir.mkdir(parents=True, exist_ok=True)
        repo_clone = repos_dir / "child_repo"
        repo_clone.mkdir(exist_ok=True)
        marker_file = repo_clone / "MARKER"
        marker_file.write_text("original")

        # Second add WITH force - should succeed and re-clone
        add_repository(
            repo=str(child_repo),
            branch="main",
            path=None,
            verbose=True,
            force=True,
            storage=test_storage,
        )

        # Verify:
        # 1. Marker file is gone (directory was removed and re-cloned)
        assert not marker_file.exists(), "Marker file should be removed with --force"

        # 2. Only one entry in pyproject.toml (not duplicated)
        handler = TOMLHandler()
        updated_config = handler.read(pyproject)
        repos = updated_config["tool"]["qen"]["repos"]
        assert len(repos) == 1, "Should have exactly one repo entry"
        assert repos[0]["url"] == str(child_repo)
        assert repos[0]["branch"] == "main"
