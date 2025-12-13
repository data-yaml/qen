"""Tests for qen pr command.

Tests PR status detection, gh CLI integration, output formatting, and error handling.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from qen.commands.pr import (
    PrInfo,
    check_gh_installed,
    format_pr_info,
    get_pr_info_for_branch,
    parse_repo_owner_and_name,
    pr_status_command,
    restack_pr,
)


class TestCheckGhInstalled:
    """Test GitHub CLI detection."""

    @patch("subprocess.run")
    def test_gh_installed(self, mock_run: Mock) -> None:
        """Test detection when gh is installed."""
        mock_run.return_value = Mock(returncode=0)

        assert check_gh_installed() is True
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_gh_not_installed(self, mock_run: Mock) -> None:
        """Test detection when gh is not installed."""
        mock_run.side_effect = FileNotFoundError()

        assert check_gh_installed() is False

    @patch("subprocess.run")
    def test_gh_timeout(self, mock_run: Mock) -> None:
        """Test detection when gh command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 5)

        assert check_gh_installed() is False


class TestGetPrInfoForBranch:
    """Test PR info retrieval for individual branches."""

    @patch("qen.commands.pr.is_git_repo")
    def test_not_git_repo(self, mock_is_git: Mock, tmp_path: Path) -> None:
        """Test when directory is not a git repository."""
        mock_is_git.return_value = False

        pr_info = get_pr_info_for_branch(tmp_path, "main", "https://github.com/org/repo")

        assert pr_info.has_pr is False
        assert pr_info.error == "Not a git repository"

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_no_pr_found(self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path) -> None:
        """Test when no PR exists for the branch."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="no pull requests")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is False
        assert pr_info.branch == "feature-branch"
        assert pr_info.error is None

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_pr_found_open(self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path) -> None:
        """Test when an open PR is found."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        pr_data = {
            "number": 123,
            "title": "Add new feature",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/org/repo/pull/123",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T10:00:00Z",
            "updatedAt": "2025-01-02T15:30:00Z",
            "commits": [{"oid": "abc123"}, {"oid": "def456"}],
            "files": [{"path": "file1.py"}, {"path": "file2.py"}, {"path": "file3.py"}],
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(pr_data), stderr="")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is True
        assert pr_info.pr_number == 123
        assert pr_info.pr_title == "Add new feature"
        assert pr_info.pr_state == "open"
        assert pr_info.pr_base == "main"
        assert pr_info.pr_url == "https://github.com/org/repo/pull/123"
        assert pr_info.pr_checks == "passing"
        assert pr_info.pr_mergeable == "mergeable"
        assert pr_info.pr_author == "testuser"
        assert pr_info.pr_created_at == "2025-01-01T10:00:00Z"
        assert pr_info.pr_updated_at == "2025-01-02T15:30:00Z"
        assert pr_info.pr_commits == 2
        assert pr_info.pr_files_changed == 3

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_pr_with_failing_checks(
        self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path
    ) -> None:
        """Test PR with failing checks."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        pr_data = {
            "number": 456,
            "title": "Fix bug",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/org/repo/pull/456",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "FAILURE"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "mergeable": "CONFLICTING",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T10:00:00Z",
            "updatedAt": "2025-01-02T15:30:00Z",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(pr_data), stderr="")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "failing"
        assert pr_info.pr_mergeable == "conflicting"

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_pr_with_pending_checks(
        self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path
    ) -> None:
        """Test PR with pending checks."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        pr_data = {
            "number": 789,
            "title": "Refactor code",
            "state": "OPEN",
            "baseRefName": "develop",
            "url": "https://github.com/org/repo/pull/789",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": ""},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "anotheruser"},
            "createdAt": "2025-01-03T12:00:00Z",
            "updatedAt": "2025-01-03T14:00:00Z",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(pr_data), stderr="")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "pending"

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_pr_with_skipped_checks(
        self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path
    ) -> None:
        """Test PR with all skipped checks."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        pr_data = {
            "number": 999,
            "title": "Skip checks",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/org/repo/pull/999",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SKIPPED"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SKIPPED"},
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-04T10:00:00Z",
            "updatedAt": "2025-01-04T12:00:00Z",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(pr_data), stderr="")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "skipped"

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_pr_with_mixed_success_and_skipped(
        self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path
    ) -> None:
        """Test PR with mix of SUCCESS and SKIPPED checks (should be passing)."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        pr_data = {
            "number": 888,
            "title": "Mixed checks",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/org/repo/pull/888",
            "statusCheckRollup": [
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SKIPPED"},
                {"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"},
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-04T10:00:00Z",
            "updatedAt": "2025-01-04T12:00:00Z",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(pr_data), stderr="")

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "passing"

    @patch("qen.commands.pr.get_current_branch")
    @patch("qen.commands.pr.is_git_repo")
    def test_gh_command_timeout(
        self, mock_is_git: Mock, mock_get_branch: Mock, tmp_path: Path
    ) -> None:
        """Test when gh command times out."""
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 10)

            pr_info = get_pr_info_for_branch(
                tmp_path, "feature-branch", "https://github.com/org/repo"
            )

        assert pr_info.has_pr is False
        assert pr_info.error is not None
        assert "Failed to query PR" in pr_info.error


