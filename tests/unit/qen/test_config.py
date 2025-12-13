"""
Tests for qen configuration management.

Tests configuration operations including:
- Config initialization and defaults
- Main config read/write operations
- Project config read/write operations
- Project listing and deletion
- Edge cases and error handling
- Integration with QenvyTest storage backend
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from qen.config import (
    ProjectAlreadyExistsError,
    QenConfig,
    QenConfigError,
)
from tests.unit.helpers.qenvy_test import QenvyTest


class TestConfigInitialization:
    """Test QenConfig initialization and basic properties."""

    def test_init_with_test_storage(self, test_storage: QenvyTest) -> None:
        """Test initialization with in-memory storage backend."""
        config = QenConfig(storage=test_storage)
        assert config._qenvy is test_storage

    def test_init_with_config_dir(self, tmp_path: Path) -> None:
        """Test initialization with custom config directory."""
        custom_dir = tmp_path / "custom_config"
        config = QenConfig(config_dir=str(custom_dir))

        # Should use filesystem storage with custom directory
        assert config._qenvy is not None
        assert config._qenvy.get_base_dir() == custom_dir

    def test_init_default(self) -> None:
        """Test initialization with default settings."""
        config = QenConfig()

        # Should use filesystem storage with default XDG directory
        assert config._qenvy is not None
        base_dir = config._qenvy.get_base_dir()
        assert base_dir is not None
        assert "qen" in str(base_dir)

    def test_main_profile_constant(self) -> None:
        """Test MAIN_PROFILE constant is defined correctly."""
        assert QenConfig.MAIN_PROFILE == "main"


class TestConfigPaths:
    """Test configuration path methods."""

    def test_get_config_dir(self, test_storage: QenvyTest) -> None:
        """Test getting configuration directory path."""
        config = QenConfig(storage=test_storage)
        config_dir = config.get_config_dir()

        assert isinstance(config_dir, Path)
        assert config_dir == Path("/tmp/qen-test")

    def test_get_main_config_path(self, test_storage: QenvyTest) -> None:
        """Test getting main configuration file path."""
        config = QenConfig(storage=test_storage)
        main_path = config.get_main_config_path()

        assert isinstance(main_path, Path)
        assert main_path == Path("/tmp/qen-test/main/config.toml")
        assert "main" in str(main_path)

    def test_get_project_config_path(self, test_storage: QenvyTest) -> None:
        """Test getting project configuration file path."""
        config = QenConfig(storage=test_storage)
        project_path = config.get_project_config_path("test-project")

        assert isinstance(project_path, Path)
        assert project_path == Path("/tmp/qen-test/test-project/config.toml")
        assert "test-project" in str(project_path)

    def test_get_project_config_path_special_chars(self, test_storage: QenvyTest) -> None:
        """Test getting project path with special characters in name."""
        config = QenConfig(storage=test_storage)
        project_path = config.get_project_config_path("my-project_123")

        assert isinstance(project_path, Path)
        assert "my-project_123" in str(project_path)


class TestConfigExistence:
    """Test configuration existence checking."""

    def test_main_config_exists_false(self, test_storage: QenvyTest) -> None:
        """Test main_config_exists returns False when not created."""
        config = QenConfig(storage=test_storage)
        assert not config.main_config_exists()

    def test_main_config_exists_true(self, test_storage: QenvyTest) -> None:
        """Test main_config_exists returns True after creation."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        assert config.main_config_exists()

    def test_project_config_exists_false(self, test_storage: QenvyTest) -> None:
        """Test project_config_exists returns False when not created."""
        config = QenConfig(storage=test_storage)
        assert not config.project_config_exists("nonexistent")

    def test_project_config_exists_true(self, test_storage: QenvyTest) -> None:
        """Test project_config_exists returns True after creation."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        assert config.project_config_exists("test-project")


class TestMainConfig:
    """Test main configuration read/write operations."""

    def test_write_main_config_minimal(self, test_storage: QenvyTest) -> None:
        """Test writing main config with required fields only."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        assert config.main_config_exists()

        # Verify stored data
        stored = test_storage.read_profile("main")
        assert stored["meta_path"] == "/tmp/meta"
        assert stored["org"] == "testorg"
        assert "current_project" not in stored  # Should not be present when None

    def test_write_main_config_with_current_project(self, test_storage: QenvyTest) -> None:
        """Test writing main config with current_project set."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "my-project",
        )

        stored = test_storage.read_profile("main")
        assert stored["meta_path"] == "/tmp/meta"
        assert stored["org"] == "testorg"
        assert stored["current_project"] == "my-project"

    def test_write_main_config_overwrite(self, test_storage: QenvyTest) -> None:
        """Test that write_main_config overwrites existing config."""
        config = QenConfig(storage=test_storage)

        # Write initial config
        config.write_main_config(
            "/tmp/meta1",
            "git@github.com:org1/meta.git",
            "/tmp/meta1/../",
            "main",
            "org1",
            "project1",
        )

        # Overwrite with new config
        config.write_main_config(
            "/tmp/meta2",
            "git@github.com:org2/meta.git",
            "/tmp/meta2/../",
            "main",
            "org2",
            "project2",
        )

        stored = test_storage.read_profile("main")
        assert stored["meta_path"] == "/tmp/meta2"
        assert stored["org"] == "org2"
        assert stored["current_project"] == "project2"

    def test_read_main_config_success(self, test_storage: QenvyTest) -> None:
        """Test reading main config successfully."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "my-project",
        )

        data = config.read_main_config()

        assert data["meta_path"] == "/tmp/meta"
        assert data["org"] == "testorg"
        assert data["current_project"] == "my-project"

    def test_read_main_config_not_exists(self, test_storage: QenvyTest) -> None:
        """Test reading main config when it doesn't exist raises error."""
        config = QenConfig(storage=test_storage)

        with pytest.raises(QenConfigError) as exc_info:
            config.read_main_config()

        assert "Failed to read main config" in str(exc_info.value)

    def test_write_main_config_error_handling(self, test_storage: QenvyTest, monkeypatch) -> None:
        """Test that write errors are wrapped in QenConfigError."""
        config = QenConfig(storage=test_storage)

        # Make create_profile raise an exception
        def mock_create_profile(*args, **kwargs):
            raise RuntimeError("Storage error")

        monkeypatch.setattr(test_storage, "create_profile", mock_create_profile)

        with pytest.raises(QenConfigError) as exc_info:
            config.write_main_config(
                "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
            )

        assert "Failed to write main config" in str(exc_info.value)


