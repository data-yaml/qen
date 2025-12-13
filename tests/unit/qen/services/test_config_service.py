"""
Tests for ConfigService.

Tests configuration service operations including:
- Service initialization
- Global config CRUD operations
- Project config CRUD operations
- Configuration field accessors
- Project listing and deletion
- Edge cases and error handling
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from qen.config import QenConfigError
from qen.services.config_service import ConfigService
from tests.unit.helpers.qenvy_test import QenvyTest


class TestConfigServiceInitialization:
    """Test ConfigService initialization and basic properties."""

    def test_init_with_test_storage(self, test_storage: QenvyTest) -> None:
        """Test initialization with in-memory storage backend."""
        service = ConfigService(storage=test_storage)
        assert service._qenvy is test_storage

    def test_init_with_config_dir(self, tmp_path: Path) -> None:
        """Test initialization with custom config directory."""
        custom_dir = tmp_path / "custom_config"
        service = ConfigService(config_dir=str(custom_dir))

        # Should use filesystem storage with custom directory
        assert service._qenvy is not None
        assert service.get_config_dir() == custom_dir

    def test_init_default(self) -> None:
        """Test initialization with default settings."""
        service = ConfigService()

        # Should use filesystem storage with default XDG directory
        assert service._qenvy is not None
        base_dir = service.get_config_dir()
        assert base_dir is not None
        assert "qen" in str(base_dir)

    def test_main_profile_constant(self) -> None:
        """Test MAIN_PROFILE constant is defined correctly."""
        assert ConfigService.MAIN_PROFILE == "main"


class TestGlobalConfigOperations:
    """Test global config CRUD operations."""

    def test_load_global_config_not_exists(self, test_storage: QenvyTest) -> None:
        """Test loading global config when it doesn't exist."""
        service = ConfigService(storage=test_storage)

        with pytest.raises(QenConfigError, match="does not exist"):
            service.load_global_config()

    def test_save_and_load_global_config(self, test_storage: QenvyTest) -> None:
        """Test saving and loading global config."""
        service = ConfigService(storage=test_storage)

        config = {
            "meta_path": "/path/to/meta",
            "meta_remote": "git@github.com:org/meta.git",
            "meta_parent": "/path/to/parent",
            "meta_default_branch": "main",
            "org": "test-org",
        }

        service.save_global_config(config)
        loaded = service.load_global_config()

        assert loaded["meta_path"] == "/path/to/meta"
        assert loaded["meta_remote"] == "git@github.com:org/meta.git"
        assert loaded["meta_parent"] == "/path/to/parent"
        assert loaded["meta_default_branch"] == "main"
        assert loaded["org"] == "test-org"

    def test_save_global_config_overwrites(self, test_storage: QenvyTest) -> None:
        """Test saving global config overwrites existing config."""
        service = ConfigService(storage=test_storage)

        # Save initial config
        config1 = {
            "meta_path": "/path/to/meta1",
            "org": "org1",
        }
        service.save_global_config(config1)

        # Save updated config
        config2 = {
            "meta_path": "/path/to/meta2",
            "org": "org2",
        }
        service.save_global_config(config2)

        # Should have latest values
        loaded = service.load_global_config()
        assert loaded["meta_path"] == "/path/to/meta2"
        assert loaded["org"] == "org2"


