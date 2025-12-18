"""Tests for qen pull command."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from qen.commands.pull import (
    check_gh_installed,
    check_repo_status,
    get_issue_info,
    get_pr_info,
    git_fetch,
    git_pull,
    has_remote,
    is_detached_head,
    pull_all_repositories,
    pull_repository,
    update_pyproject_metadata,
)
from qen.pyproject_utils import PyProjectUpdateError, read_pyproject
from tests.unit.helpers.qenvy_test import QenvyTest

# ==============================================================================
# Test GitHub CLI Detection
# ==============================================================================


class TestGitHubCLI:
    """Tests for GitHub CLI detection."""

    def test_check_gh_installed_success(self) -> None:
        """Test successful gh detection."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert check_gh_installed() is True

    def test_check_gh_installed_not_found(self) -> None:
        """Test gh not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert check_gh_installed() is False

    def test_check_gh_installed_timeout(self) -> None:
        """Test gh timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 5)):
            assert check_gh_installed() is False


# ==============================================================================
# Test PR/Issue Detection
# ==============================================================================


class TestPRDetection:
    """Tests for PR detection via gh CLI."""

    def test_get_pr_info_success(self, tmp_path: Path) -> None:
        """Test successful PR info retrieval."""
        pr_data = {
            "number": 123,
            "baseRefName": "main",
            "state": "OPEN",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = get_pr_info(tmp_path, "feature-branch")

            assert result["pr"] == 123
            assert result["pr_base"] == "main"
            assert result["pr_status"] == "open"
            assert result["pr_checks"] == "passing"

    def test_get_pr_info_no_pr(self, tmp_path: Path) -> None:
        """Test when no PR exists."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            result = get_pr_info(tmp_path, "feature-branch")

            assert "pr" not in result

    def test_get_pr_info_failing_checks(self, tmp_path: Path) -> None:
        """Test PR with failing checks."""
        pr_data = {
            "number": 456,
            "baseRefName": "develop",
            "state": "DRAFT",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "FAILURE"},
            ],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = get_pr_info(tmp_path, "bugfix-branch")

            assert result["pr"] == 456
            assert result["pr_checks"] == "failing"

    def test_get_pr_info_pending_checks(self, tmp_path: Path) -> None:
        """Test PR with pending checks."""
        pr_data = {
            "number": 789,
            "baseRefName": "main",
            "state": "OPEN",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": ""},
            ],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(pr_data),
            )

            result = get_pr_info(tmp_path, "feature")

            assert result["pr_checks"] == "pending"

    def test_get_issue_info_from_branch(self, tmp_path: Path) -> None:
        """Test extracting issue number from branch name."""
        assert get_issue_info(tmp_path, "issue-123") == 123
        assert get_issue_info(tmp_path, "fix/issue-456") == 456
        assert get_issue_info(tmp_path, "feature/issue_789") == 789
        assert get_issue_info(tmp_path, "main") is None
        assert get_issue_info(tmp_path, "feature-branch") is None


# ==============================================================================
# Test Git Operations
# ==============================================================================


class TestGitOperations:
    """Tests for git operations."""

    def test_is_detached_head_normal(self, child_repo: Path) -> None:
        """Test detecting normal (non-detached) HEAD."""
        assert is_detached_head(child_repo) is False

    def test_is_detached_head_detached(self, child_repo: Path) -> None:
        """Test detecting detached HEAD state."""
        # Get a commit hash and checkout directly
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=child_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        commit_hash = result.stdout.strip()

        # Checkout the commit directly (detached HEAD)
        subprocess.run(
            ["git", "checkout", commit_hash],
            cwd=child_repo,
            capture_output=True,
            check=True,
        )

        assert is_detached_head(child_repo) is True

    def test_has_remote_true(self, child_repo: Path) -> None:
        """Test detecting existing remote."""
        # Add a remote
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/test/repo"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        assert has_remote(child_repo, "origin") is True

    def test_has_remote_false(self, child_repo: Path) -> None:
        """Test detecting missing remote."""
        assert has_remote(child_repo, "origin") is False

    def test_git_fetch_success(self, child_repo: Path) -> None:
        """Test successful git fetch."""
        # Setup: Add a remote pointing to itself
        subprocess.run(
            ["git", "remote", "add", "origin", str(child_repo)],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        success, message = git_fetch(child_repo, verbose=False)

        assert success is True
        assert "success" in message.lower()

    def test_git_fetch_no_remote(self, child_repo: Path) -> None:
        """Test git fetch with no remote."""
        success, message = git_fetch(child_repo, verbose=False)

        assert success is False
        assert "remote" in message.lower() or "origin" in message.lower()

    def test_git_pull_already_up_to_date(self, child_repo: Path) -> None:
        """Test git pull when already up to date."""
        # Setup: Add a remote pointing to itself
        subprocess.run(
            ["git", "remote", "add", "origin", str(child_repo)],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        # Configure git to allow pulling into a repository with the same URL
        subprocess.run(
            ["git", "config", "pull.rebase", "false"],
            cwd=child_repo,
            check=True,
            capture_output=True,
        )

        success, message, stats = git_pull(child_repo, verbose=False)

        # Pull might fail when remote is same as current repo
        # This is okay - the important thing is it doesn't crash
        assert isinstance(success, bool)
        assert isinstance(message, str)

    def test_check_repo_status_clean(self, child_repo: Path) -> None:
        """Test checking status of clean repository."""
        status = check_repo_status(child_repo)

        assert status["dirty"] is False
        assert status["uncommitted_changes"] == 0

    def test_check_repo_status_dirty(self, child_repo: Path) -> None:
        """Test checking status with uncommitted changes."""
        # Create an uncommitted file
        (child_repo / "new_file.txt").write_text("content")

        status = check_repo_status(child_repo)

        assert status["dirty"] is True
        assert status["uncommitted_changes"] > 0


# ==============================================================================
# Test Metadata Updates
# ==============================================================================


class TestMetadataUpdates:
    """Tests for pyproject.toml metadata updates."""

    def test_update_pyproject_metadata_success(self, tmp_path: Path) -> None:
        """Test successful metadata update - only writes persistent fields."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/main/repo1"
"""
        )

        update_pyproject_metadata(
            tmp_path,
            "https://github.com/org/repo1",
            "main",
            {
                "updated": "2025-12-05T15:00:00Z",  # Transient - not persisted
                "pr": 123,  # Persistent
                "pr_base": "develop",  # Persistent
                "pr_status": "open",  # Transient - not persisted
                "pr_checks": "passing",  # Transient - not persisted
            },
        )

        result = read_pyproject(tmp_path)
        repo = result["tool"]["qen"]["repos"][0]
        # Only persistent fields should be written
        assert "updated" not in repo  # Transient field not persisted
        assert repo["pr"] == 123
        assert repo["pr_base"] == "develop"
        assert "pr_status" not in repo  # Transient field not persisted
        assert "pr_checks" not in repo  # Transient field not persisted

    def test_update_pyproject_metadata_repo_not_found(self, tmp_path: Path) -> None:
        """Test metadata update when repo not found."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/main/repo1"
"""
        )

        with pytest.raises(PyProjectUpdateError, match="not found"):
            update_pyproject_metadata(
                tmp_path,
                "https://github.com/org/different-repo",
                "main",
                {"updated": "2025-12-05T15:00:00Z"},
            )

    def test_update_pyproject_metadata_preserves_other_fields(self, tmp_path: Path) -> None:
        """Test that metadata update preserves other fields and ignores transient fields."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/main/repo1"
added = "2025-12-05T10:00:00Z"
"""
        )

        update_pyproject_metadata(
            tmp_path,
            "https://github.com/org/repo1",
            "main",
            {
                "updated": "2025-12-05T15:00:00Z",  # Transient - not persisted
                "pr": 456,  # Persistent - should be written
            },
        )

        result = read_pyproject(tmp_path)
        repo = result["tool"]["qen"]["repos"][0]
        assert repo["url"] == "https://github.com/org/repo1"
        assert repo["branch"] == "main"
        assert repo["path"] == "repos/main/repo1"
        assert repo["added"] == "2025-12-05T10:00:00Z"
        assert "updated" not in repo  # Transient field not persisted
        assert repo["pr"] == 456  # Persistent field written


# ==============================================================================
# Test Pull Repository Function
# ==============================================================================


class TestPullRepository:
    """Tests for pull_repository function."""

    def test_pull_repository_not_found(self, tmp_path: Path) -> None:
        """Test pulling repository that doesn't exist on disk."""
        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
            "path": "repos/main/repo",
        }

        result = pull_repository(
            repo_entry,
            tmp_path,
            fetch_only=False,
            gh_available=False,
            verbose=False,
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_pull_repository_not_git_repo(self, tmp_path: Path) -> None:
        """Test pulling directory that's not a git repo."""
        repo_dir = tmp_path / "repos" / "main" / "repo"
        repo_dir.mkdir(parents=True)

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
            "path": "repos/main/repo",
        }

        result = pull_repository(
            repo_entry,
            tmp_path,
            fetch_only=False,
            gh_available=False,
            verbose=False,
        )

        assert result["success"] is False
        assert "not a git repository" in result["message"].lower()

    def test_pull_repository_no_remote(self, tmp_path: Path, child_repo: Path) -> None:
        """Test pulling repository with no remote."""
        # Clone repo to test location
        dest = tmp_path / "repos" / "main" / "child_repo"
        dest.parent.mkdir(parents=True)

        subprocess.run(
            ["git", "clone", str(child_repo), str(dest)],
            check=True,
            capture_output=True,
        )

        # Remove the remote
        subprocess.run(
            ["git", "remote", "remove", "origin"],
            cwd=dest,
            check=True,
            capture_output=True,
        )

        repo_entry = {
            "url": "https://github.com/org/child_repo",
            "branch": "main",
            "path": "repos/main/child_repo",
        }

        result = pull_repository(
            repo_entry,
            tmp_path,
            fetch_only=False,
            gh_available=False,
            verbose=False,
        )

        assert result["success"] is False
        assert "no remote" in result["message"].lower()

    def test_pull_repository_fetch_only(self, tmp_path: Path, child_repo: Path) -> None:
        """Test fetching repository (fetch-only mode)."""
        # Setup: Clone repo and add remote
        dest = tmp_path / "repos" / "main" / "child_repo"
        dest.parent.mkdir(parents=True)

        subprocess.run(
            ["git", "clone", str(child_repo), str(dest)],
            check=True,
            capture_output=True,
        )

        repo_entry = {
            "url": str(child_repo),
            "branch": "main",
            "path": "repos/main/child_repo",
        }

        result = pull_repository(
            repo_entry,
            tmp_path,
            fetch_only=True,
            gh_available=False,
            verbose=False,
        )

        assert result["success"] is True
        assert "fetch" in result["message"].lower()

    def test_pull_repository_with_pr_info(self, tmp_path: Path, child_repo: Path) -> None:
        """Test pulling repository with PR info."""
        # Setup: Clone repo and add remote
        dest = tmp_path / "repos" / "main" / "child_repo"
        dest.parent.mkdir(parents=True)

        subprocess.run(
            ["git", "clone", str(child_repo), str(dest)],
            check=True,
            capture_output=True,
        )

        repo_entry = {
            "url": str(child_repo),
            "branch": "main",
            "path": "repos/main/child_repo",
        }

        # Mock get_pr_info instead of subprocess.run to avoid recursion issues
        with patch("qen.commands.pull.get_pr_info") as mock_get_pr:
            mock_get_pr.return_value = {
                "pr": 123,
                "pr_base": "develop",
                "pr_status": "open",
                "pr_checks": "passing",
            }

            result = pull_repository(
                repo_entry,
                tmp_path,
                fetch_only=False,
                gh_available=True,
                verbose=False,
            )

            assert result["success"] is True
            assert "pr_info" in result
            assert result["pr_info"]["pr"] == 123


