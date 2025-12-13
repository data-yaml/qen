"""Tests for git status utilities.

Tests for RepoStatus, SyncStatus, and status detection functions.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from qen.git_utils import (
    GitError,
    NotAGitRepoError,
    RepoStatus,
    SyncStatus,
    get_repo_status,
    get_sync_status,
    git_fetch,
)


class TestSyncStatusCreation:
    """Test SyncStatus creation and initialization."""

    def test_sync_status_with_defaults(self) -> None:
        """Test creating SyncStatus with default values."""
        sync = SyncStatus(has_upstream=True)

        assert sync.has_upstream
        assert sync.ahead == 0
        assert sync.behind == 0

    def test_sync_status_explicit_values(self) -> None:
        """Test creating SyncStatus with explicit values."""
        sync = SyncStatus(has_upstream=True, ahead=5, behind=3)

        assert sync.has_upstream
        assert sync.ahead == 5
        assert sync.behind == 3

    def test_sync_status_no_upstream(self) -> None:
        """Test creating SyncStatus with no upstream."""
        sync = SyncStatus(has_upstream=False)

        assert not sync.has_upstream
        assert sync.ahead == 0
        assert sync.behind == 0


class TestRepoStatusCreation:
    """Test RepoStatus creation and initialization."""

    def test_repo_status_not_exists(self) -> None:
        """Test creating RepoStatus for non-existent repository."""
        status = RepoStatus(exists=False)

        assert not status.exists
        assert status.branch is None
        assert status.modified == []
        assert status.staged == []
        assert status.untracked == []
        assert status.sync is None

    def test_repo_status_with_lists(self) -> None:
        """Test creating RepoStatus with explicit file lists."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=["file1.py"],
            staged=["file2.py"],
            untracked=["temp.txt"],
        )

        assert status.exists
        assert status.branch == "main"
        assert status.modified == ["file1.py"]
        assert status.staged == ["file2.py"]
        assert status.untracked == ["temp.txt"]

    def test_repo_status_with_sync(self) -> None:
        """Test creating RepoStatus with sync information."""
        sync = SyncStatus(has_upstream=True, ahead=1, behind=0)
        status = RepoStatus(exists=True, branch="main", sync=sync)

        assert status.sync is not None
        assert status.sync.ahead == 1