class TestFormatPrInfo:
    """Test PR info formatting."""

    def test_format_no_pr(self) -> None:
        """Test formatting when no PR exists."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="main",
            has_pr=False,
        )

        output = format_pr_info(pr_info)

        assert "📦 myrepo (main)" in output
        assert "No PR for this branch" in output

    def test_format_with_error(self) -> None:
        """Test formatting when error occurred."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="main",
            has_pr=False,
            error="Not a git repository",
        )

        output = format_pr_info(pr_info)

        assert "📦 myrepo (main)" in output
        assert "✗ Not a git repository" in output

    def test_format_open_pr(self) -> None:
        """Test formatting for open PR."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="feature",
            has_pr=True,
            pr_number=123,
            pr_title="Add new feature",
            pr_state="open",
            pr_base="main",
            pr_checks="passing",
            pr_mergeable="mergeable",
        )

        output = format_pr_info(pr_info)

        assert "📦 myrepo (feature)" in output
        assert "📋 PR #123: Add new feature" in output
        assert "🟢 State: open" in output
        assert "🎯 Target: main" in output
        assert "✓ Checks: passing" in output
        assert "✓ Mergeable" in output

    def test_format_merged_pr(self) -> None:
        """Test formatting for merged PR."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="feature",
            has_pr=True,
            pr_number=456,
            pr_title="Fix bug",
            pr_state="merged",
            pr_base="develop",
        )

        output = format_pr_info(pr_info)

        assert "🔵 State: merged" in output

    def test_format_failing_checks(self) -> None:
        """Test formatting for PR with failing checks."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="feature",
            has_pr=True,
            pr_number=789,
            pr_title="Refactor",
            pr_state="open",
            pr_checks="failing",
            pr_mergeable="conflicting",
        )

        output = format_pr_info(pr_info)

        assert "✗ Checks: failing" in output
        assert "✗ Has conflicts" in output

    def test_format_verbose(self) -> None:
        """Test verbose formatting."""
        pr_info = PrInfo(
            repo_path="myrepo",
            repo_url="https://github.com/org/myrepo",
            branch="feature",
            has_pr=True,
            pr_number=123,
            pr_title="Add feature",
            pr_state="open",
            pr_author="testuser",
            pr_url="https://github.com/org/myrepo/pull/123",
            pr_created_at="2025-01-01T10:00:00Z",
            pr_updated_at="2025-01-02T15:30:00Z",
        )

        output = format_pr_info(pr_info, verbose=True)

        assert "👤 Author: testuser" in output
        assert "🔗 URL: https://github.com/org/myrepo/pull/123" in output
        assert "📅 Created: 2025-01-01T10:00:00Z" in output
        assert "🔄 Updated: 2025-01-02T15:30:00Z" in output


class TestPrStatusCommand:
    """Test pr status command - removed CLI tests for removed 'qen pr status' subcommand.

    The 'qen pr status' subcommand was replaced with an interactive TUI ('qen pr').
    CLI tests that invoked the old subcommand have been removed.
    Unit tests for the underlying pr_status_command() function are preserved below.
    """

    pass


class TestPrStatusCommandFunction:
    """Test pr_status_command function directly."""

    @patch("qen.commands.pr.ensure_correct_branch")
    @patch("qen.commands.pr.ensure_initialized")
    @patch("qen.commands.pr.check_gh_installed")
    @patch("qen.commands.pr.read_pyproject")
    @patch("qen.commands.pr.get_pr_info_for_branch")
    @patch("pathlib.Path.exists")
    def test_pr_status_command_returns_pr_infos(
        self,
        mock_exists: Mock,
        mock_get_pr_info: Mock,
        mock_read_pyproject: Mock,
        mock_check_gh: Mock,
        mock_ensure: Mock,
        mock_ensure_branch: Mock,
    ) -> None:
        """Test that pr_status_command returns list of PrInfo objects."""
        mock_config = Mock()
        mock_config.read_main_config.return_value = {
            "meta_path": "/tmp/meta",
            "current_project": "test-project",
        }
        mock_config.read_project_config.return_value = {
            "folder": "proj/test",
            "repo": "/tmp/meta",
        }
        mock_ensure.return_value = mock_config

        mock_exists.return_value = True
        mock_check_gh.return_value = True

        mock_read_pyproject.return_value = {
            "tool": {
                "qen": {
                    "repos": [
                        {
                            "url": "https://github.com/org/repo1",
                            "branch": "main",
                            "path": "repos/repo1",
                        }
                    ]
                }
            }
        }

        expected_pr_info = PrInfo(
            repo_path="repo1",
            repo_url="https://github.com/org/repo1",
            branch="main",
            has_pr=True,
            pr_number=123,
            pr_title="Test PR",
            pr_state="open",
        )
        mock_get_pr_info.return_value = expected_pr_info

        result = pr_status_command()

        assert len(result) == 1
        assert result[0] == expected_pr_info

    @patch("qen.commands.pr.ensure_correct_branch")
    @patch("qen.commands.pr.ensure_initialized")
    @patch("qen.commands.pr.check_gh_installed")
    @patch("qen.commands.pr.read_pyproject")
    @patch("pathlib.Path.exists")
    def test_pr_status_repo_not_found(
        self,
        mock_exists: Mock,
        mock_read_pyproject: Mock,
        mock_check_gh: Mock,
        mock_ensure: Mock,
        mock_ensure_branch: Mock,
    ) -> None:
        """Test pr status when repository doesn't exist on disk."""
        mock_config = Mock()
        mock_config.read_main_config.return_value = {
            "meta_path": "/tmp/meta",
            "current_project": "test-project",
        }
        mock_config.read_project_config.return_value = {
            "folder": "proj/test",
            "repo": "/tmp/meta",
        }
        mock_ensure.return_value = mock_config

        # Project dir exists, but repo dir doesn't
        mock_exists.side_effect = lambda: mock_exists.call_count == 1

        mock_check_gh.return_value = True

        mock_read_pyproject.return_value = {
            "tool": {
                "qen": {
                    "repos": [
                        {
                            "url": "https://github.com/org/repo1",
                            "branch": "main",
                            "path": "repos/repo1",
                        }
                    ]
                }
            }
        }

        result = pr_status_command()

        assert len(result) == 1
        assert result[0].has_pr is False
        assert "not found on disk" in result[0].error


