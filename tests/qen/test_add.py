"""Tests for qen add command and related utilities."""

import shutil
import subprocess
from pathlib import Path

import pytest

from qen.commands.add import add_repository
from qen.config import QenConfig
from qen.git_utils import GitError
from qen.pyproject_utils import (
    PyProjectNotFoundError,
    add_repo_to_pyproject,
    read_pyproject,
    repo_exists_in_pyproject,
)
from qen.repo_utils import (
    RepoUrlParseError,
    clone_repository,
    infer_repo_path,
    parse_repo_url,
)
from tests.helpers.qenvy_test import QenvyTest


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
        """Test inferring repository path."""
        assert infer_repo_path("myrepo") == "repos/myrepo"
        assert infer_repo_path("another-repo") == "repos/another-repo"


# ==============================================================================
# Test Repository Cloning
# ==============================================================================


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
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo"
branch = "main"
path = "repos/repo"
""")

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
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"
""")

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
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/repo1"
""")

        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo1") is True
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo2") is False

    def test_repo_exists_no_pyproject(self, tmp_path: Path) -> None:
        """Test checking repo existence when pyproject.toml doesn't exist."""
        assert repo_exists_in_pyproject(tmp_path, "https://github.com/org/repo") is False

    def test_add_repo_to_nonexistent_pyproject(self, tmp_path: Path) -> None:
        """Test that adding repo fails if pyproject.toml doesn't exist."""
        with pytest.raises(PyProjectNotFoundError):
            add_repo_to_pyproject(
                tmp_path,
                "https://github.com/org/repo",
                "main",
                "repos/repo",
            )


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
    ) -> None:
        """Test full workflow of adding a repository."""
        # Setup: Create a meta repo with remote
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Add a remote to meta repo
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Initialize qen with in-memory storage
        test_storage.write_profile("main", {
            "meta_path": str(meta_repo),
            "org": "testorg",
            "current_project": None,
        })

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
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"
""")

        # Create project config
        test_storage.write_profile(project_name, {
            "name": project_name,
            "branch": branch,
            "folder": folder,
            "created": "2025-12-05T10:00:00Z",
        })

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

        # Verify: Repository was cloned
        cloned_path = project_dir / "repos" / "child_repo"
        assert cloned_path.exists()
        assert (cloned_path / ".git").exists()
        assert (cloned_path / "README.md").exists()

        # Verify: pyproject.toml was updated
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 1
        assert result["tool"]["qen"]["repos"][0]["path"] == "repos/child_repo"
        assert result["tool"]["qen"]["repos"][0]["branch"] == "main"

    def test_add_repository_with_custom_options(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
    ) -> None:
        """Test adding repository with custom branch and path."""
        # Setup similar to previous test
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile("main", {
            "meta_path": str(meta_repo),
            "org": "testorg",
            "current_project": None,
        })

        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"
""")

        test_storage.write_profile(project_name, {
            "name": project_name,
            "branch": branch,
            "folder": folder,
            "created": "2025-12-05T10:00:00Z",
        })

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
    ) -> None:
        """Test that adding duplicate repository fails."""
        # Setup
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile("main", {
            "meta_path": str(meta_repo),
            "org": "testorg",
            "current_project": None,
        })

        project_name = "test-project"
        branch = "2025-12-05-test-project"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Test Project\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text("""
[tool.qen]
created = "2025-12-05T10:00:00Z"
""")

        test_storage.write_profile(project_name, {
            "name": project_name,
            "branch": branch,
            "folder": folder,
            "created": "2025-12-05T10:00:00Z",
        })

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