class TestGetSyncStatus:
    """Test get_sync_status function."""

    @patch("qen.git_utils.is_git_repo")
    def test_get_sync_status_not_git_repo(self, mock_is_git: Mock) -> None:
        """Test get_sync_status raises error for non-git directory."""
        mock_is_git.return_value = False

        with pytest.raises(NotAGitRepoError):
            get_sync_status(Path("/tmp/test"), fetch=False)

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_get_sync_status_no_upstream(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test get_sync_status when no upstream is configured."""
        mock_is_git.return_value = True
        mock_run_git.side_effect = GitError("No upstream branch")

        sync = get_sync_status(Path("/tmp/test"), fetch=False)

        assert not sync.has_upstream
        assert sync.ahead == 0
        assert sync.behind == 0

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_get_sync_status_up_to_date(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test get_sync_status when up-to-date with upstream."""
        mock_is_git.return_value = True
        mock_run_git.side_effect = [
            "origin/main",  # upstream branch
            "0\t0",  # ahead behind counts
        ]

        sync = get_sync_status(Path("/tmp/test"), fetch=False)

        assert sync.has_upstream
        assert sync.ahead == 0
        assert sync.behind == 0
        assert sync.is_up_to_date()

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_get_sync_status_ahead(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test get_sync_status when ahead of upstream."""
        mock_is_git.return_value = True
        mock_run_git.side_effect = [
            "origin/main",  # upstream branch
            "3\t0",  # ahead behind counts
        ]

        sync = get_sync_status(Path("/tmp/test"), fetch=False)

        assert sync.has_upstream
        assert sync.ahead == 3
        assert sync.behind == 0
        assert not sync.is_up_to_date()

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_get_sync_status_with_fetch(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test get_sync_status with fetch enabled."""
        mock_is_git.return_value = True
        mock_run_git.side_effect = [
            "",  # fetch result
            "origin/main",  # upstream branch
            "0\t2",  # ahead behind counts
        ]

        sync = get_sync_status(Path("/tmp/test"), fetch=True)

        assert sync.has_upstream
        assert sync.ahead == 0
        assert sync.behind == 2

        # Verify fetch was called
        assert mock_run_git.call_count == 3
        first_call = mock_run_git.call_args_list[0]
        assert first_call[0][0] == ["fetch"]


class TestGetRepoStatus:
    """Test get_repo_status function."""

    def test_get_repo_status_not_exists(self, tmp_path: Path) -> None:
        """Test get_repo_status for non-existent directory."""
        repo_path = tmp_path / "nonexistent"

        status = get_repo_status(repo_path, fetch=False)

        assert not status.exists
        assert status.branch is None

    @patch("qen.git_utils.is_git_repo")
    def test_get_repo_status_not_git_repo(self, mock_is_git: Mock, tmp_path: Path) -> None:
        """Test get_repo_status for non-git directory."""
        repo_path = tmp_path / "not-git"
        repo_path.mkdir()

        mock_is_git.return_value = False

        status = get_repo_status(repo_path, fetch=False)

        assert not status.exists

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_get_repo_status_clean(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test get_repo_status for clean repository."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_run_git.return_value = ""  # empty status
        mock_get_sync.return_value = SyncStatus(has_upstream=True, ahead=0, behind=0)

        status = get_repo_status(repo_path, fetch=False)

        assert status.exists
        assert status.branch == "main"
        assert status.is_clean()
        assert len(status.modified) == 0
        assert len(status.staged) == 0
        assert len(status.untracked) == 0

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_get_repo_status_with_changes(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test get_repo_status with various file changes."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "develop"

        # Simulate git status --porcelain output
        mock_run_git.return_value = """ M file1.py
M  file2.py
A  file3.py
 D file4.py
?? temp.txt
"""
        mock_get_sync.return_value = SyncStatus(has_upstream=False)

        status = get_repo_status(repo_path, fetch=False)

        assert status.exists
        assert status.branch == "develop"
        assert not status.is_clean()

        # Check parsed files
        assert "file1.py" in status.modified
        assert "file4.py" in status.modified
        assert "file2.py" in status.staged
        assert "file3.py" in status.staged
        assert "temp.txt" in status.untracked

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_get_repo_status_with_fetch(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test get_repo_status with fetch enabled."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_run_git.return_value = ""
        mock_get_sync.return_value = SyncStatus(has_upstream=True, ahead=0, behind=0)

        status = get_repo_status(repo_path, fetch=True)

        assert status.exists
        # Verify get_sync_status was called with fetch=True
        mock_get_sync.assert_called_once_with(repo_path, fetch=True)


class TestGitFetch:
    """Test git_fetch function."""

    @patch("qen.git_utils.is_git_repo")
    def test_git_fetch_not_git_repo(self, mock_is_git: Mock) -> None:
        """Test git_fetch raises error for non-git directory."""
        mock_is_git.return_value = False

        with pytest.raises(NotAGitRepoError):
            git_fetch(Path("/tmp/test"))

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_git_fetch_success(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test git_fetch successful execution."""
        mock_is_git.return_value = True
        mock_run_git.return_value = ""

        git_fetch(Path("/tmp/test"))

        mock_run_git.assert_called_once_with(["fetch"], cwd=Path("/tmp/test"))

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.run_git_command")
    def test_git_fetch_error(self, mock_run_git: Mock, mock_is_git: Mock) -> None:
        """Test git_fetch handles errors."""
        mock_is_git.return_value = True
        mock_run_git.side_effect = GitError("Network error")

        with pytest.raises(GitError):
            git_fetch(Path("/tmp/test"))


class TestStatusPorcelainParsing:
    """Test parsing of git status --porcelain output."""

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_parse_modified_unstaged(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test parsing modified unstaged files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_run_git.return_value = " M file.py"
        mock_get_sync.return_value = SyncStatus(has_upstream=False)

        status = get_repo_status(repo_path, fetch=False)

        assert "file.py" in status.modified
        assert len(status.staged) == 0
        assert len(status.untracked) == 0

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_parse_staged_files(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test parsing staged files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_run_git.return_value = "M  file.py"
        mock_get_sync.return_value = SyncStatus(has_upstream=False)

        status = get_repo_status(repo_path, fetch=False)

        assert "file.py" in status.staged
        assert len(status.modified) == 0
        assert len(status.untracked) == 0

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_parse_untracked_files(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test parsing untracked files."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_run_git.return_value = "?? temp.txt"
        mock_get_sync.return_value = SyncStatus(has_upstream=False)

        status = get_repo_status(repo_path, fetch=False)

        assert "temp.txt" in status.untracked
        assert len(status.modified) == 0
        assert len(status.staged) == 0

    @patch("qen.git_utils.is_git_repo")
    @patch("qen.git_utils.get_current_branch")
    @patch("qen.git_utils.run_git_command")
    @patch("qen.git_utils.get_sync_status")
    def test_parse_staged_and_modified(
        self,
        mock_get_sync: Mock,
        mock_run_git: Mock,
        mock_get_branch: Mock,
        mock_is_git: Mock,
        tmp_path: Path,
    ) -> None:
        """Test parsing files that are both staged and modified."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        # MM means staged and also modified
        mock_run_git.return_value = "MM file.py"
        mock_get_sync.return_value = SyncStatus(has_upstream=False)

        status = get_repo_status(repo_path, fetch=False)

        assert "file.py" in status.staged
        assert "file.py" in status.modified
