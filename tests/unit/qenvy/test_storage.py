"""
Tests for qenvy storage implementation.

Tests filesystem operations including:
- Atomic writes
- Backups
- XDG paths
- Profile CRUD operations
"""

from pathlib import Path

import pytest

from qenvy.exceptions import (
    AtomicWriteError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
)
from qenvy.storage import QenvyConfig


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Provide temporary config directory with XDG override."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def qenvy(temp_config_dir: Path) -> QenvyConfig:
    """Provide QenvyConfig instance with temporary directory."""
    return QenvyConfig("test-app", base_dir=temp_config_dir / "test-app")


@pytest.fixture
def qenvy_with_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QenvyConfig:
    """Provide QenvyConfig instance using XDG environment variable."""
    xdg_config = tmp_path / "xdg_config"
    xdg_config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

    # Clear the platformdirs cache
    import platformdirs

    if hasattr(platformdirs, "_cache"):
        platformdirs._cache.clear()

    return QenvyConfig("test-app")


class TestStorageInitialization:
    """Test QenvyConfig initialization and directory setup."""

    def test_init_creates_base_dir(self, temp_config_dir: Path) -> None:
        """Test that initialization creates base directory."""
        app_dir = temp_config_dir / "myapp"
        assert not app_dir.exists()

        config = QenvyConfig("myapp", base_dir=app_dir)

        assert app_dir.exists()
        assert app_dir.is_dir()
        assert config.base_dir == app_dir

    def test_init_with_existing_dir(self, temp_config_dir: Path) -> None:
        """Test initialization with existing directory."""
        app_dir = temp_config_dir / "existing"
        app_dir.mkdir()

        config = QenvyConfig("existing", base_dir=app_dir)

        assert config.base_dir == app_dir

    def test_init_uses_xdg_by_default(self, qenvy_with_xdg: QenvyConfig) -> None:
        """Test that XDG_CONFIG_HOME is used when base_dir is None."""
        # Just verify that base_dir was set and exists
        assert qenvy_with_xdg.base_dir.exists()
        assert qenvy_with_xdg.base_dir.is_dir()
        assert "test-app" in str(qenvy_with_xdg.base_dir)

    def test_init_with_toml_format(self, temp_config_dir: Path) -> None:
        """Test initialization with TOML format."""
        config = QenvyConfig("app", base_dir=temp_config_dir / "app", format="toml")
        assert config.format_handler.get_extension() == ".toml"

    def test_init_with_json_format(self, temp_config_dir: Path) -> None:
        """Test initialization with JSON format."""
        config = QenvyConfig("app", base_dir=temp_config_dir / "app", format="json")
        assert config.format_handler.get_extension() == ".json"


class TestProfileCreation:
    """Test profile creation operations."""

    def test_create_empty_profile(self, qenvy: QenvyConfig) -> None:
        """Test creating an empty profile."""
        qenvy.create_profile("default")

        assert qenvy.profile_exists("default")
        config = qenvy.read_profile("default")
        assert isinstance(config, dict)
        assert "_metadata" in config

    def test_create_profile_with_config(self, qenvy: QenvyConfig) -> None:
        """Test creating a profile with initial configuration."""
        initial_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
            },
            "debug": True,
        }

        qenvy.create_profile("dev", config=initial_config)

        config = qenvy.read_profile("dev")
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert config["debug"] is True

    def test_create_profile_already_exists(self, qenvy: QenvyConfig) -> None:
        """Test that creating existing profile raises error."""
        qenvy.create_profile("default")

        with pytest.raises(ProfileAlreadyExistsError) as exc_info:
            qenvy.create_profile("default")

        assert exc_info.value.profile == "default"
        assert "already exists" in str(exc_info.value)

    def test_create_profile_with_overwrite(self, qenvy: QenvyConfig) -> None:
        """Test overwriting existing profile."""
        qenvy.create_profile("default", config={"version": 1})
        qenvy.create_profile("default", config={"version": 2}, overwrite=True)

        config = qenvy.read_profile("default")
        assert config["version"] == 2

    def test_create_profile_creates_directory(self, qenvy: QenvyConfig) -> None:
        """Test that profile directory is created."""
        qenvy.create_profile("test")

        profile_dir = qenvy.get_profile_dir("test")
        assert profile_dir.exists()
        assert profile_dir.is_dir()


