"""Integration tests for qen config branch switching.

NO MOCKS ALLOWED. These tests use real git commands and qen CLI to verify that
the qen config command actually switches git branches.
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_qen_config_switches_branch(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    """Test that qen config actually switches git branch in per-project meta.

    This test verifies that the qen config command correctly switches
    to the branch associated with the specified project in its per-project
    meta clone (not in meta prime).

    Args:
        tmp_meta_repo: Temporary git repository (meta prime)
        unique_project_name: Unique project name to avoid conflicts
        temp_config_dir: Isolated config directory to avoid polluting user config
    """
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

    # Helper to get per-project meta path from config
    def get_per_project_meta(project: str) -> Path:
        config_path = temp_config_dir / project / "config.toml"
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        return Path(config["repo"])

    # Get per-project meta paths
    project1_meta = get_per_project_meta(project1_name)
    project2_meta = get_per_project_meta(project2_name)

    # Switch to project1 - should switch branch in project1's meta
    result = run_qen(
        ["config", project1_name],
        temp_config_dir,
        cwd=tmp_meta_repo,
    )
    assert result.returncode == 0, f"qen config {project1_name} failed: {result.stderr}"

    # Verify we're on project1's branch in its per-project meta
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project1_meta,
        capture_output=True,
        text=True,
        check=True,
    )
    branch_name = result.stdout.strip()
    assert project1_name in branch_name, f"Not on project1 branch: {branch_name}"

    # Switch to project2 - should switch branch in project2's meta
    result = run_qen(
        ["config", project2_name],
        temp_config_dir,
        cwd=tmp_meta_repo,
    )
    assert result.returncode == 0, f"qen config {project2_name} failed: {result.stderr}"

    # Verify we're on project2's branch in its per-project meta
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=project2_meta,
        capture_output=True,
        text=True,
        check=True,
    )
    branch_name = result.stdout.strip()
    assert project2_name in branch_name, f"Not on project2 branch: {branch_name}"