class TestProjectConfigOperations:
    """Test project config CRUD operations."""

    def test_load_project_config_not_exists(self, test_storage: QenvyTest) -> None:
        """Test loading project config when it doesn't exist."""
        service = ConfigService(storage=test_storage)

        with pytest.raises(QenConfigError, match="does not exist"):
            service.load_project_config("nonexistent")

    def test_save_and_load_project_config(self, test_storage: QenvyTest) -> None:
        """Test saving and loading project config."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }

        service.save_project_config("test", config)
        loaded = service.load_project_config("test")

        # Should have saved values plus auto-added fields
        assert loaded["name"] == "test"
        assert loaded["branch"] == "251210-test"
        assert loaded["folder"] == "proj/251210-test"
        assert loaded["repo"] == "/path/to/meta-test"
        assert "created" in loaded  # Auto-added timestamp

    def test_save_project_config_adds_name(self, test_storage: QenvyTest) -> None:
        """Test that save_project_config ensures name field matches project_name."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }

        service.save_project_config("myproject", config)
        loaded = service.load_project_config("myproject")

        assert loaded["name"] == "myproject"

    def test_save_project_config_adds_created(self, test_storage: QenvyTest) -> None:
        """Test that save_project_config adds created timestamp if not present."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }

        before = datetime.now(UTC)
        service.save_project_config("test", config)
        after = datetime.now(UTC)

        loaded = service.load_project_config("test")
        assert "created" in loaded

        # Parse and verify timestamp is reasonable
        created = datetime.fromisoformat(loaded["created"])
        assert before <= created <= after

    def test_save_project_config_preserves_created(self, test_storage: QenvyTest) -> None:
        """Test that save_project_config preserves existing created timestamp."""
        service = ConfigService(storage=test_storage)

        original_created = "2025-01-01T00:00:00Z"
        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
            "created": original_created,
        }

        service.save_project_config("test", config)
        loaded = service.load_project_config("test")

        assert loaded["created"] == original_created

    def test_save_project_config_updates_existing(self, test_storage: QenvyTest) -> None:
        """Test that save_project_config updates existing project."""
        service = ConfigService(storage=test_storage)

        # Create initial config
        config1 = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config1)

        # Update config
        config2 = {
            "branch": "251211-test",
            "folder": "proj/251211-test",
            "repo": "/path/to/meta-test-updated",
            "created": "2025-01-01T00:00:00Z",  # Should be preserved
        }
        service.save_project_config("test", config2)

        loaded = service.load_project_config("test")
        assert loaded["branch"] == "251211-test"
        assert loaded["folder"] == "proj/251211-test"
        assert loaded["repo"] == "/path/to/meta-test-updated"


class TestUpdateCurrentProject:
    """Test updating current_project field."""

    def test_update_current_project(self, test_storage: QenvyTest) -> None:
        """Test updating current_project field."""
        service = ConfigService(storage=test_storage)

        # Create global config without current_project
        config = {
            "meta_path": "/path/to/meta",
            "org": "test-org",
        }
        service.save_global_config(config)

        # Update current_project
        service.update_current_project("myproject")

        loaded = service.load_global_config()
        assert loaded["current_project"] == "myproject"

    def test_update_current_project_overwrites(self, test_storage: QenvyTest) -> None:
        """Test that update_current_project overwrites existing value."""
        service = ConfigService(storage=test_storage)

        # Create global config with current_project
        config = {
            "meta_path": "/path/to/meta",
            "org": "test-org",
            "current_project": "project1",
        }
        service.save_global_config(config)

        # Update to different project
        service.update_current_project("project2")

        loaded = service.load_global_config()
        assert loaded["current_project"] == "project2"

    def test_update_current_project_requires_main_config(self, test_storage: QenvyTest) -> None:
        """Test that update_current_project requires main config to exist."""
        service = ConfigService(storage=test_storage)

        with pytest.raises(QenConfigError, match="does not exist"):
            service.update_current_project("myproject")


class TestConfigFieldAccessors:
    """Test configuration field accessor methods."""

    def test_get_meta_path(self, test_storage: QenvyTest) -> None:
        """Test getting meta_path from global config."""
        service = ConfigService(storage=test_storage)

        config = {"meta_path": "/path/to/meta", "org": "test-org"}
        service.save_global_config(config)

        meta_path = service.get_meta_path()
        assert meta_path == Path("/path/to/meta")

    def test_get_meta_path_missing(self, test_storage: QenvyTest) -> None:
        """Test get_meta_path when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"org": "test-org"}
        service.save_global_config(config)

        with pytest.raises(QenConfigError, match="meta_path not found"):
            service.get_meta_path()

    def test_get_meta_remote(self, test_storage: QenvyTest) -> None:
        """Test getting meta_remote from global config."""
        service = ConfigService(storage=test_storage)

        config = {"meta_remote": "git@github.com:org/meta.git", "org": "test-org"}
        service.save_global_config(config)

        meta_remote = service.get_meta_remote()
        assert meta_remote == "git@github.com:org/meta.git"

    def test_get_meta_remote_missing(self, test_storage: QenvyTest) -> None:
        """Test get_meta_remote when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"org": "test-org"}
        service.save_global_config(config)

        with pytest.raises(QenConfigError, match="meta_remote not found"):
            service.get_meta_remote()

    def test_get_meta_parent(self, test_storage: QenvyTest) -> None:
        """Test getting meta_parent from global config."""
        service = ConfigService(storage=test_storage)

        config = {"meta_parent": "/path/to/parent", "org": "test-org"}
        service.save_global_config(config)

        meta_parent = service.get_meta_parent()
        assert meta_parent == Path("/path/to/parent")

    def test_get_meta_parent_missing(self, test_storage: QenvyTest) -> None:
        """Test get_meta_parent when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"org": "test-org"}
        service.save_global_config(config)

        with pytest.raises(QenConfigError, match="meta_parent not found"):
            service.get_meta_parent()