class TestIdentifyStacks:
    """Test stack identification logic."""

    def test_no_stacks_all_on_main(self) -> None:
        """Test when all PRs target main (no stacks)."""
        from qen.commands.pr import identify_stacks

        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-1",
                has_pr=True,
                pr_number=1,
                pr_base="main",
            ),
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature-2",
                has_pr=True,
                pr_number=2,
                pr_base="main",
            ),
        ]

        stacks = identify_stacks(pr_infos)
        assert len(stacks) == 0

    def test_simple_stack_two_prs(self) -> None:
        """Test simple stack: PR2 -> PR1 -> main."""
        from qen.commands.pr import identify_stacks

        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-1",
                has_pr=True,
                pr_number=1,
                pr_title="First PR",
                pr_base="main",
            ),
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-2",
                has_pr=True,
                pr_number=2,
                pr_title="Second PR",
                pr_base="feature-1",
            ),
        ]

        stacks = identify_stacks(pr_infos)
        assert len(stacks) == 1
        assert "feature-1" in stacks
        assert len(stacks["feature-1"]) == 2
        assert stacks["feature-1"][0].pr_number == 1
        assert stacks["feature-1"][1].pr_number == 2

    def test_multiple_stacks(self) -> None:
        """Test multiple independent stacks."""
        from qen.commands.pr import identify_stacks

        pr_infos = [
            # Stack 1: feature-1 -> feature-2
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-1",
                has_pr=True,
                pr_number=1,
                pr_base="main",
            ),
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-2",
                has_pr=True,
                pr_number=2,
                pr_base="feature-1",
            ),
            # Stack 2: feature-3 -> feature-4
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature-3",
                has_pr=True,
                pr_number=3,
                pr_base="main",
            ),
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature-4",
                has_pr=True,
                pr_number=4,
                pr_base="feature-3",
            ),
        ]

        stacks = identify_stacks(pr_infos)
        assert len(stacks) == 2
        assert "feature-1" in stacks
        assert "feature-3" in stacks
        assert len(stacks["feature-1"]) == 2
        assert len(stacks["feature-3"]) == 2

    def test_deep_stack(self) -> None:
        """Test stack with 4+ levels."""
        from qen.commands.pr import identify_stacks

        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-1",
                has_pr=True,
                pr_number=1,
                pr_base="main",
            ),
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-2",
                has_pr=True,
                pr_number=2,
                pr_base="feature-1",
            ),
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-3",
                has_pr=True,
                pr_number=3,
                pr_base="feature-2",
            ),
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-4",
                has_pr=True,
                pr_number=4,
                pr_base="feature-3",
            ),
        ]

        stacks = identify_stacks(pr_infos)
        assert len(stacks) == 1
        assert "feature-1" in stacks
        assert len(stacks["feature-1"]) == 4
        # Verify order: parent before children
        assert stacks["feature-1"][0].pr_number == 1
        assert stacks["feature-1"][1].pr_number == 2
        assert stacks["feature-1"][2].pr_number == 3
        assert stacks["feature-1"][3].pr_number == 4

    def test_no_prs(self) -> None:
        """Test when no PRs exist."""
        from qen.commands.pr import identify_stacks

        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="main",
                has_pr=False,
            ),
        ]

        stacks = identify_stacks(pr_infos)
        assert len(stacks) == 0

    def test_base_branch_without_pr(self) -> None:
        """Test when base branch exists but has no PR."""
        from qen.commands.pr import identify_stacks

        # feature-2 targets feature-1, but feature-1 has no PR
        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="feature-2",
                has_pr=True,
                pr_number=2,
                pr_base="feature-1",
            ),
        ]

        stacks = identify_stacks(pr_infos)
        # Should not create a stack since feature-1 doesn't have a PR
        assert len(stacks) == 0