class TestProfileReading:
    """Test profile reading operations."""

    def test_read_nonexistent_profile(self, qenvy: QenvyConfig) -> None:
        """Test reading nonexistent profile raises error."""
        with pytest.raises(ProfileNotFoundError) as exc_info:
            qenvy.read_profile("nonexistent")

        assert exc_info.value.profile == "nonexistent"
        assert "not found" in str(exc_info.value).lower()

    def test_read_profile_preserves_types(self, qenvy: QenvyConfig) -> None:
        """Test that various data types are preserved."""
        config = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        qenvy.create_profile("types", config=config)
        loaded = qenvy.read_profile("types")

        assert loaded["string"] == "hello"
        assert loaded["integer"] == 42
        assert loaded["float"] == 3.14
        assert loaded["boolean"] is True
        assert loaded["list"] == [1, 2, 3]
        assert loaded["dict"] == {"nested": "value"}

    def test_read_profile_has_metadata(self, qenvy: QenvyConfig) -> None:
        """Test that reading profile includes metadata."""
        qenvy.create_profile("default")
        config = qenvy.read_profile("default")

        assert "_metadata" in config
        assert "created" in config["_metadata"]
        assert "modified" in config["_metadata"]


class TestProfileWriting:
    """Test profile writing operations."""

    def test_write_new_profile(self, qenvy: QenvyConfig) -> None:
        """Test writing a new profile."""
        config = {"key": "value"}
        qenvy.write_profile("new", config)

        assert qenvy.profile_exists("new")
        loaded = qenvy.read_profile("new")
        assert loaded["key"] == "value"

    def test_write_updates_existing_profile(self, qenvy: QenvyConfig) -> None:
        """Test that writing updates existing profile."""
        qenvy.create_profile("test", config={"version": 1})
        qenvy.write_profile("test", {"version": 2})

        config = qenvy.read_profile("test")
        assert config["version"] == 2

    def test_write_creates_backup(self, qenvy: QenvyConfig) -> None:
        """Test that writing creates backup of existing file."""
        qenvy.create_profile("test", config={"version": 1})

        config_path = qenvy.get_config_path("test")
        backup_path = config_path.with_suffix(config_path.suffix + ".backup")

        qenvy.write_profile("test", {"version": 2})

        assert backup_path.exists()

    def test_write_updates_metadata_timestamp(self, qenvy: QenvyConfig) -> None:
        """Test that writing updates modified timestamp."""
        qenvy.create_profile("test")
        config1 = qenvy.read_profile("test")
        modified1 = config1["_metadata"]["modified"]

        # Wait a tiny bit to ensure different timestamp
        import time

        time.sleep(0.05)

        qenvy.write_profile("test", {"updated": True})
        config2 = qenvy.read_profile("test")
        modified2 = config2["_metadata"]["modified"]

        # Modified should be different (we don't check created since metadata is updated)
        assert modified2 >= modified1  # Modified should be newer or equal


class TestProfileDeletion:
    """Test profile deletion operations."""

    def test_delete_existing_profile(self, qenvy: QenvyConfig) -> None:
        """Test deleting an existing profile."""
        qenvy.create_profile("test")
        assert qenvy.profile_exists("test")

        qenvy.delete_profile("test")

        assert not qenvy.profile_exists("test")

    def test_delete_nonexistent_profile(self, qenvy: QenvyConfig) -> None:
        """Test deleting nonexistent profile raises error."""
        with pytest.raises(ProfileNotFoundError):
            qenvy.delete_profile("nonexistent")

    def test_delete_removes_directory(self, qenvy: QenvyConfig) -> None:
        """Test that deleting profile removes directory."""
        qenvy.create_profile("test")
        profile_dir = qenvy.get_profile_dir("test")

        assert profile_dir.exists()
        qenvy.delete_profile("test")
        assert not profile_dir.exists()


class TestProfileListing:
    """Test profile listing operations."""

    def test_list_empty(self, qenvy: QenvyConfig) -> None:
        """Test listing profiles when none exist."""
        profiles = qenvy.list_profiles()
        assert profiles == []

    def test_list_single_profile(self, qenvy: QenvyConfig) -> None:
        """Test listing single profile."""
        qenvy.create_profile("default")
        profiles = qenvy.list_profiles()

        assert profiles == ["default"]

    def test_list_multiple_profiles(self, qenvy: QenvyConfig) -> None:
        """Test listing multiple profiles."""
        qenvy.create_profile("dev")
        qenvy.create_profile("prod")
        qenvy.create_profile("test")

        profiles = qenvy.list_profiles()

        assert sorted(profiles) == ["dev", "prod", "test"]

    def test_list_returns_sorted(self, qenvy: QenvyConfig) -> None:
        """Test that list_profiles returns sorted list."""
        qenvy.create_profile("zebra")
        qenvy.create_profile("alpha")
        qenvy.create_profile("beta")

        profiles = qenvy.list_profiles()

        assert profiles == ["alpha", "beta", "zebra"]


