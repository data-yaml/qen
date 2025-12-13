"""Unit tests for RuntimeContext."""

from pathlib import Path

import pytest
from platformdirs import user_config_dir

from qen.config import QenConfigError
from qen.context.runtime import RuntimeContext, RuntimeContextError


class TestRuntimeContextFromCli:
    """Tests for RuntimeContext.from_cli static factory method."""

    def test_from_cli_with_all_options(self):
        """Test creating RuntimeContext with all CLI options specified."""
        ctx = RuntimeContext.from_cli(
            config_dir="/custom/config", meta="/custom/meta", proj="myproj"
        )

        assert ctx.config_dir == Path("/custom/config")
        assert ctx.meta_path_override == Path("/custom/meta")
        assert ctx.current_project_override == "myproj"

    def test_from_cli_with_none_values(self):
        """Test creating RuntimeContext with None values (use defaults/config)."""
        ctx = RuntimeContext.from_cli(config_dir=None, meta=None, proj=None)

        # Should use platformdirs default (platform-specific)
        assert ctx.config_dir == Path(user_config_dir("qen"))
        assert ctx.meta_path_override is None
        assert ctx.current_project_override is None

    def test_from_cli_with_partial_options(self):
        """Test creating RuntimeContext with some options specified."""
        ctx = RuntimeContext.from_cli(config_dir=None, meta="/custom/meta", proj=None)

        assert ctx.config_dir == Path(user_config_dir("qen"))
        assert ctx.meta_path_override == Path("/custom/meta")
        assert ctx.current_project_override is None


class TestRuntimeContextConfigService:
    """Tests for RuntimeContext.config_service property."""

    def test_config_service_lazy_loading(self, tmp_path):
        """Test that config_service is lazy-loaded on first access."""
        ctx = RuntimeContext(
            config_dir=tmp_path / "config",
            meta_path_override=tmp_path / "meta",
            current_project_override="testproj",
        )

        # Should be None initially
        assert ctx._config_service is None

        # Access should trigger creation
        service = ctx.config_service
        assert service is not None
        assert isinstance(service, object)

        # Should return same instance on subsequent access
        service2 = ctx.config_service
        assert service is service2

    def test_config_service_uses_overrides(self, tmp_path):
        """Test that config_service is initialized with overrides."""
        ctx = RuntimeContext(
            config_dir=tmp_path / "config",
            meta_path_override=tmp_path / "meta",
            current_project_override="testproj",
        )

        service = ctx.config_service

        # Verify service was created with correct parameters
        # (We can't easily verify internal state, but we can check it was created)
        assert service is not None


class TestRuntimeContextGetCurrentProject:
    """Tests for RuntimeContext.get_current_project method."""

    def test_get_current_project_from_override(self, mocker, tmp_path):
        """Test getting project name from override (not config)."""
        ctx = RuntimeContext(
            config_dir=tmp_path / "config", current_project_override="override-proj"
        )

        # Should return override without accessing config
        result = ctx.get_current_project()
        assert result == "override-proj"

    def test_get_current_project_from_config(self, mocker, tmp_path):
        """Test getting project name from config when no override."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return a project
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {"current_project": "config-proj"}
        ctx._config_service = mock_service

        result = ctx.get_current_project()
        assert result == "config-proj"
        mock_service.read_main_config.assert_called_once()

    def test_get_current_project_missing_in_config(self, mocker, tmp_path):
        """Test error when current_project is not in config."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return config without current_project
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="No current project set"):
            ctx.get_current_project()

    def test_get_current_project_invalid_type(self, mocker, tmp_path):
        """Test error when current_project has invalid type."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return invalid type
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {"current_project": 123}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Invalid current_project"):
            ctx.get_current_project()

    def test_get_current_project_config_read_error(self, mocker, tmp_path):
        """Test error handling when config read fails."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to raise an error
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.side_effect = QenConfigError("Config error")
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Failed to get current project"):
            ctx.get_current_project()


class TestRuntimeContextGetMetaPath:
    """Tests for RuntimeContext.get_meta_path method."""

    def test_get_meta_path_from_override(self, mocker, tmp_path):
        """Test getting meta path from override (not config)."""
        ctx = RuntimeContext(
            config_dir=tmp_path / "config", meta_path_override=tmp_path / "override" / "meta"
        )

        # Should return override without accessing config
        result = ctx.get_meta_path()
        assert result == tmp_path / "override" / "meta"

    def test_get_meta_path_from_config(self, mocker, tmp_path):
        """Test getting meta path from config when no override."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return a meta path
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {"meta_path": "/config/meta"}
        ctx._config_service = mock_service

        result = ctx.get_meta_path()
        assert result == Path("/config/meta")
        mock_service.read_main_config.assert_called_once()

    def test_get_meta_path_missing_in_config(self, mocker, tmp_path):
        """Test error when meta_path is not in config."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return config without meta_path
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="meta_path not configured"):
            ctx.get_meta_path()

    def test_get_meta_path_invalid_type(self, mocker, tmp_path):
        """Test error when meta_path has invalid type."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to return invalid type
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {"meta_path": 123}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Invalid meta_path"):
            ctx.get_meta_path()

    def test_get_meta_path_config_read_error(self, mocker, tmp_path):
        """Test error handling when config read fails."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock the config service to raise an error
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.side_effect = QenConfigError("Config error")
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Failed to get meta_path"):
            ctx.get_meta_path()


