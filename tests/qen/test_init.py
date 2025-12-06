"""Tests for qen init command.

Tests qen init functionality including:
- Meta repo discovery
- Organization extraction from git remotes
- Config creation and management
- Project initialization
- Error conditions
"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import click
import pytest

from qen.commands.init import init_project, init_qen
from qen.config import ProjectAlreadyExistsError, QenConfig, QenConfigError
from qen.git_utils import (
    AmbiguousOrgError,
    GitError,
    MetaRepoNotFoundError,
    NotAGitRepoError,
)
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
        assert "Extracting organization" in captured.out
        assert "Organization: testorg" in captured.out

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

        # Initialize qen config
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Execute: Create project
        project_name = "test-project"
        init_project(project_name, verbose=False, storage=test_storage)

        # Verify: Project config was created
        assert config.project_config_exists(project_name)
        project_config = config.read_project_config(project_name)
        assert project_config["name"] == project_name
        assert "branch" in project_config
        assert "folder" in project_config
        assert "created" in project_config

        # Verify: Project directory exists
        folder_path = Path(project_config["folder"])
        project_dir = meta_repo / folder_path
        assert project_dir.exists()
        assert (project_dir / "README.md").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / "repos").exists()
        assert (project_dir / ".gitignore").exists()

        # Verify: Current project was updated
        main_config = config.read_main_config()
        assert main_config["current_project"] == project_name

        # Verify: Branch was created
        result = subprocess.run(
            ["git", "branch", "--list", project_config["branch"]],
            cwd=meta_repo,
            capture_output=True,
            text=True,
        )
        assert project_config["branch"] in result.stdout

    def test_init_project_without_main_config(self, test_storage: QenvyTest) -> None:
        """Test that init_project fails without main config."""
        with pytest.raises(click.exceptions.Abort):
            init_project("test-project", verbose=False, storage=test_storage)

    def test_init_project_already_exists(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
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

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Create project first time
        project_name = "test-project"
        init_project(project_name, verbose=False, storage=test_storage)

        # Try to create again - should fail
        with pytest.raises(click.exceptions.Abort):
            init_project(project_name, verbose=False, storage=test_storage)

    def test_init_project_verbose_output(
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

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Execute with verbose=True
        init_project("test-project", verbose=True, storage=test_storage)

        # Verify: Verbose output was produced
        captured = capsys.readouterr()
        assert "Creating project: test-project" in captured.out
        assert "Meta repository:" in captured.out
        assert "Created branch:" in captured.out
        assert "Created directory:" in captured.out

    def test_init_project_creates_correct_structure(
        self,
        temp_git_repo: Path,
        test_storage: QenvyTest,
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

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Execute
        project_name = "test-project"
        init_project(project_name, verbose=False, storage=test_storage)

        # Verify: Check all files and their content
        project_config = config.read_project_config(project_name)
        project_dir = meta_repo / project_config["folder"]

        # Check README.md
        readme_content = (project_dir / "README.md").read_text()
        assert project_name in readme_content
        assert "qen clone" in readme_content

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

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Note: init_project doesn't expose date parameter, but we can test
        # that it uses the current date correctly
        project_name = "test-project"
        init_project(project_name, verbose=False, storage=test_storage)

        # Verify: Branch and folder use today's date
        project_config = config.read_project_config(project_name)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
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
            created="2025-12-05T10:00:00Z",
        )

        # Try to create again - should fail
        with pytest.raises(ProjectAlreadyExistsError) as exc_info:
            config.write_project_config(
                project_name=project_name,
                branch="2025-12-05-test-project",
                folder="proj/2025-12-05-test-project",
                created="2025-12-05T10:00:00Z",
            )

        assert project_name in str(exc_info.value)

    def test_list_projects(self, test_storage: QenvyTest) -> None:
        """Test listing all projects."""
        config = QenConfig(storage=test_storage)

        # Create main config
        config.write_main_config(
            meta_path="/path/to/meta",
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
        )

        config.write_project_config(
            project_name="project2",
            branch="2025-12-05-project2",
            folder="proj/2025-12-05-project2",
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
    ) -> None:
        """Test that init_project handles errors gracefully."""
        # No main config - should fail gracefully
        with pytest.raises(click.exceptions.Abort):
            init_project("test-project", verbose=False, storage=test_storage)

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

        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path=str(meta_repo),
            org="testorg",
            current_project=None,
        )

        # Test various project names
        for project_name in ["test-project", "test_project", "test-project-123"]:
            init_project(project_name, verbose=False, storage=test_storage)
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
            created=None,  # Should use current time
        )

        # Verify that created field exists and is valid ISO 8601
        project_config = config.read_project_config("test-project")
        assert "created" in project_config

        # Parse to verify it's valid ISO 8601
        created_dt = datetime.fromisoformat(project_config["created"])
        assert created_dt is not None