class TestProjectFieldAccessors:
    """Test project field accessor methods."""

    def test_get_project_repo_path(self, test_storage: QenvyTest) -> None:
        """Test getting project repo path."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        repo_path = service.get_project_repo_path("test")
        assert repo_path == Path("/path/to/meta-test")

    def test_get_project_repo_path_missing(self, test_storage: QenvyTest) -> None:
        """Test get_project_repo_path when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"branch": "251210-test", "folder": "proj/251210-test"}
        service.save_project_config("test", config)

        with pytest.raises(QenConfigError, match="repo not found"):
            service.get_project_repo_path("test")

    def test_get_project_branch(self, test_storage: QenvyTest) -> None:
        """Test getting project branch."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        branch = service.get_project_branch("test")
        assert branch == "251210-test"

    def test_get_project_branch_missing(self, test_storage: QenvyTest) -> None:
        """Test get_project_branch when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"folder": "proj/251210-test", "repo": "/path/to/meta-test"}
        service.save_project_config("test", config)

        with pytest.raises(QenConfigError, match="branch not found"):
            service.get_project_branch("test")

    def test_get_project_folder(self, test_storage: QenvyTest) -> None:
        """Test getting project folder."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        folder = service.get_project_folder("test")
        assert folder == "proj/251210-test"

    def test_get_project_folder_missing(self, test_storage: QenvyTest) -> None:
        """Test get_project_folder when field is missing."""
        service = ConfigService(storage=test_storage)

        config = {"branch": "251210-test", "repo": "/path/to/meta-test"}
        service.save_project_config("test", config)

        with pytest.raises(QenConfigError, match="folder not found"):
            service.get_project_folder("test")


class TestProjectManagement:
    """Test project listing and management operations."""

    def test_list_projects_empty(self, test_storage: QenvyTest) -> None:
        """Test listing projects when none exist."""
        service = ConfigService(storage=test_storage)

        projects = service.list_projects()
        assert projects == []

    def test_list_projects_single(self, test_storage: QenvyTest) -> None:
        """Test listing projects with one project."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        projects = service.list_projects()
        assert projects == ["test"]

    def test_list_projects_multiple(self, test_storage: QenvyTest) -> None:
        """Test listing projects with multiple projects."""
        service = ConfigService(storage=test_storage)

        for name in ["project1", "project2", "project3"]:
            config = {
                "branch": f"251210-{name}",
                "folder": f"proj/251210-{name}",
                "repo": f"/path/to/meta-{name}",
            }
            service.save_project_config(name, config)

        projects = service.list_projects()
        assert sorted(projects) == ["project1", "project2", "project3"]

    def test_list_projects_excludes_main(self, test_storage: QenvyTest) -> None:
        """Test that list_projects excludes main profile."""
        service = ConfigService(storage=test_storage)

        # Add main config
        service.save_global_config({"meta_path": "/path/to/meta", "org": "test-org"})

        # Add project config
        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        projects = service.list_projects()
        assert "main" not in projects
        assert "test" in projects

    def test_project_exists_true(self, test_storage: QenvyTest) -> None:
        """Test project_exists returns True when project exists."""
        service = ConfigService(storage=test_storage)

        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        assert service.project_exists("test") is True

    def test_project_exists_false(self, test_storage: QenvyTest) -> None:
        """Test project_exists returns False when project doesn't exist."""
        service = ConfigService(storage=test_storage)

        assert service.project_exists("nonexistent") is False

    def test_delete_project(self, test_storage: QenvyTest) -> None:
        """Test deleting a project."""
        service = ConfigService(storage=test_storage)

        # Create project
        config = {
            "branch": "251210-test",
            "folder": "proj/251210-test",
            "repo": "/path/to/meta-test",
        }
        service.save_project_config("test", config)

        # Verify it exists
        assert service.project_exists("test") is True

        # Delete it
        service.delete_project("test")

        # Verify it's gone
        assert service.project_exists("test") is False

    def test_delete_project_nonexistent(self, test_storage: QenvyTest) -> None:
        """Test deleting a project that does not exist."""
        service = ConfigService(storage=test_storage)

        # Should raise QenConfigError when project does not exist
        with pytest.raises(QenConfigError, match="Failed to delete"):
            service.delete_project("nonexistent")


class TestGetConfigDir:
    """Test get_config_dir method."""

    def test_get_config_dir(self, test_storage: QenvyTest) -> None:
        """Test getting configuration directory path."""
        service = ConfigService(storage=test_storage)
        config_dir = service.get_config_dir()

        assert isinstance(config_dir, Path)
        assert config_dir == Path("/tmp/qen-test")
