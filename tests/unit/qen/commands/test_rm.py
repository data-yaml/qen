"""Tests for qen rm command.

Tests removal of repositories from a qen project including:
- Repository identifier parsing (index, URL, org/repo, name)
- Safety checks (unpushed commits, uncommitted changes, unmerged PRs)
- User confirmation flow
- Repository removal from config and filesystem
- Workspace file regeneration
- Error handling for various failure modes
"""

from pathlib import Path

import click
import pytest

from qen.commands.rm import (
    RepoToRemove,
    SafetyCheck,
    check_repo_safety,
    confirm_removal,
    parse_repo_identifiers,
    remove_repository,
    rm,
    update_workspace_after_removal,
)
from qen.git_utils import RepoStatus, SyncStatus
from qen.pyproject_utils import PyProjectUpdateError
from tests.unit.helpers.qenvy_test import QenvyTest

# ==============================================================================
# Test RepoToRemove Dataclass
# ==============================================================================


class TestRepoToRemove:
    """Test RepoToRemove dataclass."""

    def test_repo_to_remove_creation(self) -> None:
        """Test creating a RepoToRemove instance."""
        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={"url": "https://github.com/org/repo", "branch": "main"},
        )

        assert repo.index == 1
        assert repo.url == "https://github.com/org/repo"
        assert repo.branch == "main"
        assert repo.path == "repos/repo"
        assert isinstance(repo.repo_entry, dict)


# ==============================================================================
# Test SafetyCheck Dataclass
# ==============================================================================


class TestSafetyCheck:
    """Test SafetyCheck dataclass and methods."""

    def test_safety_check_is_safe_when_clean(self) -> None:
        """Test is_safe() returns True when no issues detected."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_unpushed=False,
            has_uncommitted=False,
            has_unmerged_pr=False,
        )

        assert check.is_safe() is True

    def test_safety_check_is_safe_with_unpushed(self) -> None:
        """Test is_safe() returns False when unpushed commits exist."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_unpushed=True,
            unpushed_count=3,
        )

        assert check.is_safe() is False

    def test_safety_check_is_safe_with_uncommitted(self) -> None:
        """Test is_safe() returns False when uncommitted changes exist."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_uncommitted=True,
            uncommitted_files=["file1.py", "file2.py"],
        )

        assert check.is_safe() is False

    def test_safety_check_is_safe_with_unmerged_pr(self) -> None:
        """Test is_safe() returns False when unmerged PR exists."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="feature",
            has_unmerged_pr=True,
            pr_number=123,
            pr_status="open",
        )

        assert check.is_safe() is False

    def test_safety_check_warning_message_unpushed_single(self) -> None:
        """Test warning_message() for single unpushed commit."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_unpushed=True,
            unpushed_count=1,
        )

        message = check.warning_message()
        assert "1 unpushed commit" in message

    def test_safety_check_warning_message_unpushed_multiple(self) -> None:
        """Test warning_message() for multiple unpushed commits."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_unpushed=True,
            unpushed_count=5,
        )

        message = check.warning_message()
        assert "5 unpushed commits" in message

    def test_safety_check_warning_message_uncommitted_single(self) -> None:
        """Test warning_message() for single uncommitted file."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_uncommitted=True,
            uncommitted_files=["file1.py"],
        )

        message = check.warning_message()
        assert "1 uncommitted file" in message

    def test_safety_check_warning_message_uncommitted_multiple(self) -> None:
        """Test warning_message() for multiple uncommitted files."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="main",
            has_uncommitted=True,
            uncommitted_files=["file1.py", "file2.py", "file3.py"],
        )

        message = check.warning_message()
        assert "3 uncommitted files" in message

    def test_safety_check_warning_message_unmerged_pr(self) -> None:
        """Test warning_message() for unmerged PR."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="feature",
            has_unmerged_pr=True,
            pr_number=456,
            pr_status="open",
        )

        message = check.warning_message()
        assert "unmerged PR #456 (open)" in message

    def test_safety_check_warning_message_combined(self) -> None:
        """Test warning_message() with multiple issues."""
        check = SafetyCheck(
            repo_url="https://github.com/org/repo",
            repo_branch="feature",
            has_unpushed=True,
            unpushed_count=2,
            has_uncommitted=True,
            uncommitted_files=["file1.py"],
            has_unmerged_pr=True,
            pr_number=789,
            pr_status="draft",
        )

        message = check.warning_message()
        assert "2 unpushed commits" in message
        assert "1 uncommitted file" in message
        assert "unmerged PR #789 (draft)" in message


# ==============================================================================
# Test parse_repo_identifiers Function
# ==============================================================================


class TestParseRepoIdentifiers:
    """Test parse_repo_identifiers function."""

    @pytest.fixture
    def project_dir_with_repos(self, tmp_path: Path) -> Path:
        """Create a project directory with pyproject.toml containing repos."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        pyproject_content = """
