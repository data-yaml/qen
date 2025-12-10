"""Integration tests for qen config branch switching.

NO MOCKS ALLOWED. These tests use real git commands and qen CLI to verify that
the qen config command actually switches git branches.
"""

import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_qen_config_switches_branch(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that qen config actually switches git branch.

    This test verifies that the qen config command correctly switches
    to the branch associated with the specified project.

    Args:
        tmp_meta_repo: Temporary git repository for testing
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
    # Change to meta repo directory
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_meta_repo)

        # Initialize qen (REAL command)
        result = run_qen(["init"], temp_config_dir, cwd=tmp_meta_repo)
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create two projects
        project1_name = f"{unique_project_name}-1"
        project2_name = f"{unique_project_name}-2"

        # Create projects
        for project_name in [project1_name, project2_name]:
            result = run_qen(
                ["init", project_name, "--yes"],
                temp_config_dir,
                cwd=tmp_meta_repo,
            )
            assert result.returncode == 0, f"qen init {project_name} failed: {result.stderr}"

        # Switch to project1 - should switch branch
        result = run_qen(
            ["config", project1_name],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen config {project1_name} failed: {result.stderr}"

        # Verify we're on project1's branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=tmp_meta_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch_name = result.stdout.strip()
        assert project1_name in branch_name, f"Not on project branch: {branch_name}"

        # Switch to project2 - should switch branch again
        result = run_qen(
            ["config", project2_name],
            temp_config_dir,
            cwd=tmp_meta_repo,
        )
        assert result.returncode == 0, f"qen config {project2_name} failed: {result.stderr}"

        # Verify we're on project2's branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=tmp_meta_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        branch_name = result.stdout.strip()
        assert project2_name in branch_name, f"Not on project branch: {branch_name}"

    finally:
        os.chdir(original_cwd)
