"""Integration test for proj/qen wrapper script.

Tests that the auto-generated wrapper script:
1. Has all template variables substituted (no ${...} remain)
2. Is executable
3. Can run basic qen commands

Uses REAL qen-test repository for integration testing.
NO MOCKS ALLOWED.

Key insight: Use --meta flag to specify qen-test as meta repo
without touching the user's actual qen configuration.
"""

import re
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from tests.integration.helpers import create_test_project


@pytest.mark.integration
def test_qen_wrapper_generation(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
) -> None:
    """Test that qen init generates working wrapper script - REAL GITHUB API.

    Creates a real project in qen-test and verifies:
    - All files from ./proj templates are created
    - No template variables remain (no ${...})
    - Wrapper script is executable
    - Wrapper script can run commands

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Temporary config directory to avoid polluting user config
    """
    # Generate project name with unique prefix
    project_name = f"{unique_prefix}-wrapper-test"

    # Create project using helper - returns per-project meta and project dir paths
    per_project_meta, project_dir = create_test_project(
        real_test_repo,
        project_name,
        temp_config_dir,
    )

    # Track branch for cleanup
    # Extract branch name from project (YYMMDD-project-name format)
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # Verify project directory exists
    assert project_dir.exists(), f"Project directory not created: {project_dir}"

    # Verify all expected files exist
    expected_files = ["README.md", "pyproject.toml", ".gitignore", "qen"]
    for file in expected_files:
        file_path = project_dir / file
        assert file_path.exists(), f"Expected file missing: {file}"

    # Verify repos directory exists
    repos_dir = project_dir / "repos"
    assert repos_dir.exists(), "repos directory not created"
    assert repos_dir.is_dir(), "repos is not a directory"

    # Verify qen wrapper is executable
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.stat().st_mode & 0o111, "qen wrapper is not executable"

    # Verify NO template variables remain in any file
    # Check for Python template variables like ${project_name}, ${date}, etc.
    # Exclude bash variables like ${BASH_SOURCE[0]} which use digits/brackets
    # Template variables use only letters and underscores
    template_var_pattern = re.compile(r"\$\{([a-z_]+)\}")

    for file in ["README.md", "pyproject.toml", ".gitignore", "qen"]:
        content = (project_dir / file).read_text()
        matches = template_var_pattern.findall(content)
        assert not matches, f"Unsubstituted template variables in {file}: {matches}"

    # Verify wrapper script can execute
    # Run a simple command: ./qen status (should work even with no repos)
    # NOTE: This is the only place we call ./qen directly (testing the wrapper itself)
    # IMPORTANT: Must pass --config-dir to avoid polluting user's config
    result = subprocess.run(
        ["./qen", "--config-dir", str(temp_config_dir), "status"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    # Should succeed or fail gracefully (not with exec error)
    # Don't check return code - just verify it runs without bash errors
    assert "bash:" not in result.stderr.lower(), f"Wrapper execution failed: {result.stderr}"
    assert "command not found" not in result.stderr.lower(), (
        f"uvx or qen not found: {result.stderr}"
    )


@pytest.mark.integration
def test_qen_wrapper_help_command(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
) -> None:
    """Test wrapper forwards --help to qen CLI - REAL OPERATIONS.

    Verifies the wrapper script passes through help flag correctly.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Temporary config directory
    """
    # Create project
    project_name = f"{unique_prefix}-help-test"
    per_project_meta, project_dir = create_test_project(
        real_test_repo,
        project_name,
        temp_config_dir,
    )

    # Track branch for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # Find wrapper script
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.exists(), f"qen wrapper not created at {qen_wrapper}"

    # Test: Run ./qen --help (REAL execution)
    result = subprocess.run(
        ["./qen", "--help"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    # Should show qen help text
    assert result.returncode == 0 or "Usage:" in result.stdout, (
        f"Help command failed: {result.stderr}"
    )
    assert "qen" in result.stdout.lower(), "Should show qen help text"


@pytest.mark.integration
@pytest.mark.parametrize(
    "cwd_type,test_suffix",
    [
        ("parent", "parent-test"),
        ("arbitrary", "arbitrary-test"),
    ],
)
def test_qen_wrapper_works_from_different_cwd(
    cwd_type: str,
    test_suffix: str,
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test wrapper works from different working directories - REAL OPERATIONS.

    Verifies the wrapper script resolves paths correctly when invoked from
    different locations (parent directory or arbitrary unrelated directory).

    Args:
        cwd_type: Type of working directory ("parent" or "arbitrary")
        test_suffix: Suffix for project name
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Temporary config directory
        tmp_path: Pytest temporary directory
    """
    # Create project
    project_name = f"{unique_prefix}-{test_suffix}"
    per_project_meta, project_dir = create_test_project(
        real_test_repo,
        project_name,
        temp_config_dir,
    )

    # Track branch for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # Find wrapper script
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.exists(), f"Wrapper script not found: {qen_wrapper}"

    # Determine working directory based on cwd_type
    if cwd_type == "parent":
        # Run from parent directory (proj/)
        cwd = per_project_meta / "proj"
    elif cwd_type == "arbitrary":
        # Create and use arbitrary unrelated directory
        arbitrary_dir = tmp_path / "arbitrary-location"
        arbitrary_dir.mkdir()
        cwd = arbitrary_dir
    else:
        pytest.fail(f"Unknown cwd_type: {cwd_type}")

    # Test: Run wrapper from specified working directory (REAL execution)
    result = subprocess.run(
        [str(qen_wrapper), "--config-dir", str(temp_config_dir), "status"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    # Should succeed
    assert "bash:" not in result.stderr.lower(), (
        f"Wrapper failed from {cwd_type} directory: {result.stderr}"
    )
    assert "command not found" not in result.stderr.lower(), (
        f"uvx or qen not found when run from {cwd_type} directory: {result.stderr}"
    )


@pytest.mark.integration
def test_qen_wrapper_project_context(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
) -> None:
    """Test wrapper activates correct project context - REAL OPERATIONS.

    Creates multiple projects and verifies each wrapper activates its own
    project context correctly, not mixing up projects.

    Args:
        real_test_repo: Path to cloned qen-test repository
        unique_prefix: Unique prefix for test branches
        cleanup_branches: List to track branches for cleanup
        temp_config_dir: Temporary config directory
    """
    # Create two projects
    project1_name = f"{unique_prefix}-context-1"
    project2_name = f"{unique_prefix}-context-2"

    per_project_meta1, project1_dir = create_test_project(
        real_test_repo,
        project1_name,
        temp_config_dir,
    )

    per_project_meta2, project2_dir = create_test_project(
        real_test_repo,
        project2_name,
        temp_config_dir,
    )

    # Track branches for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch1_name = f"{date_prefix}-{project1_name}"
    branch2_name = f"{date_prefix}-{project2_name}"
    cleanup_branches.extend([branch1_name, branch2_name])

    # Find both wrapper scripts
    wrapper1 = project1_dir / "qen"
    wrapper2 = project2_dir / "qen"

    assert wrapper1.exists(), f"wrapper1 not created at {wrapper1}"
    assert wrapper2.exists(), f"wrapper2 not created at {wrapper2}"

    # Read wrapper scripts to verify they have correct project context (REAL file reads)
    wrapper1_content = wrapper1.read_text()
    wrapper2_content = wrapper2.read_text()

    # Verify each wrapper has its own project name embedded
    assert project1_name in wrapper1_content, "Wrapper 1 should contain project1 name"
    assert project2_name in wrapper2_content, "Wrapper 2 should contain project2 name"

    # Verify project names don't cross-contaminate
    assert project2_name not in wrapper1_content, "Wrapper 1 should NOT contain project2 name"
    assert project1_name not in wrapper2_content, "Wrapper 2 should NOT contain project1 name"

    # Verify wrappers have correct per-project meta paths (not meta prime!)
    assert str(per_project_meta1) in wrapper1_content, (
        "Wrapper 1 should contain per-project meta path"
    )
    assert str(per_project_meta2) in wrapper2_content, (
        "Wrapper 2 should contain per-project meta path"
    )

    # Test: Run both wrappers and verify they work independently (REAL execution)
    result1 = subprocess.run(
        [str(wrapper1), "--config-dir", str(temp_config_dir), "status"],
        capture_output=True,
        text=True,
    )
    assert "bash:" not in result1.stderr.lower(), (
        f"Wrapper1 execution failed with bash error: {result1.stderr}"
    )

    result2 = subprocess.run(
        [str(wrapper2), "--config-dir", str(temp_config_dir), "status"],
        capture_output=True,
        text=True,
    )
    assert "bash:" not in result2.stderr.lower(), (
        f"Wrapper2 execution failed with bash error: {result2.stderr}"
    )