[tool.qen]
created = "2025-12-08T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo1"
branch = "main"
path = "repos/repo1"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo2"
branch = "feature"
path = "repos/repo2"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo2"
branch = "develop"
path = "repos/repo2-develop"

[[tool.qen.repos]]
url = "https://github.com/other/repo3"
branch = "main"
path = "repos/repo3"
"""
        (project_dir / "pyproject.toml").write_text(pyproject_content)
        return project_dir

    def test_parse_repo_identifiers_by_index(self, project_dir_with_repos: Path) -> None:
        """Test parsing repositories by 1-based index."""
        repos = parse_repo_identifiers(("1", "3"), project_dir_with_repos, "testorg")

        assert len(repos) == 2
        assert repos[0].index == 1
        assert repos[0].url == "https://github.com/testorg/repo1"
        assert repos[0].branch == "main"
        assert repos[1].index == 3
        assert repos[1].url == "https://github.com/testorg/repo2"
        assert repos[1].branch == "develop"

    def test_parse_repo_identifiers_by_url(self, project_dir_with_repos: Path) -> None:
        """Test parsing repositories by full URL."""
        repos = parse_repo_identifiers(
            ("https://github.com/testorg/repo1",), project_dir_with_repos, "testorg"
        )

        assert len(repos) == 1
        assert repos[0].url == "https://github.com/testorg/repo1"
        assert repos[0].branch == "main"
        assert repos[0].index == 1

    def test_parse_repo_identifiers_by_org_slash_repo(self, project_dir_with_repos: Path) -> None:
        """Test parsing repositories by org/repo format."""
        repos = parse_repo_identifiers(("other/repo3",), project_dir_with_repos, "testorg")

        assert len(repos) == 1
        assert repos[0].url == "https://github.com/other/repo3"
        assert repos[0].branch == "main"

    def test_parse_repo_identifiers_by_name_with_org(self, project_dir_with_repos: Path) -> None:
        """Test parsing repositories by name only using org from config."""
        repos = parse_repo_identifiers(("repo1",), project_dir_with_repos, "testorg")

        assert len(repos) == 1
        assert repos[0].url == "https://github.com/testorg/repo1"
        assert repos[0].branch == "main"

    def test_parse_repo_identifiers_by_name_no_org(self, project_dir_with_repos: Path) -> None:
        """Test parsing by name without org in config raises error."""
        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(("repo1",), project_dir_with_repos, None)

        assert "Cannot parse identifier" in str(exc_info.value)

    def test_parse_repo_identifiers_index_out_of_range(self, project_dir_with_repos: Path) -> None:
        """Test parsing with index out of range raises error."""
        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(("99",), project_dir_with_repos, "testorg")

        assert "Index 99 out of range" in str(exc_info.value)
        assert "Valid indices: 1-4" in str(exc_info.value)

    def test_parse_repo_identifiers_index_zero(self, project_dir_with_repos: Path) -> None:
        """Test parsing with index 0 raises error."""
        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(("0",), project_dir_with_repos, "testorg")

        assert "Index 0 out of range" in str(exc_info.value)

    def test_parse_repo_identifiers_not_found(self, project_dir_with_repos: Path) -> None:
        """Test parsing with non-existent repository raises error."""
        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(
                ("https://github.com/missing/repo",), project_dir_with_repos, "testorg"
            )

        assert "Repository not found" in str(exc_info.value)

    def test_parse_repo_identifiers_multiple_branches(self, project_dir_with_repos: Path) -> None:
        """Test parsing URL with multiple branches raises helpful error."""
        # repo2 has both "feature" and "develop" branches
        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(("testorg/repo2",), project_dir_with_repos, "testorg")

        error_msg = str(exc_info.value)
        assert "Multiple branches found" in error_msg
        assert "feature" in error_msg
        assert "develop" in error_msg
        assert "Specify index or URL with branch" in error_msg

    def test_parse_repo_identifiers_no_repos_in_project(self, tmp_path: Path) -> None:
        """Test parsing when project has no repositories."""
        project_dir = tmp_path / "empty_project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            """
