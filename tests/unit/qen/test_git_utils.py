"""Unit tests for qen.git_utils module."""

import subprocess
import unittest.mock

import pytest

from qen.git_utils import checkout_branch, has_uncommitted_changes


def test_has_uncommitted_changes_clean(tmp_path):
    """Test has_uncommitted_changes with clean repo."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = unittest.mock.Mock(stdout="", returncode=0)

        result = has_uncommitted_changes(tmp_path)

        assert result is False
        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )


def test_has_uncommitted_changes_dirty(tmp_path):
    """Test has_uncommitted_changes with uncommitted changes."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = unittest.mock.Mock(stdout=" M file.txt\n", returncode=0)

        result = has_uncommitted_changes(tmp_path)

        assert result is True
        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        )


def test_checkout_branch_success(tmp_path):
    """Test checkout_branch success."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = unittest.mock.Mock(returncode=0)

        checkout_branch(tmp_path, "my-branch")

        mock_run.assert_called_once_with(["git", "checkout", "my-branch"], cwd=tmp_path, check=True)


def test_checkout_branch_failure(tmp_path):
    """Test checkout_branch when branch doesn't exist or checkout fails."""
    with unittest.mock.patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "checkout", "non-existent-branch"],
            stderr="error: pathspec 'non-existent-branch' did not match any file(s) known to git",
        )

        with pytest.raises(subprocess.CalledProcessError):
            checkout_branch(tmp_path, "non-existent-branch")

        mock_run.assert_called_once_with(
            ["git", "checkout", "non-existent-branch"], cwd=tmp_path, check=True
        )
