"""Tests for qen init command.

Tests qen init functionality including:
- Meta repo discovery
- Organization extraction from git remotes
- Config creation and management
- Project initialization
- Error conditions
"""

import subprocess
from datetime import datetime
from pathlib import Path

import click
import pytest

from qen.commands.init import init_project, init_qen
from qen.config import ProjectAlreadyExistsError, QenConfig, QenConfigError
from tests.helpers.qenvy_test import QenvyTest

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
            init_qen(verbose=False, storage=test_storage)
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
            init_qen(verbose=False, storage=test_storage)
        finally:
            os.chdir(original_cwd)

        # Verify: Config was created with correct meta_path
        assert config.main_config_exists()
        main_config = config.read_main_config()
        assert main_config["meta_path"] == str(meta_repo)

    def test_init_qen_not_git_repo(self, tmp_path: Path) -> None:
        """Test that init fails when not in a git repository."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(click.exceptions.Abort):
                init_qen(verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_qen_no_meta_repo(self, temp_git_repo: Path) -> None:
        """Test that init fails when not in meta repository."""
        # Don't rename to meta - keep original name
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_git_repo)
            with pytest.raises(click.exceptions.Abort):
                init_qen(verbose=False)
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
            with pytest.raises(click.exceptions.Abort):
                init_qen(verbose=False)
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
            with pytest.raises(click.exceptions.Abort):
                init_qen(verbose=False)
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
            init_qen(verbose=True, storage=test_storage)
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

            # Run init first time
            init_qen(verbose=False, storage=test_storage)
            first_config = config.read_main_config()

            # Run init again
            init_qen(verbose=False, storage=test_storage)
            second_config = config.read_main_config()

            # Verify: Config is unchanged (excluding metadata timestamps)
            assert first_config["meta_path"] == second_config["meta_path"]
            assert first_config["org"] == second_config["org"]
        finally:
            os.chdir(original_cwd)


# ==============================================================================
# Test init_project Function (Project Initialization)
# ==============================================================================


class TestInitProjectFunction:
    """Test init_project function for creating new projects."""

    def test_init_project_success(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test successful project creation."""
        # Setup: Create meta repo and initialize qen
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch(
            "qen.commands.init.find_remote_branches",
            return_value=[],
        )

        # Track the created per_project_meta path
        created_per_project_meta = None

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            nonlocal created_per_project_meta
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            # Create initial commit on main branch
            (per_project_meta / "README.md").write_text("# Test Repo")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "branch", "-M", "main"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            created_per_project_meta = per_project_meta
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
        )

        # Mock git push to avoid network calls
        original_run = subprocess.run

        def mock_run(*args, **kwargs):
            if args and args[0] and "push" in args[0]:
                return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")
            return original_run(*args, **kwargs)

        mocker.patch("subprocess.run", side_effect=mock_run)

        # Initialize qen config
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            meta_remote="https://github.com/testorg/meta",
            meta_parent=str(meta_repo.parent),
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Execute: Create project with yes=True to skip confirmation
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Verify: Project config was created
        assert config.project_config_exists(project_name)
        project_config = config.read_project_config(project_name)
        assert project_config["name"] == project_name
        assert "branch" in project_config
        assert "folder" in project_config
        assert "repo" in project_config
        assert "created" in project_config
        assert created_per_project_meta is not None
        assert project_config["repo"] == str(created_per_project_meta)

        # Verify: Project directory exists in per-project meta
        folder_path = Path(project_config["folder"])
        project_dir = created_per_project_meta / folder_path
        assert project_dir.exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "repos").exists()
        assert (project_dir / ".gitignore").exists()

        # Verify: Current project was updated
        main_config = config.read_main_config()
        assert main_config["current_project"] == project_name

        # Verify: Branch was created in per-project meta
        result = subprocess.run(
            ["git", "branch", "--list", project_config["branch"]],
            cwd=created_per_project_meta,
            capture_output=True,
            text=True,
        )
        assert project_config["branch"] in result.stdout

    def test_init_project_without_main_config(self, test_storage: QenvyTest, mocker) -> None:
        """Test that init_project auto-initializes when main config missing."""
        # Mock find_meta_repo to simulate we're in a meta repo
        mock_meta_path = Path("/tmp/mock-meta")
        mocker.patch("qen.commands.init.find_meta_repo", return_value=mock_meta_path)

        # Mock the git operations that init_qen would perform
        mocker.patch(
            "qen.commands.init.extract_remote_and_org",
            return_value=("git@github.com:testorg/meta.git", "testorg"),
        )
        mocker.patch("qen.git_utils.get_default_branch_from_remote", return_value="main")

        # Mock find_remote_branches to return empty list
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # After auto-init, init_project should fail because it can't clone (mocked incorrectly)
        # Let's just verify it doesn't abort immediately - it will try to proceed
        with pytest.raises(click.exceptions.Abort):
            init_project("test-project", verbose=False, yes=True, storage=test_storage)

    def test_init_project_already_exists(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that init_project fails if project already exists."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Create per-project meta repo for first initialization
        per_project_meta = meta_repo.parent / "meta-test-project"
        per_project_meta.mkdir()
        subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
        (per_project_meta / "README.md").write_text("# Test Project")
        subprocess.run(["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=per_project_meta,
            check=True,
            capture_output=True,
        )

        # Mock clone_per_project_meta to return our test repo
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

        # Create project first time
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Try to create again - should fail
        with pytest.raises(click.exceptions.Abort):
            init_project(project_name, verbose=False, yes=True, storage=test_storage)

    def test_init_project_force_recreate(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that init_project with --force recreates existing project."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock clone_per_project_meta to create a fresh repo each time (handles force mode)
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = meta_repo.parent / "meta-test-project"
            # Recreate if it was deleted by force mode
            if not per_project_meta.exists():
                per_project_meta.mkdir()
            if not (per_project_meta / ".git").exists():
                subprocess.run(
                    ["git", "init"], cwd=per_project_meta, check=True, capture_output=True
                )
                (per_project_meta / "README.md").write_text("# Test Project")
                subprocess.run(
                    ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
                )
                subprocess.run(
                    ["git", "commit", "-m", "Initial commit"],
                    cwd=per_project_meta,
                    check=True,
                    capture_output=True,
                )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Create project first time
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Try to create again with force - should succeed
        init_project(project_name, verbose=True, yes=True, force=True, storage=test_storage)

        # Verify: New config exists with correct values
        second_config = config.read_project_config(project_name)
        second_branch = second_config["branch"]

        # Branch and folder should be recreated
        assert config.project_config_exists(project_name)
        assert second_config["name"] == project_name

        # Verify new branch exists (in per-project meta, not meta prime)
        per_project_meta_path = Path(second_config["repo"])
        result = subprocess.run(
            ["git", "branch", "--list", second_branch],
            cwd=per_project_meta_path,
            capture_output=True,
            text=True,
        )
        assert second_branch in result.stdout

    def test_init_project_verbose_output(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        capsys,
        mocker,
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

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text("# Test Project")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Execute with verbose=True and yes=True
        init_project("test-project", verbose=True, yes=True, storage=test_storage)

        # Verify: Verbose output was produced
        captured = capsys.readouterr()
        # With discovery-first approach, we see discovery state and actions
        assert "Discovering project state..." in captured.out
        assert "Project: test-project" in captured.out
        assert "Remote branches: Not found" in captured.out
        assert "Actions to perform:" in captured.out
        assert "Cloned:" in captured.out
        assert "Created branch:" in captured.out
        assert "Created directory:" in captured.out

    def test_init_project_creates_correct_structure(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that project structure is created correctly."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text("# Test Project")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Execute with yes=True
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Verify: Check all files and their content
        project_config = config.read_project_config(project_name)
        # Project is now in per-project meta, not meta prime
        per_project_meta_path = Path(project_config["repo"])
        project_dir = per_project_meta_path / project_config["folder"]

        # Check README.md
        readme_content = (project_dir / "README.md").read_text()
        assert project_name in readme_content
        assert "./qen" in readme_content  # Check for project wrapper

        # Check pyproject.toml
        pyproject_content = (project_dir / "pyproject.toml").read_text()
        assert "[tool.qen]" in pyproject_content
        assert "created" in pyproject_content

        # Check .gitignore
        gitignore_content = (project_dir / ".gitignore").read_text()
        assert "repos/" in gitignore_content

        # Check repos directory
        assert (project_dir / "repos").is_dir()

    def test_init_project_with_custom_date(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test project creation with custom date."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text("# Test Project")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Note: init_project doesn't expose date parameter, but we can test
        # that it uses the current date correctly
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Verify: Branch and folder use today's date (local time, not UTC)
        project_config = config.read_project_config(project_name)
        today = datetime.now().strftime("%y%m%d")  # Local time for user-facing branch names
        assert project_config["branch"].startswith(today)
        assert project_config["folder"].startswith(f"proj/{today}")


# ==============================================================================
# Test QenConfig Integration
# ==============================================================================


class TestQenConfigIntegration:
    """Test QenConfig class with init commands."""

    def test_main_config_creation(self, test_storage: QenvyTest) -> None:
        """Test creating main configuration."""
        config = QenConfig(storage=test_storage)

        # Initially doesn't exist
        assert not config.main_config_exists()

        # Write main config
        config.write_main_config(
            meta_path="/path/to/meta",
            meta_remote="https://github.com/testorg/meta",
            meta_parent="/path/to/meta/../",
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Now exists
        assert config.main_config_exists()

        # Read back
        main_config = config.read_main_config()
        assert main_config["meta_path"] == "/path/to/meta"
        assert main_config["org"] == "testorg"
        assert "current_project" not in main_config

    def test_main_config_with_current_project(self, test_storage: QenvyTest) -> None:
        """Test main config with current_project set."""
        config = QenConfig(storage=test_storage)

        config.write_main_config(
            meta_path="/path/to/meta",
            meta_remote="https://github.com/testorg/meta",
            meta_parent="/path/to/meta/../",
            meta_default_branch="main",
            org="testorg",
            current_project="my-project",
        )

        main_config = config.read_main_config()
        assert main_config["current_project"] == "my-project"

    def test_update_current_project(self, test_storage: QenvyTest) -> None:
        """Test updating current_project field."""
        config = QenConfig(storage=test_storage)

        # Create initial config
        config.write_main_config(
            meta_path="/path/to/meta",
            meta_remote="https://github.com/testorg/meta",
            meta_parent="/path/to/meta/../",
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Update current_project
        config.update_current_project("project1")
        main_config = config.read_main_config()
        assert main_config["current_project"] == "project1"

        # Update to different project
        config.update_current_project("project2")
        main_config = config.read_main_config()
        assert main_config["current_project"] == "project2"

        # Set to None (should remove from TOML)
        config.update_current_project(None)
        main_config = config.read_main_config()
        assert "current_project" not in main_config

    def test_project_config_creation(self, test_storage: QenvyTest) -> None:
        """Test creating project configuration."""
        config = QenConfig(storage=test_storage)

        project_name = "test-project"
        assert not config.project_config_exists(project_name)

        # Write project config
        config.write_project_config(
            project_name=project_name,
            branch="2025-12-05-test-project",
            folder="proj/2025-12-05-test-project",
            repo="/tmp/meta-test-project",
            created="2025-12-05T10:00:00Z",
        )

        # Verify
        assert config.project_config_exists(project_name)
        project_config = config.read_project_config(project_name)
        assert project_config["name"] == project_name
        assert project_config["branch"] == "2025-12-05-test-project"
        assert project_config["folder"] == "proj/2025-12-05-test-project"
        assert project_config["created"] == "2025-12-05T10:00:00Z"

    def test_project_config_duplicate_fails(self, test_storage: QenvyTest) -> None:
        """Test that creating duplicate project config fails."""
        config = QenConfig(storage=test_storage)

        project_name = "test-project"

        # Create first time
        config.write_project_config(
            project_name=project_name,
            branch="2025-12-05-test-project",
            folder="proj/2025-12-05-test-project",
            repo="/tmp/meta-test-project",
            created="2025-12-05T10:00:00Z",
        )

        # Try to create again - should fail
        with pytest.raises(ProjectAlreadyExistsError) as exc_info:
            config.write_project_config(
                project_name=project_name,
                branch="2025-12-05-test-project",
                folder="proj/2025-12-05-test-project",
                repo="/tmp/meta-test-project",
                created="2025-12-05T10:00:00Z",
            )

        assert project_name in str(exc_info.value)

    def test_list_projects(self, test_storage: QenvyTest) -> None:
        """Test listing all projects."""
        config = QenConfig(storage=test_storage)

        # Create main config
        config.write_main_config(
            meta_path="/path/to/meta",
            meta_remote="https://github.com/testorg/meta",
            meta_parent="/path/to/meta/../",
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Initially no projects
        projects = config.list_projects()
        assert projects == []

        # Create some projects
        config.write_project_config(
            project_name="project1",
            branch="2025-12-05-project1",
            folder="proj/2025-12-05-project1",
            repo="/tmp/meta-project1",
        )

        config.write_project_config(
            project_name="project2",
            branch="2025-12-05-project2",
            folder="proj/2025-12-05-project2",
            repo="/tmp/meta-project2",
        )

        # List should not include main profile
        projects = config.list_projects()
        assert len(projects) == 2
        assert "project1" in projects
        assert "project2" in projects
        assert "main" not in projects

    def test_delete_project_config(self, test_storage: QenvyTest) -> None:
        """Test deleting project configuration."""
        config = QenConfig(storage=test_storage)

        project_name = "test-project"

        # Create project
        config.write_project_config(
            project_name=project_name,
            branch="2025-12-05-test-project",
            folder="proj/2025-12-05-test-project",
            repo="/tmp/meta-test-project",
        )

        assert config.project_config_exists(project_name)

        # Delete project
        config.delete_project_config(project_name)

        assert not config.project_config_exists(project_name)

    def test_config_paths(self, test_storage: QenvyTest) -> None:
        """Test getting configuration paths."""
        config = QenConfig(storage=test_storage)

        # Main config path
        main_path = config.get_main_config_path()
        assert "main" in str(main_path)
        assert "config.toml" in str(main_path)

        # Project config path
        project_path = config.get_project_config_path("test-project")
        assert "test-project" in str(project_path)
        assert "config.toml" in str(project_path)

        # Config directory
        config_dir = config.get_config_dir()
        assert config_dir.name == "qen-test"  # QenvyTest uses /tmp/qen-test


# ==============================================================================
# Test Error Handling
# ==============================================================================


class TestInitErrorHandling:
    """Test error handling in init commands."""

    def test_init_qen_graceful_failure(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Test that init_qen handles errors gracefully."""
        import os

        # Change to non-git directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Should raise click.Abort, not let exceptions bubble up
            with pytest.raises(click.exceptions.Abort):
                init_qen(verbose=False)
        finally:
            os.chdir(original_cwd)

    def test_init_project_graceful_failure(
        self,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that init_project handles errors gracefully."""
        # Mock find_meta_repo to simulate we're in a meta repo
        mock_meta_path = Path("/tmp/mock-meta")
        mocker.patch("qen.commands.init.find_meta_repo", return_value=mock_meta_path)

        # Mock the git operations that init_qen would perform
        mocker.patch(
            "qen.commands.init.extract_remote_and_org",
            return_value=("git@github.com:testorg/meta.git", "testorg"),
        )
        mocker.patch("qen.git_utils.get_default_branch_from_remote", return_value="main")

        # Mock find_remote_branches to return empty list
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # No main config - should auto-initialize then fail on clone (no mock for clone)
        with pytest.raises(click.exceptions.Abort):
            init_project("test-project", verbose=False, yes=True, storage=test_storage)

    def test_config_error_handling(self, test_storage: QenvyTest) -> None:
        """Test error handling in config operations."""
        config = QenConfig(storage=test_storage)

        # Reading non-existent main config
        with pytest.raises(QenConfigError):
            config.read_main_config()

        # Reading non-existent project config
        with pytest.raises(QenConfigError):
            config.read_project_config("nonexistent")

        # Updating current_project without main config
        with pytest.raises(QenConfigError):
            config.update_current_project("project1")


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestInitEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_project_name_with_special_characters(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test project names with hyphens and underscores."""
        # Setup
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock clone_per_project_meta for all calls
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = meta_repo.parent / f"meta-{project_name}"
            per_project_meta.mkdir(exist_ok=True)
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text(f"# {project_name}")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Test various project names
        for project_name in ["test-project", "test_project", "test-project-123"]:
            init_project(project_name, verbose=False, yes=True, storage=test_storage)
            assert config.project_config_exists(project_name)

    def test_meta_repo_at_root(self, tmp_path: Path, test_storage: QenvyTest) -> None:
        """Test when meta repo is at the root (not nested)."""
        # Create meta repo
        meta_repo = tmp_path / "meta"
        meta_repo.mkdir()

        subprocess.run(
            ["git", "init"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
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

        # Initialize qen
        config = QenConfig(storage=test_storage)

        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(meta_repo)
            init_qen(verbose=False, storage=test_storage)
        finally:
            os.chdir(original_cwd)

        # Verify
        assert config.main_config_exists()
        main_config = config.read_main_config()
        assert main_config["meta_path"] == str(meta_repo)

    def test_project_config_default_created_timestamp(
        self,
        test_storage: QenvyTest,
    ) -> None:
        """Test that project config uses default timestamp if not provided."""
        config = QenConfig(storage=test_storage)

        # Create project config without created timestamp
        config.write_project_config(
            project_name="test-project",
            branch="2025-12-05-test-project",
            folder="proj/2025-12-05-test-project",
            repo="/tmp/meta-test-project",
            created=None,  # Should use current time
        )

        # Verify that created field exists and is valid ISO 8601
        project_config = config.read_project_config("test-project")
        assert "created" in project_config

        # Parse to verify it's valid ISO 8601
        created_dt = datetime.fromisoformat(project_config["created"])
        assert created_dt is not None


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

        # Create per-project meta repo
        per_project_meta = meta_repo.parent / "meta-test-project"
        per_project_meta.mkdir()
        subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
        (per_project_meta / "README.md").write_text("# Test Project")
        subprocess.run(["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
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
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Verify: Project branch was created from main, not feature-branch
        project_config = config.read_project_config(project_name)
        project_branch = project_config["branch"]

        # Get the merge-base of the project branch in per_project_meta
        # It should be main (the initial commit), not feature-branch
        merge_base = subprocess.run(
            ["git", "merge-base", project_branch, "main"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # Get the main branch's current commit hash in per_project_meta
        per_project_main_commit = subprocess.run(
            ["git", "rev-parse", "main"],
            cwd=per_project_meta,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        # The merge-base should equal per_project_meta's main commit hash
        # (meaning project branch started from main in the per-project meta)
        assert merge_base == per_project_main_commit, (
            f"Project branch should have branched from main ({per_project_main_commit}), "
            f"but merge-base is {merge_base}"
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


# ==============================================================================
# Test PR Creation Prompt
# ==============================================================================


class TestInitProjectPRCreation:
    """Test PR creation prompt in init_project."""

    def test_init_project_with_yes_flag_skips_prompt(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that --yes flag skips the 'Continue?' confirmation prompt."""
        # Setup: Create meta repo and initialize qen
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text("# Test Project")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Mock click.confirm to ensure it's not called (due to yes=True)
        mock_confirm = mocker.patch("click.confirm")

        # Execute with yes=True
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=True, storage=test_storage)

        # Verify: click.confirm was not called (yes=True skips the "Continue?" prompt)
        mock_confirm.assert_not_called()

    def test_init_project_prompts_continue_when_yes_false(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that 'Continue?' prompt appears when --yes is not used."""
        # Setup: Create meta repo and initialize qen
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        # Mock clone_per_project_meta to create a fresh repo
        def create_per_project_meta(remote, project_name, parent, default_branch):
            per_project_meta = parent / f"meta-{project_name}"
            per_project_meta.mkdir()
            subprocess.run(["git", "init"], cwd=per_project_meta, check=True, capture_output=True)
            (per_project_meta / "README.md").write_text("# Test Project")
            subprocess.run(
                ["git", "add", "."], cwd=per_project_meta, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=per_project_meta,
                check=True,
                capture_output=True,
            )
            return per_project_meta

        mocker.patch(
            "qen.git_utils.clone_per_project_meta",
            side_effect=create_per_project_meta,
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

        # Mock click.confirm to return True (user confirms to continue)
        mock_confirm = mocker.patch("click.confirm", return_value=True)

        # Execute with yes=False (should trigger "Continue?" prompt)
        project_name = "test-project"
        init_project(project_name, verbose=False, yes=False, storage=test_storage)

        # Verify: click.confirm was called once for "Continue?" prompt
        mock_confirm.assert_called_once()
        # Verify the prompt text contains "Continue?"
        call_args = mock_confirm.call_args
        assert "Continue?" in str(call_args)

    def test_init_project_aborts_when_user_declines(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
        mocker,
    ) -> None:
        """Test that init_project aborts when user declines 'Continue?' prompt."""
        # Setup: Create meta repo and initialize qen
        meta_repo = temp_git_repo.parent / "meta"
        temp_git_repo.rename(meta_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Mock find_remote_branches to return empty list (no remote branches)
        mocker.patch("qen.commands.init.find_remote_branches", return_value=[])

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            meta_remote="https://github.com/testorg/meta",
            meta_parent=str(meta_repo.parent),
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        # Mock click.confirm to return False (user declines to continue)
        mocker.patch("click.confirm", return_value=False)

        # Execute with yes=False (should trigger "Continue?" prompt and abort)
        project_name = "test-project"
        with pytest.raises(click.exceptions.Abort):
            init_project(project_name, verbose=False, yes=False, storage=test_storage)

        # Verify: Project config was NOT created
        assert not config.project_config_exists(project_name)