class TestCurrentProjectUpdate:
    """Test updating current_project field in main config."""

    def test_update_current_project_set(self, test_storage: QenvyTest) -> None:
        """Test setting current_project to a new value."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        config.update_current_project("new-project")

        data = config.read_main_config()
        assert data["current_project"] == "new-project"

    def test_update_current_project_change(self, test_storage: QenvyTest) -> None:
        """Test changing current_project to a different value."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "project1",
        )

        config.update_current_project("project2")

        data = config.read_main_config()
        assert data["current_project"] == "project2"

    def test_update_current_project_to_none(self, test_storage: QenvyTest) -> None:
        """Test clearing current_project by setting to None."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "my-project",
        )

        config.update_current_project(None)

        data = config.read_main_config()
        assert "current_project" not in data

    def test_update_current_project_already_none(self, test_storage: QenvyTest) -> None:
        """Test setting current_project to None when already None."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        config.update_current_project(None)

        data = config.read_main_config()
        assert "current_project" not in data

    def test_update_current_project_no_main_config(self, test_storage: QenvyTest) -> None:
        """Test updating current_project when main config doesn't exist."""
        config = QenConfig(storage=test_storage)

        with pytest.raises(QenConfigError) as exc_info:
            config.update_current_project("project")

        assert "Failed to update current_project" in str(exc_info.value)

    def test_update_current_project_error_handling(
        self, test_storage: QenvyTest, monkeypatch
    ) -> None:
        """Test error handling in update_current_project."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        # Make write_profile raise an exception
        def mock_write_profile(*args, **kwargs):
            raise RuntimeError("Write error")

        monkeypatch.setattr(test_storage, "write_profile", mock_write_profile)

        with pytest.raises(QenConfigError) as exc_info:
            config.update_current_project("project")

        assert "Failed to update current_project" in str(exc_info.value)


class TestProjectConfig:
    """Test project configuration read/write operations."""

    def test_write_project_config_minimal(self, test_storage: QenvyTest) -> None:
        """Test writing project config with required fields only."""
        config = QenConfig(storage=test_storage)

        # Capture time before writing
        before = datetime.now(UTC)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")
        after = datetime.now(UTC)

        assert config.project_config_exists("test-project")

        # Verify stored data
        stored = test_storage.read_profile("test-project")
        assert stored["name"] == "test-project"
        assert stored["branch"] == "main"
        assert stored["folder"] == "projects/test"

        # Verify timestamp is in range
        created_time = datetime.fromisoformat(stored["created"])
        assert before <= created_time <= after

    def test_write_project_config_with_created(self, test_storage: QenvyTest) -> None:
        """Test writing project config with explicit created timestamp."""
        config = QenConfig(storage=test_storage)
        custom_time = "2024-01-15T10:30:00+00:00"

        config.write_project_config(
            "test-project", "main", "projects/test", "/tmp/meta", created=custom_time
        )

        stored = test_storage.read_profile("test-project")
        assert stored["created"] == custom_time

    def test_write_project_config_already_exists(self, test_storage: QenvyTest) -> None:
        """Test that writing existing project raises ProjectAlreadyExistsError."""
        config = QenConfig(storage=test_storage)

        # Create project
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        # Try to create again
        with pytest.raises(ProjectAlreadyExistsError) as exc_info:
            config.write_project_config("test-project", "dev", "projects/test2", "/tmp/meta")

        assert exc_info.value.project_name == "test-project"
        assert "test-project" in exc_info.value.config_path
        assert "already exists" in str(exc_info.value)

    def test_write_project_config_multiple_projects(self, test_storage: QenvyTest) -> None:
        """Test writing multiple project configs."""
        config = QenConfig(storage=test_storage)

        config.write_project_config("project1", "main", "projects/project1", "/tmp/meta")
        config.write_project_config("project2", "dev", "projects/project2", "/tmp/meta")
        config.write_project_config("project3", "feature", "projects/project3", "/tmp/meta")

        assert config.project_config_exists("project1")
        assert config.project_config_exists("project2")
        assert config.project_config_exists("project3")

    def test_read_project_config_success(self, test_storage: QenvyTest) -> None:
        """Test reading project config successfully."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        data = config.read_project_config("test-project")

        assert data["name"] == "test-project"
        assert data["branch"] == "main"
        assert data["folder"] == "projects/test"
        assert "created" in data

    def test_read_project_config_not_exists(self, test_storage: QenvyTest) -> None:
        """Test reading project config when it doesn't exist."""
        config = QenConfig(storage=test_storage)

        with pytest.raises(QenConfigError) as exc_info:
            config.read_project_config("nonexistent")

        assert "Failed to read project config" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_write_project_config_special_chars(self, test_storage: QenvyTest) -> None:
        """Test writing project config with special characters in values."""
        config = QenConfig(storage=test_storage)

        config.write_project_config(
            "my-project_123",
            "feature/add-support",
            "projects/my-project_123",
            "/tmp/meta",
        )

        data = config.read_project_config("my-project_123")
        assert data["name"] == "my-project_123"
        assert data["branch"] == "feature/add-support"
        assert data["folder"] == "projects/my-project_123"