[tool.qen]
created = "2025-12-08T10:00:00Z"
"""
        )

        with pytest.raises(click.ClickException) as exc_info:
            parse_repo_identifiers(("1",), project_dir, "testorg")

        assert "No repositories in project" in str(exc_info.value)

    def test_parse_repo_identifiers_multiple_repos(self, project_dir_with_repos: Path) -> None:
        """Test parsing multiple repositories at once."""
        repos = parse_repo_identifiers(("1", "4"), project_dir_with_repos, "testorg")

        # Changed from expecting testorg/repo2 to just repo1 and repo3
        assert len(repos) == 2
        assert repos[0].index == 1
        assert repos[0].url == "https://github.com/testorg/repo1"
        assert repos[1].index == 4
        assert repos[1].url == "https://github.com/other/repo3"

    def test_parse_repo_identifiers_strips_whitespace(self, project_dir_with_repos: Path) -> None:
        """Test that identifiers are stripped of whitespace."""
        repos = parse_repo_identifiers(
            ("  1  ", " testorg/repo1 "), project_dir_with_repos, "testorg"
        )

        assert len(repos) == 2
        assert repos[0].index == 1
        assert repos[1].index == 1


# ==============================================================================
# Test check_repo_safety Function
# ==============================================================================


class TestCheckRepoSafety:
    """Test check_repo_safety function."""

    def test_check_repo_safety_nonexistent_repo(self, tmp_path: Path) -> None:
        """Test safety check on nonexistent repository returns safe."""
        repo_path = tmp_path / "nonexistent"
        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is True
        assert check.has_unpushed is False
        assert check.has_uncommitted is False
        assert check.has_unmerged_pr is False

    def test_check_repo_safety_clean_repo(self, tmp_path: Path, mocker) -> None:
        """Test safety check on clean repository."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        # Mock git operations to return clean status
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=[],
            untracked=[],
        )

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is True
        assert check.has_unpushed is False
        assert check.has_uncommitted is False

    def test_check_repo_safety_unpushed_commits(self, tmp_path: Path, mocker) -> None:
        """Test safety check detects unpushed commits."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        # Mock git operations to show unpushed commits
        mock_sync = SyncStatus(has_upstream=True, ahead=3, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is False
        assert check.has_unpushed is True
        assert check.unpushed_count == 3

    def test_check_repo_safety_uncommitted_changes(self, tmp_path: Path, mocker) -> None:
        """Test safety check detects uncommitted changes."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        # Mock git operations to show uncommitted changes
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(
            exists=True,
            branch="main",
            modified=["file1.py", "file2.py"],
            staged=["file3.py"],
            untracked=["new_file.py"],
        )

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is False
        assert check.has_uncommitted is True
        assert len(check.uncommitted_files) == 4
        assert "file1.py" in check.uncommitted_files
        assert "file3.py" in check.uncommitted_files
        assert "new_file.py" in check.uncommitted_files

    def test_check_repo_safety_unmerged_pr(self, tmp_path: Path, mocker) -> None:
        """Test safety check detects unmerged PR."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "feature",
            "pr": 123,
            "pr_status": "open",
        }

        # Mock git operations to return clean status
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="feature")

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is False
        assert check.has_unmerged_pr is True
        assert check.pr_number == 123
        assert check.pr_status == "open"

    def test_check_repo_safety_merged_pr_is_safe(self, tmp_path: Path, mocker) -> None:
        """Test safety check considers merged PR as safe."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "feature",
            "pr": 123,
            "pr_status": "merged",
        }

        # Mock git operations to return clean status
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="feature")

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is True
        assert check.has_unmerged_pr is False

    def test_check_repo_safety_no_upstream(self, tmp_path: Path, mocker) -> None:
        """Test safety check with no upstream branch."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        # Mock git operations - no upstream
        mock_sync = SyncStatus(has_upstream=False, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")

        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is True
        assert check.has_unpushed is False

    def test_check_repo_safety_git_error_graceful(self, tmp_path: Path, mocker) -> None:
        """Test safety check handles git errors gracefully."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        repo_entry = {
            "url": "https://github.com/org/repo",
            "branch": "main",
        }

        # Mock git operations to raise exceptions
        mocker.patch("qen.git_utils.get_sync_status", side_effect=Exception("Git error"))
        mocker.patch("qen.git_utils.get_repo_status", side_effect=Exception("Git error"))

        # Should not raise, but return safe (conservative)
        check = check_repo_safety(repo_path, repo_entry)

        assert check.is_safe() is True