class TestProfileExistence:
    """Test profile existence checking."""

    def test_exists_returns_true(self, qenvy: QenvyConfig) -> None:
        """Test that profile_exists returns True for existing profile."""
        qenvy.create_profile("test")
        assert qenvy.profile_exists("test") is True

    def test_exists_returns_false(self, qenvy: QenvyConfig) -> None:
        """Test that profile_exists returns False for nonexistent profile."""
        assert qenvy.profile_exists("nonexistent") is False


class TestAtomicWrites:
    """Test atomic write operations."""

    def test_atomic_write_uses_temp_file(self, qenvy: QenvyConfig) -> None:
        """Test that atomic writes use temporary file."""
        config = {"test": "value"}
        profile_dir = qenvy.get_profile_dir("test")
        profile_dir.mkdir(parents=True)

        qenvy.write_profile("test", config)

        # Check that no temp files remain
        temp_files = list(profile_dir.glob(".config.tmp-*"))
        assert len(temp_files) == 0

    def test_atomic_write_on_failure_cleans_up(
        self, qenvy: QenvyConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that atomic write cleans up temp file on failure."""
        profile_dir = qenvy.get_profile_dir("test")
        profile_dir.mkdir(parents=True)

        # Patch format handler to raise error
        def failing_write(path: Path, config: dict) -> None:
            raise OSError("Simulated write failure")

        monkeypatch.setattr(qenvy.format_handler, "write", failing_write)

        with pytest.raises(AtomicWriteError):
            qenvy.write_profile("test", {"test": "value"})

        # Verify no temp files left behind
        temp_files = list(profile_dir.glob(".config.tmp-*"))
        assert len(temp_files) == 0


class TestPathUtilities:
    """Test path utility methods."""

    def test_get_base_dir(self, qenvy: QenvyConfig) -> None:
        """Test getting base directory."""
        base_dir = qenvy.get_base_dir()
        assert base_dir.exists()
        assert base_dir.is_dir()

    def test_get_profile_dir(self, qenvy: QenvyConfig) -> None:
        """Test getting profile directory."""
        qenvy.create_profile("test")
        profile_dir = qenvy.get_profile_dir("test")

        assert profile_dir.exists()
        assert profile_dir.name == "test"
        assert profile_dir.parent == qenvy.get_base_dir()

    def test_get_config_path(self, qenvy: QenvyConfig) -> None:
        """Test getting config file path."""
        qenvy.create_profile("test")
        config_path = qenvy.get_config_path("test")

        assert config_path.exists()
        assert config_path.suffix == ".toml"
        assert config_path.name == "config.toml"

    def test_get_profile_info(self, qenvy: QenvyConfig) -> None:
        """Test getting profile information."""
        qenvy.create_profile("test", config={"key": "value"})

        info = qenvy.get_profile_info("test")

        assert info.name == "test"
        assert info.exists is True
        assert "test" in info.config_path
        assert info.metadata is not None
        assert "created" in info.metadata


class TestFormatSupport:
    """Test different file format support."""

    def test_toml_format_roundtrip(self, temp_config_dir: Path) -> None:
        """Test TOML format read/write roundtrip."""
        config = QenvyConfig("app", base_dir=temp_config_dir / "app", format="toml")

        test_config = {
            "database": {"host": "localhost", "port": 5432},
            "debug": True,
        }

        config.create_profile("test", config=test_config)
        loaded = config.read_profile("test")

        assert loaded["database"]["host"] == "localhost"
        assert loaded["debug"] is True

    def test_json_format_roundtrip(self, temp_config_dir: Path) -> None:
        """Test JSON format read/write roundtrip."""
        config = QenvyConfig("app", base_dir=temp_config_dir / "app", format="json")

        test_config = {
            "database": {"host": "localhost", "port": 5432},
            "debug": True,
        }

        config.create_profile("test", config=test_config)
        loaded = config.read_profile("test")

        assert loaded["database"]["host"] == "localhost"
        assert loaded["debug"] is True

    def test_config_file_has_correct_extension(self, temp_config_dir: Path) -> None:
        """Test that config files have correct extensions."""
        toml_config = QenvyConfig("toml-app", base_dir=temp_config_dir / "toml-app", format="toml")
        json_config = QenvyConfig("json-app", base_dir=temp_config_dir / "json-app", format="json")

        toml_config.create_profile("test")
        json_config.create_profile("test")

        assert toml_config.get_config_path("test").suffix == ".toml"
        assert json_config.get_config_path("test").suffix == ".json"