class TestFormatStackDisplay:
    """Test stack display formatting."""

    def test_format_empty_stacks(self) -> None:
        """Test formatting when no stacks exist."""
        from qen.commands.pr import format_stack_display

        output = format_stack_display({})
        assert "No stacks found" in output

    def test_format_simple_stack(self) -> None:
        """Test formatting a simple stack."""
        from qen.commands.pr import format_stack_display

        stacks = {
            "feature-1": [
                PrInfo(
                    repo_path="repo1",
                    repo_url="https://github.com/org/repo1",
                    branch="feature-1",
                    has_pr=True,
                    pr_number=1,
                    pr_title="First PR",
                    pr_base="main",
                    pr_commits=5,
                    pr_files_changed=10,
                    pr_checks="passing",
                    pr_mergeable="mergeable",
                ),
                PrInfo(
                    repo_path="repo1",
                    repo_url="https://github.com/org/repo1",
                    branch="feature-2",
                    has_pr=True,
                    pr_number=2,
                    pr_title="Second PR",
                    pr_base="feature-1",
                    pr_commits=3,
                    pr_files_changed=7,
                    pr_checks="pending",
                    pr_mergeable="mergeable",
                ),
            ]
        }

        output = format_stack_display(stacks)
        assert "Stack rooted at: feature-1" in output
        assert "PR #1: First PR" in output
        assert "PR #2: Second PR" in output
        assert "5 commits" in output
        assert "10 files" in output
        assert "3 commits" in output
        assert "7 files" in output
        assert "Checks: passing" in output
        assert "Checks: pending" in output


