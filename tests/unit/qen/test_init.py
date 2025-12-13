"""Tests for qen init command.

Tests qen init functionality including:
- Meta repo discovery
- Organization extraction from git remotes
- Config creation and management
- Project initialization
- Error conditions
"""

import subprocess
from pathlib import Path

import click
import pytest

from qen.commands.init import init_project, init_qen
from qen.config import QenConfig
from qen.context.runtime import RuntimeContext
from tests.unit.helpers.qenvy_test import QenvyTest


def create_test_runtime_context(
    test_storage: QenvyTest, meta_path: Path | None = None, current_project: str | None = None
) -> RuntimeContext:
    """Helper to create RuntimeContext for testing."""
    ctx = RuntimeContext(
        config_dir=Path("/tmp/test-qen-config"),
        meta_path_override=meta_path,
        current_project_override=current_project,
    )
    # Replace the config service with one using test storage
    ctx._config_service = QenConfig(
        storage=test_storage,
        meta_path_override=meta_path,
        current_project_override=current_project,
    )
    return ctx


# ==============================================================================
# Test init_qen Function (Tooling Initialization)
# ==============================================================================


class TestInitQenFunction:
    """Test init_qen function for tooling initialization."""

    def test_init_qen_success(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test successful qen initialization from within meta repo."""
        # Setup: Rename to meta and add remote
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Create config with test storage
        config = QenConfig(storage=test_storage)

        # Execute init from meta directory
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            ctx = create_test_runtime_context(test_storage)
            init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

        # Verify: Main config was created
        assert config.main_config_exists()

        # Verify: Config has correct values
        main_config = config.read_main_config()
        assert main_config["meta_path"] == str(meta_repo)
        assert main_config["org"] == "testorg"
        assert "current_project" not in main_config  # Should be None, so not in TOML

    def test_init_qen_from_subdirectory(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test qen initialization from subdirectory within meta repo."""
        # Setup: Rename to meta and create subdirectory
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        subdir = meta_repo / "subdir"
        subdir.mkdir()

        # Create config with test storage
        config = QenConfig(storage=test_storage)

        # Execute init from subdirectory
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(subdir)
            ctx = create_test_runtime_context(test_storage)
            init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

        # Verify: Config was created with correct meta_path
        assert config.main_config_exists()
        main_config = config.read_main_config()
        assert main_config["meta_path"] == str(meta_repo)

    def test_init_qen_not_git_repo(self, tmp_path: Path, test_storage: QenvyTest) -> None:
        """Test that init fails when not in a git repository."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            ctx = create_test_runtime_context(test_storage)
            with pytest.raises(click.exceptions.Abort):
                init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_qen_no_meta_repo(self, temp_git_repo: Path, test_storage: QenvyTest) -> None:
        """Test that init fails when not in meta repository."""
        # Don't rename to meta - keep original name
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            ctx = create_test_runtime_context(test_storage)
            with pytest.raises(click.exceptions.Abort):
                init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_qen_no_remotes(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that init fails when git repo has no remotes."""
        # Setup: Rename to meta but don't add remotes
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            ctx = create_test_runtime_context(test_storage)
            with pytest.raises(click.exceptions.Abort):
                init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_qen_ambiguous_org(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that init fails with multiple different orgs in remotes."""
        # Setup: Rename to meta and add remotes with different orgs
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/org1/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "remote", "add", "upstream", "https://github.com/org2/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            ctx = create_test_runtime_context(test_storage)
            with pytest.raises(click.exceptions.Abort):
                init_qen(ctx=ctx, verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_qen_verbose_output(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        capsys,
    ) -> None:
        """Test that verbose mode produces output."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Execute with verbose=True
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            ctx = create_test_runtime_context(test_storage)
            init_qen(ctx=ctx, verbose=True)
        finally:
            os.chdir(original_cwd)

        # Verify: Verbose output was produced
        captured = capsys.readouterr()
        assert "Searching for meta repository" in captured.out
        assert "Found meta repository" in captured.out
        assert "Extracting metadata" in captured.out
        assert "Organization: testorg" in captured.out
        assert "Remote URL:" in captured.out
        assert "Meta parent directory:" in captured.out
        assert "Detecting default branch" in captured.out
        assert "Default branch:" in captured.out

    def test_init_qen_idempotent(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that running init multiple times is safe."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        config = QenConfig(storage=test_storage)

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            ctx = create_test_runtime_context(test_storage)

            # Run init first time
            init_qen(ctx=ctx, verbose=False)
            first_config = config.read_main_config()

            # Run init again
            init_qen(ctx=ctx, verbose=False)
            second_config = config.read_main_config()

            # Verify: Config is unchanged (excluding metadata timestamps)
            assert first_config["meta_path"] == second_config["meta_path"]
            assert first_config["org"] == second_config["org"]
        finally:
            os.chdir(original_cwd)


# ==============================================================================
# Test init_project Function (Project Initialization)
# ==============================================================================
# NOTE: These tests were moved to integration tests or deleted due to being
# pseudo-integration tests that did real git operations without proper mocking.

# ==============================================================================
# Test Branch Creation Behavior
# ==============================================================================
# NOTE: TestInitProjectFunction, TestInitEdgeCases, and TestInitProjectPRCreation
# were deleted as they were pseudo-integration tests doing real git operations.
# See tests/integration/test_init.py for proper integration test coverage.


# ==============================================================================
# Test Branch Creation Behavior
# ==============================================================================


class TestInitProjectBranchCreation:
    """Test that qen init creates branches from the correct base."""

    def test_init_project_branches_from_main_not_current_branch(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that qen init creates project branch from main, not current branch.

        This is a regression test for the bug where qen init would branch from
        the current branch instead of main/master.
        """
        # Setup: Create meta repo and initialize qen
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        # Create an initial commit on main
        initial_file = meta_repo / "README.md"
        initial_file.write_text("Initial commit")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Get commit hash of main (current branch at this point)
        main_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=meta_repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Create remote tracking branch for main
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/main", main_commit],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Set refs/remotes/origin/HEAD to point to main
        subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Create per-project meta repo by cloning from meta_repo
        # This simulates what clone_per_project_meta actually does
        per_project_meta = meta_repo.parent / "meta-test-project"
        subprocess.run(
            ["git", "clone", str(meta_repo), str(per_project_meta)],
            check=True,
            capture_output=True,
        )

        # Switch to main branch in per-project meta
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=per_project_meta,
            check=True,
            capture_output=True,
        )

        # Mock clone_per_project_meta
        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            return_value=per_project_meta,
        )

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            meta_remote="https://github.com/testorg/meta",
            meta_parent=str(meta_repo.parent),
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Create a feature branch and switch to it
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Add a commit to the feature branch to differentiate it from main
        feature_file = meta_repo / "feature.txt"
        feature_file.write_text("This is only on feature branch")
        subprocess.run(
            ["git", "add", "feature.txt"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add feature file"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Execute: Create project while on feature-branch
        project_name = "test-project"
        ctx = create_test_runtime_context(test_storage)
        init_project(ctx=ctx, project_name=project_name, verbose=False, yes=True)

        # Verify: Project branch was created from default branch, not feature-branch
        project_config = config.read_project_config(project_name)
        project_branch = project_config["branch"]

        # Get the default branch name from config (could be 'main' or 'master')
        main_config = config.read_main_config()
        default_branch = main_config["meta_default_branch"]

        # Get the merge-base of the project branch in per_project_meta
        # It should be the default branch (the initial commit), not feature-branch
        merge_base = subprocess.run(
            ["git", "merge-base", project_branch, default_branch],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Get the default branch's current commit hash in per_project_meta
        per_project_default_commit = subprocess.run(
            ["git", "rev-parse", default_branch],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # The merge-base should equal per_project_meta's default branch commit hash
        # (meaning project branch started from default branch in the per-project meta)
        assert merge_base == per_project_default_commit, (
            f"Project branch should have branched from {default_branch} "
            f"({per_project_default_commit}), but merge-base is {merge_base}"
        )

        # Additionally verify: feature.txt should NOT exist on the project branch
        # (per-project meta was cloned from remote, not from meta_repo with feature-branch)
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", project_branch],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "feature.txt" not in result.stdout, (
            "Project branch should not contain feature.txt from feature-branch"
        )
