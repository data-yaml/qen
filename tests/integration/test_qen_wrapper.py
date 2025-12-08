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

from tests.conftest import run_qen


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

    # Create project using run_qen helper (REAL command, NO MOCKS)
    # Helper automatically adds --config-dir to isolate test config
    # --meta flag specifies qen-test as meta repo
    result = run_qen(
        ["--meta", str(real_test_repo), "init", project_name, "--yes"],
        temp_config_dir,
    )

    assert result.returncode == 0, f"qen init failed: {result.stderr}"

    # Track branch for cleanup
    # Extract branch name from project (YYMMDD-project-name format)
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # Verify project directory exists
    project_dir = real_test_repo / "proj" / branch_name
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