class TestListProjects:
    """Test listing project configurations."""

    def test_list_projects_empty(self, test_storage: QenvyTest) -> None:
        """Test listing projects when none exist."""
        config = QenConfig(storage=test_storage)
        projects = config.list_projects()

        assert projects == []

    def test_list_projects_excludes_main(self, test_storage: QenvyTest) -> None:
        """Test that list_projects excludes the main profile."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )

        projects = config.list_projects()

        assert "main" not in projects
        assert projects == []

    def test_list_projects_single(self, test_storage: QenvyTest) -> None:
        """Test listing projects with one project."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("project1", "main", "projects/project1", "/tmp/meta")

        projects = config.list_projects()

        assert projects == ["project1"]

    def test_list_projects_multiple(self, test_storage: QenvyTest) -> None:
        """Test listing projects with multiple projects."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("project1", "main", "projects/project1", "/tmp/meta")
        config.write_project_config("project2", "dev", "projects/project2", "/tmp/meta")
        config.write_project_config("project3", "feature", "projects/project3", "/tmp/meta")

        projects = config.list_projects()

        # Should be sorted
        assert projects == ["project1", "project2", "project3"]

    def test_list_projects_with_main_config(self, test_storage: QenvyTest) -> None:
        """Test listing projects when main config also exists."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )
        config.write_project_config("project1", "main", "projects/project1", "/tmp/meta")
        config.write_project_config("project2", "dev", "projects/project2", "/tmp/meta")

        projects = config.list_projects()

        assert "main" not in projects
        assert projects == ["project1", "project2"]