# ==============================================================================
# Test confirm_removal Function
# ==============================================================================


class TestConfirmRemoval:
    """Test confirm_removal function."""

    def test_confirm_removal_with_yes_flag(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal auto-confirms with --yes flag."""
        _ = mocker.patch("qen.commands.rm.click.echo")
        mock_confirm = mocker.patch("qen.commands.rm.click.confirm")

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {}

        result = confirm_removal(repos, safety_checks, tmp_path, False, True, False)

        assert result is True
        mock_confirm.assert_not_called()

    def test_confirm_removal_user_confirms(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal when user confirms."""
        mocker.patch("qen.commands.rm.click.echo")
        mock_confirm = mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {
            ("https://github.com/org/repo", "main"): SafetyCheck(
                repo_url="https://github.com/org/repo", repo_branch="main"
            )
        }

        result = confirm_removal(repos, safety_checks, tmp_path, False, False, False)

        assert result is True
        mock_confirm.assert_called_once()

    def test_confirm_removal_user_declines(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal when user declines."""
        mocker.patch("qen.commands.rm.click.echo")
        mock_confirm = mocker.patch("qen.commands.rm.click.confirm", return_value=False)
        _ = mock_confirm  # Satisfy linter

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {}

        result = confirm_removal(repos, safety_checks, tmp_path, False, False, False)

        assert result is False

    def test_confirm_removal_shows_warnings(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal displays safety warnings."""
        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {
            ("https://github.com/org/repo", "main"): SafetyCheck(
                repo_url="https://github.com/org/repo",
                repo_branch="main",
                has_unpushed=True,
                unpushed_count=2,
            )
        }

        confirm_removal(repos, safety_checks, tmp_path, False, False, False)

        # Verify warning was displayed
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "2 unpushed commits" in output
        assert "uncommitted/unpushed work that will be lost" in output

    def test_confirm_removal_force_skips_warnings(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal with --force skips safety warnings."""
        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {}

        confirm_removal(repos, safety_checks, tmp_path, True, False, False)

        # Verify force message was displayed
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "skipped safety checks due to --force" in output

    def test_confirm_removal_verbose_shows_files(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal verbose mode shows file details."""
        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {
            ("https://github.com/org/repo", "main"): SafetyCheck(
                repo_url="https://github.com/org/repo",
                repo_branch="main",
                has_uncommitted=True,
                uncommitted_files=["file1.py", "file2.py"],
            )
        }

        confirm_removal(repos, safety_checks, tmp_path, False, False, True)

        # Verify file list was displayed
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "Uncommitted files:" in output
        assert "file1.py" in output
        assert "file2.py" in output

    def test_confirm_removal_multiple_repos(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal with multiple repositories."""
        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo1",
                branch="main",
                path="repos/repo1",
                repo_entry={},
            ),
            RepoToRemove(
                index=2,
                url="https://github.com/org/repo2",
                branch="feature",
                path="repos/repo2",
                repo_entry={},
            ),
        ]
        safety_checks = {}

        confirm_removal(repos, safety_checks, tmp_path, False, False, False)

        # Verify plural wording
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "2 repositories" in output
        # Changed check to be more flexible
        assert "repositories" in output.lower()

    def test_confirm_removal_truncates_long_file_list(self, tmp_path: Path, mocker) -> None:
        """Test confirm_removal truncates file lists longer than 5."""
        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        # Create list of 10 files
        many_files = [f"file{i}.py" for i in range(10)]

        repos = [
            RepoToRemove(
                index=1,
                url="https://github.com/org/repo",
                branch="main",
                path="repos/repo",
                repo_entry={},
            )
        ]
        safety_checks = {
            ("https://github.com/org/repo", "main"): SafetyCheck(
                repo_url="https://github.com/org/repo",
                repo_branch="main",
                has_uncommitted=True,
                uncommitted_files=many_files,
            )
        }

        confirm_removal(repos, safety_checks, tmp_path, False, False, True)

        # Verify truncation message
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "... and 5 more" in output


# ==============================================================================
# Test remove_repository Function
# ==============================================================================


class TestRemoveRepository:
    """Test remove_repository function."""

    def test_remove_repository_success(self, tmp_path: Path, mocker) -> None:
        """Test successful repository removal."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo_path = project_dir / "repos" / "repo"
        repo_path.mkdir(parents=True)

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        # Mock remove_repo_from_pyproject
        mock_remove = mocker.patch(
            "qen.pyproject_utils.remove_repo_from_pyproject", return_value="repos/repo"
        )

        success, error = remove_repository(repo, project_dir, verbose=False)

        assert success is True
        assert error is None
        assert not repo_path.exists()
        mock_remove.assert_called_once_with(project_dir, "https://github.com/org/repo", "main")

    def test_remove_repository_config_failure(self, tmp_path: Path, mocker) -> None:
        """Test repository removal when config update fails."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        # Mock remove_repo_from_pyproject to raise error
        _ = mocker.patch(
            "qen.pyproject_utils.remove_repo_from_pyproject",
            side_effect=PyProjectUpdateError("Failed to update"),
        )

        success, error = remove_repository(repo, project_dir, verbose=False)

        assert success is False
        assert "Failed to update config" in error

    def test_remove_repository_directory_deletion_error(self, tmp_path: Path, mocker) -> None:
        """Test repository removal when directory deletion fails."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo_path = project_dir / "repos" / "repo"
        repo_path.mkdir(parents=True)

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        # Mock remove_repo_from_pyproject
        mocker.patch("qen.pyproject_utils.remove_repo_from_pyproject", return_value="repos/repo")

        # Mock shutil.rmtree to raise error
        mocker.patch("qen.commands.rm.shutil.rmtree", side_effect=OSError("Permission denied"))

        success, error = remove_repository(repo, project_dir, verbose=False)

        assert success is True  # Config removed successfully
        assert error is not None
        assert "Could not delete directory" in error
        assert "Permission denied" in error

    def test_remove_repository_already_deleted(self, tmp_path: Path, mocker) -> None:
        """Test repository removal when directory doesn't exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        # Mock remove_repo_from_pyproject
        mocker.patch("qen.pyproject_utils.remove_repo_from_pyproject", return_value="repos/repo")

        success, error = remove_repository(repo, project_dir, verbose=False)

        assert success is True
        assert error is None

    def test_remove_repository_verbose(self, tmp_path: Path, mocker) -> None:
        """Test repository removal with verbose output."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo_path = project_dir / "repos" / "repo"
        repo_path.mkdir(parents=True)

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.pyproject_utils.remove_repo_from_pyproject", return_value="repos/repo")

        remove_repository(repo, project_dir, verbose=True)

        # Verify verbose messages
        assert mock_echo.call_count >= 2
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "Removed from config" in output
        assert "Removed directory" in output

    def test_remove_repository_not_in_config(self, tmp_path: Path, mocker) -> None:
        """Test repository removal when repo not in config."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        repo = RepoToRemove(
            index=1,
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
            repo_entry={},
        )

        # Mock remove_repo_from_pyproject to return None (not found)
        mocker.patch("qen.pyproject_utils.remove_repo_from_pyproject", return_value=None)

        success, error = remove_repository(repo, project_dir, verbose=False)

        # Should still succeed (already removed)
        assert success is True
        assert error is None


# ==============================================================================
# Test update_workspace_after_removal Function
# ==============================================================================


class TestUpdateWorkspaceAfterRemoval:
    """Test update_workspace_after_removal function."""

    def test_update_workspace_after_removal_success(self, tmp_path: Path, mocker) -> None:
        """Test successful workspace regeneration."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create pyproject.toml
        (project_dir / "pyproject.toml").write_text(
            """
[tool.qen]
created = "2025-12-08T10:00:00Z"
repos = []
"""
        )

        # Mock create_workspace_files
        mock_create = mocker.patch(
            "qen.commands.workspace.create_workspace_files",
            return_value={"vscode": project_dir / "workspace.code-workspace"},
        )
        mocker.patch(
            "qen.pyproject_utils.read_pyproject", return_value={"tool": {"qen": {"repos": []}}}
        )

        update_workspace_after_removal(project_dir, "test-project", False, False)

        mock_create.assert_called_once()

    def test_update_workspace_after_removal_with_no_workspace_flag(
        self, tmp_path: Path, mocker
    ) -> None:
        """Test workspace regeneration skipped with --no-workspace."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        mock_create = mocker.patch("qen.commands.workspace.create_workspace_files")

        update_workspace_after_removal(project_dir, "test-project", True, False)

        mock_create.assert_not_called()

    def test_update_workspace_after_removal_verbose(self, tmp_path: Path, mocker) -> None:
        """Test workspace regeneration with verbose output."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mock_create = mocker.patch(
            "qen.commands.workspace.create_workspace_files",
            return_value={"vscode": project_dir / "workspace.code-workspace"},
        )
        _ = mock_create  # Satisfy linter
        mocker.patch(
            "qen.pyproject_utils.read_pyproject", return_value={"tool": {"qen": {"repos": []}}}
        )

        update_workspace_after_removal(project_dir, "test-project", False, True)

        # Verify verbose messages
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "Regenerating workspace files" in output
        assert "Updated:" in output

    def test_update_workspace_after_removal_handles_errors(self, tmp_path: Path, mocker) -> None:
        """Test workspace regeneration handles errors gracefully."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch(
            "qen.pyproject_utils.read_pyproject",
            side_effect=Exception("Failed to read config"),
        )

        # Should not raise, just warn
        update_workspace_after_removal(project_dir, "test-project", False, False)

        # Verify warning was displayed
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "Warning:" in output
        assert "Could not regenerate workspace files" in output


# ==============================================================================
# Test rm Command
# ==============================================================================


class TestRmCommand:
    """Test rm command CLI integration."""

    @pytest.fixture
    def mock_config_and_project(self, tmp_path: Path, test_storage: QenvyTest) -> tuple[Path, Path]:
        """Setup mock configuration and project."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        project_dir = meta_path / "proj" / "test-project"
        project_dir.mkdir(parents=True)

        # Create pyproject.toml
        (project_dir / "pyproject.toml").write_text(
            """
[tool.qen]
created = "2025-12-08T10:00:00Z"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo1"
branch = "main"
path = "repos/repo1"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo2"
branch = "feature"
path = "repos/repo2"
"""
        )

        # Create repo directories
        (project_dir / "repos" / "repo1").mkdir(parents=True)
        (project_dir / "repos" / "repo2").mkdir(parents=True)

        # Setup config
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_path),
                "github_org": "testorg",
                "current_project": "test-project",
                "org": "testorg",
            },
        )

        test_storage.write_profile(
            "test-project",
            {
                "name": "test-project",
                "branch": "251208-test-project",
                "folder": "proj/test-project",
                "repo": str(meta_path),
                "created": "2025-12-08T10:00:00Z",
            },
        )

        return meta_path, project_dir

    def test_rm_command_success(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test successful rm command execution."""
        meta_path, project_dir = mock_config_and_project

        # Mock ensure_initialized
        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        _ = mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations for safety checks
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")
        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        # Mock confirmation
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)

        # Mock workspace update
        mocker.patch("qen.commands.rm.update_workspace_after_removal")

        # Create Click context
        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        # Execute command
        _ = ctx.invoke(rm, repos=("1",), force=False, yes=True, no_workspace=False, verbose=False)

        # Verify repo was removed
        updated_content = (project_dir / "pyproject.toml").read_text()
        assert "repo1" not in updated_content
        assert "repo2" in updated_content

    def test_rm_command_no_active_project(
        self, tmp_path: Path, test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command fails when no active project."""
        # Setup config with no current project
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(tmp_path / "meta"),
                "github_org": "testorg",
                "current_project": None,
            },
        )

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="main")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        with pytest.raises(click.ClickException) as exc_info:
            ctx.invoke(rm, repos=("1",), force=False, yes=False, no_workspace=False, verbose=False)

        assert "No active project" in str(exc_info.value)

    def test_rm_command_user_aborts(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command when user aborts confirmation."""
        meta_path, project_dir = mock_config_and_project

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations for safety checks
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")
        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        # User declines confirmation
        mocker.patch("qen.commands.rm.click.confirm", return_value=False)

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        with pytest.raises(click.Abort):
            ctx.invoke(rm, repos=("1",), force=False, yes=False, no_workspace=False, verbose=False)

        # Verify repo was NOT removed
        updated_content = (project_dir / "pyproject.toml").read_text()
        assert "repo1" in updated_content

    def test_rm_command_with_force_flag(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command with --force flag skips safety checks."""
        meta_path, project_dir = mock_config_and_project

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations - should NOT be called with --force
        mock_sync = mocker.patch("qen.git_utils.get_sync_status")
        mock_status = mocker.patch("qen.git_utils.get_repo_status")

        mocker.patch("qen.commands.rm.click.confirm", return_value=True)
        mocker.patch("qen.commands.rm.update_workspace_after_removal")

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        ctx.invoke(rm, repos=("1",), force=True, yes=True, no_workspace=False, verbose=False)

        # Verify safety checks were NOT called
        mock_sync.assert_not_called()
        mock_status.assert_not_called()

    def test_rm_command_multiple_repos(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command removing multiple repositories."""
        meta_path, project_dir = mock_config_and_project

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations for safety checks
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")
        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        mocker.patch("qen.commands.rm.click.confirm", return_value=True)
        mocker.patch("qen.commands.rm.update_workspace_after_removal")

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        ctx.invoke(rm, repos=("1", "2"), force=False, yes=True, no_workspace=False, verbose=False)

        # Verify both repos were removed
        updated_content = (project_dir / "pyproject.toml").read_text()
        assert "repo1" not in updated_content
        assert "repo2" not in updated_content

    def test_rm_command_config_overrides(
        self, tmp_path: Path, test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command respects context config overrides."""
        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mock_ensure = mocker.patch("qen.init_utils.ensure_initialized", return_value=config)
        _ = mock_ensure  # Satisfy ruff linter

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251209-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")
        # Mock click.confirm for any prompts
        mocker.patch("click.confirm", return_value=True)

        # Setup minimal config
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(tmp_path / "meta"),
                "org": "testorg",
                "current_project": "test-project",
            },
        )

        test_storage.write_profile(
            "test-project",
            {
                "name": "test-project",
                "branch": "251209-test-project",
                "folder": "proj/test-project",
            },
        )

        project_dir = tmp_path / "meta" / "proj" / "test-project"
        project_dir.mkdir(parents=True)
        (project_dir / "pyproject.toml").write_text(
            """
[tool.qen]
created = "2025-12-08T10:00:00Z"
repos = []
"""
        )

        ctx = click.Context(rm)
        ctx.obj = {
            "config_overrides": {
                "config_dir": tmp_path / "custom_config",
                "meta_path": tmp_path / "custom_meta",
                "current_project": "custom-project",
            }
        }

        try:
            ctx.invoke(rm, repos=(), force=False, yes=False, no_workspace=False, verbose=False)
        except (click.ClickException, click.Abort):
            pass

        # Verify ensure_initialized received overrides
        call_kwargs = mock_ensure.call_args.kwargs
        assert call_kwargs["config_dir"] == tmp_path / "custom_config"
        assert call_kwargs["meta_path_override"] == tmp_path / "custom_meta"
        assert call_kwargs["current_project_override"] == "custom-project"

    def test_rm_command_verbose_output(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command verbose output."""
        meta_path, project_dir = mock_config_and_project

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations for safety checks
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")
        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        mock_echo = mocker.patch("qen.commands.rm.click.echo")
        mocker.patch("qen.commands.rm.click.confirm", return_value=True)
        mocker.patch("qen.commands.rm.update_workspace_after_removal")

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        ctx.invoke(rm, repos=("1",), force=False, yes=True, no_workspace=False, verbose=True)

        # Verify verbose messages were displayed
        assert mock_echo.call_count > 0
        call_args_list = [str(call[0]) for call in mock_echo.call_args_list]
        output = " ".join(call_args_list)
        assert "Removed from config" in output or "Removed directory" in output

    def test_rm_command_partial_failure(
        self, mock_config_and_project: tuple[Path, Path], test_storage: QenvyTest, mocker
    ) -> None:
        """Test rm command handles partial failures gracefully."""
        meta_path, project_dir = mock_config_and_project

        from qen.config import QenConfig

        config = QenConfig(storage=test_storage)
        mocker.patch("qen.init_utils.ensure_initialized", return_value=config)

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="251208-test-project")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        # Mock git operations for safety checks
        mock_sync = SyncStatus(has_upstream=True, ahead=0, behind=0)
        mock_status = RepoStatus(exists=True, branch="main")
        mocker.patch("qen.git_utils.get_sync_status", return_value=mock_sync)
        mocker.patch("qen.git_utils.get_repo_status", return_value=mock_status)

        mocker.patch("qen.commands.rm.click.confirm", return_value=True)
        mocker.patch("qen.commands.rm.update_workspace_after_removal")

        # Mock remove_repo_from_pyproject to fail on second call
        call_count = {"count": 0}

        def side_effect(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 2:
                raise PyProjectUpdateError("Failed to remove")
            return "repos/repo1"

        mocker.patch("qen.pyproject_utils.remove_repo_from_pyproject", side_effect=side_effect)

        ctx = click.Context(rm)
        ctx.obj = {"config_overrides": {}}

        with pytest.raises(click.ClickException) as exc_info:
            ctx.invoke(
                rm, repos=("1", "2"), force=False, yes=True, no_workspace=False, verbose=False
            )

        assert "Some repositories could not be removed" in str(exc_info.value)