class TestGetStackSummary:
    """Test stack summary statistics."""

    def test_summary_empty(self) -> None:
        """Test summary for no stacks."""
        from qen.commands.pr import get_stack_summary

        summary = get_stack_summary({})
        assert summary["total_stacks"] == 0
        assert summary["total_prs_in_stacks"] == 0
        assert summary["max_depth"] == 0

    def test_summary_multiple_stacks(self) -> None:
        """Test summary for multiple stacks."""
        from qen.commands.pr import get_stack_summary

        pr1 = PrInfo(
            repo_path="repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature-1",
            has_pr=True,
            pr_number=1,
            pr_base="main",
        )
        pr2 = PrInfo(
            repo_path="repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature-2",
            has_pr=True,
            pr_number=2,
            pr_base="feature-1",
        )
        pr3 = PrInfo(
            repo_path="repo2",
            repo_url="https://github.com/org/repo2",
            branch="feature-3",
            has_pr=True,
            pr_number=3,
            pr_base="main",
        )

        stacks = {
            "feature-1": [pr1, pr2],  # depth 2
            "feature-3": [pr3],  # depth 1
        }

        summary = get_stack_summary(stacks)
        assert summary["total_stacks"] == 2
        assert summary["total_prs_in_stacks"] == 3
        assert summary["max_depth"] == 2


class TestPrStackCommand:
    """Test qen pr stack command - removed CLI tests for removed 'qen pr stack' subcommand.

    The 'qen pr stack' subcommand was replaced with an interactive TUI ('qen pr --action stack').
    CLI tests that invoked the old subcommand have been removed.
    Unit tests for the underlying identify_stacks() and format_stack_display() functions
    are preserved in TestIdentifyStacks and TestFormatStackDisplay.
    """

    pass


class TestParseRepoOwnerAndName:
    """Test repository URL parsing."""

    def test_parse_https_url(self) -> None:
        """Test parsing HTTPS GitHub URL."""
        result = parse_repo_owner_and_name("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_parse_https_url_with_git_suffix(self) -> None:
        """Test parsing HTTPS URL with .git suffix."""
        result = parse_repo_owner_and_name("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_parse_ssh_url(self) -> None:
        """Test parsing SSH GitHub URL."""
        result = parse_repo_owner_and_name("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")

    def test_parse_owner_repo_format(self) -> None:
        """Test parsing owner/repo format."""
        result = parse_repo_owner_and_name("owner/repo")
        assert result == ("owner", "repo")

    def test_parse_invalid_url(self) -> None:
        """Test parsing invalid URL returns None."""
        assert parse_repo_owner_and_name("invalid-url") is None
        assert parse_repo_owner_and_name("http://example.com/repo") is None


class TestRestackPr:
    """Test PR restacking functionality."""

    @patch("subprocess.run")
    def test_restack_pr_success(self, mock_run: Mock) -> None:
        """Test successful PR branch update."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = restack_pr("owner", "repo", 123)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "api" in call_args
        assert "repos/owner/repo/pulls/123/update-branch" in call_args
        assert "-X" in call_args
        assert "PUT" in call_args

    @patch("subprocess.run")
    def test_restack_pr_already_up_to_date(self, mock_run: Mock) -> None:
        """Test when PR is already up to date."""
        mock_run.return_value = Mock(
            returncode=1, stdout="", stderr="pull request branch is already up to date"
        )

        result = restack_pr("owner", "repo", 123)

        assert result is True

    @patch("subprocess.run")
    def test_restack_pr_failure(self, mock_run: Mock) -> None:
        """Test PR update failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="API error")

        result = restack_pr("owner", "repo", 123)

        assert result is False

    @patch("subprocess.run")
    def test_restack_pr_timeout(self, mock_run: Mock) -> None:
        """Test PR update timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

        result = restack_pr("owner", "repo", 123)

        assert result is False

    def test_restack_pr_dry_run(self) -> None:
        """Test dry run mode doesn't make API calls."""
        result = restack_pr("owner", "repo", 123, dry_run=True)

        assert result is True


class TestPrRestackCommand:
    """Test qen pr restack command - removed CLI tests for removed 'qen pr restack' subcommand.

    The 'qen pr restack' subcommand was replaced with an interactive TUI ('qen pr --action restack').
    CLI tests that invoked the old subcommand have been removed.
    Unit tests for the underlying restack_pr() function are preserved in TestRestackPr.
    """

    pass