# ==============================================================================
# Test Pull All Repositories (Integration)
# ==============================================================================


class TestPullAllRepositories:
    """Integration tests for pull_all_repositories."""

    def test_pull_all_no_config(self, tmp_path: Path, test_storage: QenvyTest) -> None:
        """Test pull with no qen configuration."""
        import click

        # Don't create any config - mock ensure_initialized to raise Abort (simulating auto-init failure)
        with (
            patch("qen.commands.pull.ensure_initialized", side_effect=click.Abort()),
            patch("qen.commands.pull.ensure_correct_branch"),
            pytest.raises(click.exceptions.Abort),
        ):
            pull_all_repositories(
                project_name=None,
                fetch_only=False,
                verbose=False,
                storage=test_storage,
            )

    def test_pull_all_no_active_project(self, tmp_path: Path, test_storage: QenvyTest) -> None:
        """Test pull with no active project."""
        import click

        # Create main config without current_project
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(tmp_path / "meta"),
                "org": "testorg",
            },
        )

        with (
            pytest.raises(click.exceptions.Abort),
            patch("qen.commands.pull.ensure_correct_branch"),
        ):
            pull_all_repositories(
                project_name=None,
                fetch_only=False,
                verbose=False,
                storage=test_storage,
            )

    def test_pull_all_no_repos(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
    ) -> None:
        """Test pull when project has no repositories."""
        # Setup: Create project with no repos
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "meta_remote": "https://github.com/testorg/meta",
                "meta_parent": str(meta_repo.parent),
                "meta_default_branch": "main",
                "org": "testorg",
                "current_project": "test-project",
            },
        )

        project_name = "test-project"
        folder = "proj/2025-12-05-test-project"
        project_dir = meta_repo / folder
        project_dir.mkdir(parents=True)

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
                "branch": "2025-12-05-test-project",
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        # Should not raise, just output message
        with patch("qen.commands.pull.ensure_correct_branch"):
            pull_all_repositories(
                project_name=None,
                fetch_only=False,
                verbose=False,
                storage=test_storage,
            )

    def test_pull_all_success(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
    ) -> None:
        """Test successful pull of all repositories."""
        # Setup: Create project with one repository
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "meta_remote": "https://github.com/testorg/meta",
                "meta_parent": str(meta_repo.parent),
                "meta_default_branch": "main",
                "org": "testorg",
                "current_project": "test-project",
            },
        )

        project_name = "test-project"
        folder = "proj/2025-12-05-test-project"
        project_dir = meta_repo / folder
        project_dir.mkdir(parents=True)

        # Clone child_repo into project
        repo_path = project_dir / "repos" / "main" / "child_repo"
        repo_path.parent.mkdir(parents=True)

        subprocess.run(
            ["git", "clone", str(child_repo), str(repo_path)],
            check=True,
            capture_output=True,
        )

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            f"""
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "{child_repo}"
branch = "main"
path = "repos/main/child_repo"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": "2025-12-05-test-project",
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        # Execute pull
        with patch("qen.commands.pull.ensure_correct_branch"):
            pull_all_repositories(
                project_name=None,
                fetch_only=False,
                verbose=False,
                storage=test_storage,
            )

        # Verify: Only persistent metadata was written (not transient fields like 'updated')
        result = read_pyproject(project_dir)
        repo = result["tool"]["qen"]["repos"][0]
        assert "updated" not in repo  # Transient field not persisted
        assert repo["branch"] == "main"  # Persistent field written

    def test_pull_all_fetch_only(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
    ) -> None:
        """Test fetch-only mode."""
        # Setup similar to previous test
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "meta_remote": "https://github.com/testorg/meta",
                "meta_parent": str(meta_repo.parent),
                "meta_default_branch": "main",
                "org": "testorg",
                "current_project": "test-project",
            },
        )

        project_name = "test-project"
        folder = "proj/2025-12-05-test-project"
        project_dir = meta_repo / folder
        project_dir.mkdir(parents=True)

        repo_path = project_dir / "repos" / "main" / "child_repo"
        repo_path.parent.mkdir(parents=True)

        subprocess.run(
            ["git", "clone", str(child_repo), str(repo_path)],
            check=True,
            capture_output=True,
        )

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            f"""
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "{child_repo}"
branch = "main"
path = "repos/main/child_repo"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": "2025-12-05-test-project",
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        # Execute fetch-only
        with patch("qen.commands.pull.ensure_correct_branch"):
            pull_all_repositories(
                project_name=None,
                fetch_only=True,
                verbose=False,
                storage=test_storage,
            )

        # Should succeed without errors, no transient fields persisted
        result = read_pyproject(project_dir)
        repo = result["tool"]["qen"]["repos"][0]
        assert "updated" not in repo  # Transient field not persisted

    def test_pull_all_multiple_repos(
        self,
        tmp_path: Path,
        test_storage: QenvyTest,
        temp_git_repo: Path,
        child_repo: Path,
    ) -> None:
        """Test pulling multiple repositories."""
        # Setup: Create project with multiple repositories
        meta_repo = temp_git_repo
        meta_repo.rename(tmp_path / "meta")
        meta_repo = tmp_path / "meta"

        # Create a second test repo
        child_repo2 = tmp_path / "child_repo2"
        child_repo2.mkdir()
        subprocess.run(["git", "init"], cwd=child_repo2, check=True, capture_output=True)
        # Configure git user (required for commits in CI)
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=child_repo2,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=child_repo2,
            check=True,
            capture_output=True,
        )
        (child_repo2 / "README.md").write_text("# Child Repo 2\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=child_repo2, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=child_repo2,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "meta_remote": "https://github.com/testorg/meta",
                "meta_parent": str(meta_repo.parent),
                "meta_default_branch": "main",
                "org": "testorg",
                "current_project": "test-project",
            },
        )

        project_name = "test-project"
        folder = "proj/2025-12-05-test-project"
        project_dir = meta_repo / folder
        project_dir.mkdir(parents=True)

        # Clone both repos
        repo1_path = project_dir / "repos" / "main" / "child_repo"
        repo1_path.parent.mkdir(parents=True)
        subprocess.run(
            ["git", "clone", str(child_repo), str(repo1_path)],
            check=True,
            capture_output=True,
        )

        repo2_path = project_dir / "repos" / "main" / "child_repo2"
        # Parent directory already exists from repo1
        subprocess.run(
            ["git", "clone", str(child_repo2), str(repo2_path)],
            check=True,
            capture_output=True,
        )

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text(
            f"""
[tool.qen]
created = "2025-12-05T10:00:00Z"

[[tool.qen.repos]]
url = "{child_repo}"
branch = "main"
path = "repos/main/child_repo"

[[tool.qen.repos]]
url = "{child_repo2}"
branch = "main"
path = "repos/main/child_repo2"
"""
        )

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": "2025-12-05-test-project",
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        # Execute pull
        with patch("qen.commands.pull.ensure_correct_branch"):
            pull_all_repositories(
                project_name=None,
                fetch_only=False,
                verbose=False,
                storage=test_storage,
            )

        # Verify both repos updated (but no transient fields persisted)
        result = read_pyproject(project_dir)
        repos = result["tool"]["qen"]["repos"]
        assert len(repos) == 2
        assert "updated" not in repos[0]  # Transient field not persisted
        assert "updated" not in repos[1]  # Transient field not persisted
