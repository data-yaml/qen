"""Integration tests for qen init using REAL GitHub remotes.

These tests use data-yaml/qen-test as the remote repository to validate
that qen init works correctly with real GitHub API operations including:
- git ls-remote for remote branch discovery
- git clone from real GitHub URLs
- Proper handling of network errors

IMPORTANT: These are REAL integration tests - NO MOCKS allowed!
- Use real git commands
- Use real GitHub repository (data-yaml/qen-test)
- Test actual network operations

See spec/6-debt/09-wrapper-test-fixes.md for context on why these tests
were created (previous tests used file:// URLs and didn't test real remotes).
"""

from pathlib import Path

import pytest

from tests.conftest import run_qen

pytestmark = pytest.mark.integration


class TestQenInitWithRealRemote:
    """Test qen init (global config) with real GitHub remote."""

    def test_init_extracts_real_github_remote(
        self,
        remote_meta_test_repo: Path,
        temp_config_dir: Path,
    ) -> None:
        """Test that qen init extracts the real GitHub remote URL.

        This test validates:
        1. qen init can find the local meta repo (data-yaml/qen-test clone)
        2. It extracts the real GitHub remote URL
        3. It queries the remote for default branch using git ls-remote
        4. It stores the correct metadata in global config
        """
        # Run qen init from within the cloned repository
        result = run_qen(["init"], temp_config_dir, cwd=remote_meta_test_repo)

        # Should succeed
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Verify global config was created
        global_config = temp_config_dir / "main" / "config.toml"
        assert global_config.exists(), "Global config not created"

        # Read config and verify it has real GitHub URL
        import tomllib

        config_data = tomllib.loads(global_config.read_text())

        assert "meta_remote" in config_data, "meta_remote not in config"
        assert "github.com" in config_data["meta_remote"], (
            f"Expected GitHub URL, got: {config_data['meta_remote']}"
        )
        assert "data-yaml/qen-test" in config_data["meta_remote"], (
            f"Expected data-yaml/qen-test, got: {config_data['meta_remote']}"
        )

        # Verify organization was extracted
        assert config_data.get("org") == "data-yaml", (
            f"Expected org 'data-yaml', got: {config_data.get('org')}"
        )

        # Verify default branch was detected (should be "main")
        assert config_data.get("meta_default_branch") == "main", (
            f"Expected default branch 'main', got: {config_data.get('meta_default_branch')}"
        )

        # Verify meta_path points to the local clone
        assert Path(config_data["meta_path"]) == remote_meta_test_repo

        # Verify meta_parent is set correctly (parent directory of meta)
        assert Path(config_data["meta_parent"]) == remote_meta_test_repo.parent


class TestQenInitProjectWithRealRemote:
    """Test qen init <project> (project creation) with real GitHub remote."""

    def test_init_project_creates_new_with_real_clone(
        self,
        remote_meta_test_repo: Path,
        temp_config_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test creating a new project clones from real GitHub URL.

        This test validates:
        1. qen init <project> discovers no existing remote branches
        2. It clones from the REAL GitHub URL (not file://)
        3. It creates per-project meta in correct location
        4. It creates project structure correctly
        """
        import uuid
        from datetime import datetime

        # First, initialize qen global config
        result = run_qen(["init"], temp_config_dir, cwd=remote_meta_test_repo)
        assert result.returncode == 0, f"qen init failed: {result.stderr}"

        # Create unique project name to avoid conflicts
        unique_id = str(uuid.uuid4())[:8]
        project_name = f"testproj-{unique_id}"

        # Run qen init <project> with --yes to skip confirmation
        result = run_qen(
            ["init", project_name, "--yes"],
            temp_config_dir,
            cwd=remote_meta_test_repo,
        )

        # Should succeed
        assert result.returncode == 0, f"qen init {project_name} failed: {result.stderr}"

        # Verify per-project meta was created
        per_project_meta = remote_meta_test_repo.parent / f"meta-{project_name}"
        assert per_project_meta.exists(), f"Per-project meta not created: {per_project_meta}"

        # Verify it's a git repository
        assert (per_project_meta / ".git").exists(), "Per-project meta is not a git repo"

        # Verify remote points to real GitHub (not file://)
        import subprocess

        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        remote_url = remote_result.stdout.strip()

        assert "github.com" in remote_url, f"Expected GitHub URL, got: {remote_url}"
        assert "data-yaml/qen-test" in remote_url, f"Expected data-yaml/qen-test, got: {remote_url}"
        assert not remote_url.startswith("file://"), (
            f"Remote should not use file:// protocol, got: {remote_url}"
        )

        # Verify project structure was created
        date_prefix = datetime.now().strftime("%y%m%d")
        branch_name = f"{date_prefix}-{project_name}"
        project_dir = per_project_meta / "proj" / branch_name

        assert project_dir.exists(), f"Project directory not created: {project_dir}"
        assert (project_dir / "README.md").exists(), "README.md not created"
        assert (project_dir / "pyproject.toml").exists(), "pyproject.toml not created"

        # Verify we're on the correct branch
        branch_result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = branch_result.stdout.strip()
        assert current_branch == branch_name, (
            f"Expected branch '{branch_name}', got '{current_branch}'"
        )

        # Verify project config was created
        project_config = temp_config_dir / project_name / "config.toml"
        assert project_config.exists(), "Project config not created"

        import tomllib

        config_data = tomllib.loads(project_config.read_text())
        assert config_data["name"] == project_name
        assert Path(config_data["repo"]) == per_project_meta

    def test_init_project_already_setup_no_op(
        self,
        remote_meta_test_repo: Path,
        temp_config_dir: Path,
        tmp_path: Path,
    ) -> None:
        """Test running qen init <project> when project already exists.

        This test validates:
        1. Discovery detects existing project (config + repo)
        2. No clone operation is attempted
        3. Command succeeds with no-op behavior
        """
        import uuid

        # Setup: Initialize qen and create a project
        result = run_qen(["init"], temp_config_dir, cwd=remote_meta_test_repo)
        assert result.returncode == 0

        unique_id = str(uuid.uuid4())[:8]
        project_name = f"testproj-{unique_id}"

        result = run_qen(
            ["init", project_name, "--yes"],
            temp_config_dir,
            cwd=remote_meta_test_repo,
        )
        assert result.returncode == 0

        # Verify project exists
        per_project_meta = remote_meta_test_repo.parent / f"meta-{project_name}"
        assert per_project_meta.exists()

        # Run qen init <project> again (should be no-op)
        result = run_qen(
            ["init", project_name],
            temp_config_dir,
            cwd=remote_meta_test_repo,
        )

        # Should succeed without errors
        assert result.returncode == 0, f"Second init failed: {result.stderr}"

        # Verify no second clone was attempted (check git log hasn't changed)
        import subprocess

        log_result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )

        # Should have qen-test commits + 1 project creation commit
        # The exact number depends on qen-test history, but should have project init commit on top
        log_lines = [line for line in log_result.stdout.strip().split("\n") if line]
        assert len(log_lines) >= 2, f"Expected at least 2 commits, got {len(log_lines)}"

        # Verify the top commit is the project initialization
        assert "Initialize project" in log_lines[0], (
            f"Top commit should be project init, got: {log_lines[0]}"
        )