class TestDeleteProjectConfig:
    """Test deleting project configurations."""

    def test_delete_project_config_success(self, test_storage: QenvyTest) -> None:
        """Test deleting an existing project config."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        assert config.project_config_exists("test-project")

        config.delete_project_config("test-project")

        assert not config.project_config_exists("test-project")

    def test_delete_project_config_not_exists(self, test_storage: QenvyTest) -> None:
        """Test deleting a non-existent project config raises error."""
        config = QenConfig(storage=test_storage)

        # Should raise an error
        with pytest.raises(QenConfigError) as exc_info:
            config.delete_project_config("nonexistent")

        assert "Failed to delete project config" in str(exc_info.value)
        assert "nonexistent" in str(exc_info.value)

    def test_delete_project_config_multiple(self, test_storage: QenvyTest) -> None:
        """Test deleting one project doesn't affect others."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("project1", "main", "projects/project1", "/tmp/meta")
        config.write_project_config("project2", "dev", "projects/project2", "/tmp/meta")
        config.write_project_config("project3", "feature", "projects/project3", "/tmp/meta")

        config.delete_project_config("project2")

        assert config.project_config_exists("project1")
        assert not config.project_config_exists("project2")
        assert config.project_config_exists("project3")

    def test_delete_project_config_error_handling(
        self, test_storage: QenvyTest, monkeypatch
    ) -> None:
        """Test error handling in delete_project_config."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        # Make delete_profile raise an exception
        def mock_delete_profile(*args, **kwargs):
            raise RuntimeError("Delete error")

        monkeypatch.setattr(test_storage, "delete_profile", mock_delete_profile)

        with pytest.raises(QenConfigError) as exc_info:
            config.delete_project_config("test-project")

        assert "Failed to delete project config" in str(exc_info.value)
        assert "test-project" in str(exc_info.value)


class TestConfigIntegration:
    """Integration tests for QenConfig with complex workflows."""

    def test_complete_workflow(self, test_storage: QenvyTest) -> None:
        """Test a complete workflow: init, add projects, switch, delete."""
        config = QenConfig(storage=test_storage)

        # Initialize main config
        config.write_main_config(
            "/tmp/meta", "git@github.com:myorg/meta.git", "/tmp/meta/../", "main", "myorg"
        )
        assert config.main_config_exists()

        # Add projects
        config.write_project_config("proj1", "main", "projects/proj1", "/tmp/meta")
        config.write_project_config("proj2", "dev", "projects/proj2", "/tmp/meta")

        # Set current project
        config.update_current_project("proj1")
        main_config = config.read_main_config()
        assert main_config["current_project"] == "proj1"

        # List projects
        projects = config.list_projects()
        assert projects == ["proj1", "proj2"]

        # Switch current project
        config.update_current_project("proj2")
        main_config = config.read_main_config()
        assert main_config["current_project"] == "proj2"

        # Delete a project
        config.delete_project_config("proj1")
        projects = config.list_projects()
        assert projects == ["proj2"]

    def test_multiple_configs_independent(self, test_storage: QenvyTest) -> None:
        """Test that multiple QenConfig instances share storage correctly."""
        config1 = QenConfig(storage=test_storage)
        config2 = QenConfig(storage=test_storage)

        # Write with config1
        config1.write_main_config(
            "/tmp/meta", "git@github.com:testorg/meta.git", "/tmp/meta/../", "main", "testorg"
        )
        config1.write_project_config("project1", "main", "projects/project1", "/tmp/meta")

        # Read with config2
        assert config2.main_config_exists()
        assert config2.project_config_exists("project1")

        main_data = config2.read_main_config()
        assert main_data["org"] == "testorg"

        project_data = config2.read_project_config("project1")
        assert project_data["name"] == "project1"

    def test_isolated_storage_instances(self) -> None:
        """Test that different storage instances are isolated."""
        storage1 = QenvyTest()
        storage2 = QenvyTest()

        config1 = QenConfig(storage=storage1)
        config2 = QenConfig(storage=storage2)

        # Write to config1
        config1.write_main_config(
            "/tmp/meta1", "git@github.com:org1/meta.git", "/tmp/meta1/../", "main", "org1"
        )

        # Should not exist in config2
        assert config1.main_config_exists()
        assert not config2.main_config_exists()

    def test_edge_case_empty_string_values(self, test_storage: QenvyTest) -> None:
        """Test handling of empty string values."""
        config = QenConfig(storage=test_storage)

        # Empty strings should be allowed (validation is not enforced by Config)
        config.write_project_config("", "", "", "/tmp/meta")

        data = config.read_project_config("")
        assert data["name"] == ""
        assert data["branch"] == ""
        assert data["folder"] == ""

    def test_edge_case_long_values(self, test_storage: QenvyTest) -> None:
        """Test handling of very long string values."""
        config = QenConfig(storage=test_storage)

        long_name = "a" * 1000
        long_branch = "b" * 1000
        long_folder = "c" * 1000
        repo_path = "/fake/repo"

        config.write_project_config(long_name, long_branch, long_folder, repo_path)

        data = config.read_project_config(long_name)
        assert data["name"] == long_name
        assert data["branch"] == long_branch
        assert data["folder"] == long_folder


class TestExceptionTypes:
    """Test custom exception types and their behavior."""

    def test_qen_config_error_base(self) -> None:
        """Test QenConfigError is a proper exception."""
        error = QenConfigError("Test error")

        assert isinstance(error, Exception)
        assert str(error) == "Test error"

    def test_project_already_exists_error(self) -> None:
        """Test ProjectAlreadyExistsError attributes."""
        error = ProjectAlreadyExistsError("test-project", "/path/to/config")

        assert isinstance(error, QenConfigError)
        assert error.project_name == "test-project"
        assert error.config_path == "/path/to/config"
        assert "test-project" in str(error)
        assert "already exists" in str(error)
        assert "/path/to/config" in str(error)

    def test_project_already_exists_error_raised(self, test_storage: QenvyTest) -> None:
        """Test ProjectAlreadyExistsError is raised with correct attributes."""
        config = QenConfig(storage=test_storage)
        config.write_project_config("test-project", "main", "projects/test", "/tmp/meta")

        with pytest.raises(ProjectAlreadyExistsError) as exc_info:
            config.write_project_config("test-project", "dev", "projects/test2", "/tmp/meta")

        error = exc_info.value
        assert error.project_name == "test-project"
        assert "test-project" in error.config_path


class TestConfigOverrides:
    """Test runtime configuration overrides."""

    def test_meta_path_override(self, test_storage: QenvyTest) -> None:
        """Test meta_path_override parameter."""
        # Create config with stored meta_path
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/original/meta",
            "git@github.com:testorg/meta.git",
            "/original/meta/../",
            "main",
            "testorg",
        )

        # Create new config with override
        config_with_override = QenConfig(storage=test_storage, meta_path_override="/override/meta")

        main_config = config_with_override.read_main_config()
        assert main_config["meta_path"] == "/override/meta"
        assert main_config["org"] == "testorg"

        # Verify override is not persisted
        config_without_override = QenConfig(storage=test_storage)
        original_config = config_without_override.read_main_config()
        assert original_config["meta_path"] == "/original/meta"

    def test_current_project_override(self, test_storage: QenvyTest) -> None:
        """Test current_project_override parameter."""
        # Create config with stored current_project
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "original-proj",
        )

        # Create new config with override
        config_with_override = QenConfig(
            storage=test_storage, current_project_override="override-proj"
        )

        main_config = config_with_override.read_main_config()
        assert main_config["current_project"] == "override-proj"
        assert main_config["org"] == "testorg"

        # Verify override is not persisted
        config_without_override = QenConfig(storage=test_storage)
        original_config = config_without_override.read_main_config()
        assert original_config["current_project"] == "original-proj"

    def test_override_nonexistent_config(self, test_storage: QenvyTest) -> None:
        """Test overrides work even when main config doesn't exist."""
        # Don't create main config
        config = QenConfig(
            storage=test_storage,
            meta_path_override="/tmp/meta",
            current_project_override="test-proj",
        )

        # Should return dict with overrides even though main config doesn't exist
        main_config = config.read_main_config()
        assert main_config["meta_path"] == "/tmp/meta"
        assert main_config["current_project"] == "test-proj"

        # Verify nothing was persisted
        assert not config.main_config_exists()

    def test_combined_overrides(self, test_storage: QenvyTest) -> None:
        """Test multiple overrides applied together."""
        # Create config with stored values
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/original/meta",
            "git@github.com:testorg/meta.git",
            "/original/meta/../",
            "main",
            "testorg",
            "orig-proj",
        )

        # Create new config with both overrides
        config_with_overrides = QenConfig(
            storage=test_storage,
            meta_path_override="/override/meta",
            current_project_override="override-proj",
        )

        main_config = config_with_overrides.read_main_config()
        assert main_config["meta_path"] == "/override/meta"
        assert main_config["current_project"] == "override-proj"
        assert main_config["org"] == "testorg"

        # Verify overrides are not persisted
        config_without_override = QenConfig(storage=test_storage)
        original_config = config_without_override.read_main_config()
        assert original_config["meta_path"] == "/original/meta"
        assert original_config["current_project"] == "orig-proj"

    def test_override_with_path_object(self, test_storage: QenvyTest) -> None:
        """Test meta_path_override accepts Path objects."""
        from pathlib import Path

        config = QenConfig(storage=test_storage, meta_path_override=Path("/tmp/meta"))

        main_config = config.read_main_config()
        assert main_config["meta_path"] == "/tmp/meta"

    def test_override_none_values(self, test_storage: QenvyTest) -> None:
        """Test overrides with None values (no override)."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "proj",
        )

        # Create config with None overrides (should use stored values)
        config_no_override = QenConfig(
            storage=test_storage,
            meta_path_override=None,
            current_project_override=None,
        )

        main_config = config_no_override.read_main_config()
        assert main_config["meta_path"] == "/tmp/meta"
        assert main_config["current_project"] == "proj"

    def test_override_only_meta_path(self, test_storage: QenvyTest) -> None:
        """Test overriding only meta_path, leaving other values unchanged."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/original/meta",
            "git@github.com:testorg/meta.git",
            "/original/meta/../",
            "main",
            "testorg",
            "proj",
        )

        config_with_override = QenConfig(storage=test_storage, meta_path_override="/override/meta")

        main_config = config_with_override.read_main_config()
        assert main_config["meta_path"] == "/override/meta"
        assert main_config["current_project"] == "proj"
        assert main_config["org"] == "testorg"

    def test_override_only_current_project(self, test_storage: QenvyTest) -> None:
        """Test overriding only current_project, leaving other values unchanged."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            "/tmp/meta",
            "git@github.com:testorg/meta.git",
            "/tmp/meta/../",
            "main",
            "testorg",
            "orig",
        )

        config_with_override = QenConfig(storage=test_storage, current_project_override="override")

        main_config = config_with_override.read_main_config()
        assert main_config["meta_path"] == "/tmp/meta"
        assert main_config["current_project"] == "override"
        assert main_config["org"] == "testorg"

    def test_override_with_config_dir(self, test_storage: QenvyTest, tmp_path: Path) -> None:
        """Test overrides work with custom config_dir."""
        custom_dir = tmp_path / "custom_config"

        # Note: Can't use both storage and config_dir in real usage,
        # but test that parameters are accepted
        config = QenConfig(
            storage=test_storage,
            config_dir=str(custom_dir),
            meta_path_override="/override/meta",
        )

        # Override should work even with config_dir
        main_config = config.read_main_config()
        assert main_config["meta_path"] == "/override/meta"