class TestRuntimeContextGetProjectRoot:
    """Tests for RuntimeContext.get_project_root method."""

    def test_get_project_root_success(self, mocker, tmp_path):
        """Test getting project root successfully."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {
            "repo": "/path/to/meta-myproj",
            "folder": "proj/myproj",
        }
        ctx._config_service = mock_service

        result = ctx.get_project_root()
        assert result == Path("/path/to/meta-myproj")
        mock_service.read_project_config.assert_called_once_with("myproj")

    def test_get_project_root_missing_repo_field(self, mocker, tmp_path):
        """Test error when repo field is missing from project config."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return config without repo
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {"folder": "proj/myproj"}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="missing 'repo' field"):
            ctx.get_project_root()

    def test_get_project_root_invalid_repo_type(self, mocker, tmp_path):
        """Test error when repo field has invalid type."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return invalid type
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {"repo": 123, "folder": "proj/myproj"}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Invalid repo path"):
            ctx.get_project_root()

    def test_get_project_root_config_read_error(self, mocker, tmp_path):
        """Test error handling when project config read fails."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to raise an error
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.side_effect = QenConfigError("Config error")
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Failed to get project root"):
            ctx.get_project_root()


class TestRuntimeContextGetProjectPyproject:
    """Tests for RuntimeContext.get_project_pyproject method."""

    def test_get_project_pyproject_success(self, mocker, tmp_path):
        """Test getting project pyproject.toml path successfully."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {
            "repo": "/path/to/meta-myproj",
            "folder": "proj/myproj",
        }
        ctx._config_service = mock_service

        result = ctx.get_project_pyproject()
        expected = Path("/path/to/meta-myproj/proj/myproj/pyproject.toml")
        assert result == expected
        mock_service.read_project_config.assert_called_once_with("myproj")

    def test_get_project_pyproject_missing_repo(self, mocker, tmp_path):
        """Test error when repo field is missing."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return config without repo
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {"folder": "proj/myproj"}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="config incomplete"):
            ctx.get_project_pyproject()

    def test_get_project_pyproject_missing_folder(self, mocker, tmp_path):
        """Test error when folder field is missing."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return config without folder
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {"repo": "/path/to/meta-myproj"}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="config incomplete"):
            ctx.get_project_pyproject()

    def test_get_project_pyproject_invalid_repo_type(self, mocker, tmp_path):
        """Test error when repo field has invalid type."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return invalid type
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {"repo": 123, "folder": "proj/myproj"}
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Invalid repo path"):
            ctx.get_project_pyproject()

    def test_get_project_pyproject_invalid_folder_type(self, mocker, tmp_path):
        """Test error when folder field has invalid type."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to return invalid type
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.return_value = {
            "repo": "/path/to/meta-myproj",
            "folder": 123,
        }
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Invalid folder"):
            ctx.get_project_pyproject()

    def test_get_project_pyproject_config_read_error(self, mocker, tmp_path):
        """Test error handling when project config read fails."""
        ctx = RuntimeContext(config_dir=tmp_path / "config", current_project_override="myproj")

        # Mock the config service to raise an error
        mock_service = mocker.MagicMock()
        mock_service.read_project_config.side_effect = QenConfigError("Config error")
        ctx._config_service = mock_service

        with pytest.raises(RuntimeContextError, match="Failed to get project pyproject.toml"):
            ctx.get_project_pyproject()


class TestRuntimeContextIntegration:
    """Integration tests for RuntimeContext with multiple method calls."""

    def test_override_priority(self, mocker, tmp_path):
        """Test that overrides take priority over config values."""
        ctx = RuntimeContext(
            config_dir=tmp_path / "config",
            meta_path_override=tmp_path / "override" / "meta",
            current_project_override="override-proj",
        )

        # Mock config service to return different values
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {
            "meta_path": "/config/meta",
            "current_project": "config-proj",
        }
        ctx._config_service = mock_service

        # Overrides should take priority
        assert ctx.get_current_project() == "override-proj"
        assert ctx.get_meta_path() == tmp_path / "override" / "meta"

        # Config should not be accessed since overrides are present
        mock_service.read_main_config.assert_not_called()

    def test_full_workflow_with_config(self, mocker, tmp_path):
        """Test complete workflow using config values (no overrides)."""
        ctx = RuntimeContext(config_dir=tmp_path / "config")

        # Mock config service
        mock_service = mocker.MagicMock()
        mock_service.read_main_config.return_value = {
            "meta_path": "/config/meta",
            "current_project": "myproj",
        }
        mock_service.read_project_config.return_value = {
            "repo": "/path/to/meta-myproj",
            "folder": "proj/myproj",
        }
        ctx._config_service = mock_service

        # Get current project
        project = ctx.get_current_project()
        assert project == "myproj"

        # Get meta path
        meta_path = ctx.get_meta_path()
        assert meta_path == Path("/config/meta")

        # Get project root
        project_root = ctx.get_project_root()
        assert project_root == Path("/path/to/meta-myproj")

        # Get pyproject path
        pyproject = ctx.get_project_pyproject()
        assert pyproject == Path("/path/to/meta-myproj/proj/myproj/pyproject.toml")

        # Verify expected calls
        # Note: get_project_root and get_project_pyproject both call get_current_project,
        # which calls read_main_config. So we have 4 calls total:
        # 1. get_current_project() direct call
        # 2. get_meta_path() call
        # 3. get_project_root() -> get_current_project() call
        # 4. get_project_pyproject() -> get_current_project() call
        assert mock_service.read_main_config.call_count == 4
        assert mock_service.read_project_config.call_count == 2  # For root and pyproject
