"""Integration tests for PR status parsing against real GitHub repository."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal
from unittest.mock import Mock, patch

import pytest

from qen.commands.pr import get_pr_info_for_branch


def load_mock_pr_data(repo_path: Path, branch: str) -> dict | None:
    """Load mock PR data from the test repository.

    Args:
        repo_path: Path to the test repository
        branch: Branch name to get PR data for

    Returns:
        Mock PR data dictionary or None if not found
    """
    mock_dir = repo_path / ".gh-mock"
    if not mock_dir.exists():
        return None

    mock_file = mock_dir / f"{branch.replace('/', '_')}.json"
    if not mock_file.exists():
        return None

    return json.loads(mock_file.read_text())


def ensure_test_pr_exists(
    branch: str,
    title: str,
    expected_checks: Literal["passing", "failing", "pending", "mixed", "none", "conflicts"],
) -> None:
    """
    Ensure a test PR exists in the test repository with specific characteristics.

    For local test repos, this is a no-op since PRs are pre-configured.

    Args:
        branch: Name of the test branch
        title: Title of the pull request
        expected_checks: Expected check state for the PR
    """
    # For local test repo, PRs are pre-configured in setup_test_repo.py
    pass


def trigger_slow_workflow(branch: str) -> None:
    """
    Trigger a workflow that takes time to simulate in-progress checks.

    TODO: Implement workflow trigger
    Args:
        branch: Name of the branch to trigger workflow on
    """
    # TODO: Implement GitHub Actions workflow trigger
    print(f"Triggering slow workflow for branch {branch}")


@pytest.fixture
def mock_gh_pr_view(request):
    """Mock gh pr view command to return test PR data.

    This fixture patches subprocess.run to intercept gh CLI calls and return
    mock PR data from the .gh-mock directory in the test repository.
    """
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        # Only intercept gh pr view commands
        if args and len(args[0]) >= 3 and args[0][0:3] == ["gh", "pr", "view"]:
            # Extract the branch name from the command
            branch = args[0][3] if len(args[0]) > 3 else "main"
            cwd = kwargs.get("cwd")

            if cwd:
                repo_path = Path(cwd)
                mock_data = load_mock_pr_data(repo_path, branch)

                if mock_data:
                    # Create a successful response with mock data
                    mock_result = Mock()
                    mock_result.returncode = 0
                    mock_result.stdout = json.dumps(mock_data)
                    mock_result.stderr = ""
                    return mock_result

        # For non-gh commands or when mock data isn't available, use original
        return original_run(*args, **kwargs)

    # Patch in both subprocess module and qen.commands.pr module
    with (
        patch("subprocess.run", side_effect=mock_run),
        patch("qen.commands.pr.subprocess.run", side_effect=mock_run),
    ):
        yield


@pytest.mark.integration
@pytest.mark.requires_test_repo
@pytest.mark.usefixtures("mock_gh_pr_view")
class TestRealPrStatus:
    """Test PR status parsing against a real GitHub repository."""

    def test_pr_with_passing_checks(self, clone_test_repo) -> None:
        """Test parsing PR with all passing checks."""
        # The fixture returns the repo path directly
        repo_path = clone_test_repo

        # Checkout the test branch
        subprocess.run(
            ["git", "checkout", "test/passing-checks"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Get PR info using real qen code
        pr_info = get_pr_info_for_branch(
            repo_path, "test/passing-checks", "https://github.com/quiltdata/qen-test-repo"
        )

        # Verify parsing
        assert pr_info is not None
        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "passing"

    def test_pr_with_failing_checks(self, clone_test_repo) -> None:
        """Test parsing PR with failing checks."""
        repo_path = clone_test_repo
        subprocess.run(
            ["git", "checkout", "test/failing-checks"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        pr_info = get_pr_info_for_branch(
            repo_path, "test/failing-checks", "https://github.com/quiltdata/qen-test-repo"
        )

        assert pr_info is not None
        assert pr_info.has_pr is True
        assert pr_info.pr_checks == "failing"

    def test_pr_with_in_progress_checks(self, clone_test_repo) -> None:
        """Test parsing PR with in-progress checks."""
        repo_path = clone_test_repo
        subprocess.run(
            ["git", "checkout", "test/in-progress-checks"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        pr_info = get_pr_info_for_branch(
            repo_path, "test/in-progress-checks", "https://github.com/quiltdata/qen-test-repo"
        )

        assert pr_info is not None
        assert pr_info.pr_checks == "pending"

    def test_pr_with_mixed_states(self, clone_test_repo) -> None:
        """Test parsing PR with mixed check states."""
        repo_path = clone_test_repo
        subprocess.run(
            ["git", "checkout", "test/mixed-checks"], cwd=repo_path, check=True, capture_output=True
        )

        pr_info = get_pr_info_for_branch(
            repo_path, "test/mixed-checks", "https://github.com/quiltdata/qen-test-repo"
        )

        assert pr_info is not None
        # Mixed checks (success + skipped) still count as passing
        assert pr_info.pr_checks == "passing"

    def test_pr_with_no_checks(self, clone_test_repo) -> None:
        """Test parsing PR with no checks."""
        repo_path = clone_test_repo
        subprocess.run(
            ["git", "checkout", "test/no-checks"], cwd=repo_path, check=True, capture_output=True
        )

        pr_info = get_pr_info_for_branch(
            repo_path, "test/no-checks", "https://github.com/quiltdata/qen-test-repo"
        )

        assert pr_info is not None
        # When there are no checks, pr_checks is None (not "none")
        assert pr_info.pr_checks is None

    def test_pr_with_merge_conflicts(self, clone_test_repo) -> None:
        """Test parsing PR with merge conflicts."""
        repo_path = clone_test_repo
        subprocess.run(
            ["git", "checkout", "test/merge-conflicts"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        pr_info = get_pr_info_for_branch(
            repo_path, "test/merge-conflicts", "https://github.com/quiltdata/qen-test-repo"
        )

        assert pr_info is not None
        assert pr_info.has_pr is True
        # Merge conflicts are indicated by pr_mergeable, not pr_checks
        assert pr_info.pr_mergeable == "conflicting"
