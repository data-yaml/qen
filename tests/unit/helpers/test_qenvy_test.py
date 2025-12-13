"""Tests for QenvyTest in-memory storage implementation."""

from tests.unit.helpers.qenvy_test import QenvyTest


def test_qenvy_test_basic_operations():
    """Test basic read/write/delete operations."""
    storage = QenvyTest()

    # Write a profile
    storage.write_profile("test", {"key": "value", "number": 42})

    # Read it back
    config = storage.read_profile("test")
    assert config["key"] == "value"
    assert config["number"] == 42

    # Check it exists
    assert storage.profile_exists("test")

    # List profiles
    assert "test" in storage.list_profiles()

    # Delete it
    storage.delete_profile("test")
    assert not storage.profile_exists("test")

    storage.clear()


def test_qenvy_test_isolation():
    """Test that changes don't affect original data."""
    storage = QenvyTest()

    # Write initial data
    original_data = {"key": "value"}
    storage.write_profile("test", original_data)

    # Modify the original
    original_data["key"] = "modified"

    # Read back should be unchanged
    config = storage.read_profile("test")
    assert config["key"] == "value"

    # Modify the read config
    config["new_key"] = "new_value"

    # Read again should still be unchanged
    config2 = storage.read_profile("test")
    assert "new_key" not in config2

    storage.clear()


def test_qenvy_test_multiple_profiles():
    """Test managing multiple profiles."""
    storage = QenvyTest()

    storage.write_profile("profile1", {"name": "Profile 1"})
    storage.write_profile("profile2", {"name": "Profile 2"})
    storage.write_profile("profile3", {"name": "Profile 3"})

    profiles = storage.list_profiles()
    assert len(profiles) == 3
    assert "profile1" in profiles
    assert "profile2" in profiles
    assert "profile3" in profiles

    storage.clear()


def test_qenvy_test_clear():
    """Test that clear() removes all data."""
    storage = QenvyTest()

    storage.write_profile("test1", {"key": "value1"})
    storage.write_profile("test2", {"key": "value2"})

    assert len(storage.list_profiles()) == 2

    storage.clear()

    assert len(storage.list_profiles()) == 0
    assert not storage.profile_exists("test1")
    assert not storage.profile_exists("test2")


def test_qenvy_test_metadata_handling():
    """Test that metadata is handled correctly."""
    storage = QenvyTest()

    # Write without metadata
    storage.write_profile("test", {"key": "value"})

    # Read back - should have metadata added
    config = storage.read_profile("test")
    assert "_metadata" in config
    assert "created" in config["_metadata"]
    assert "modified" in config["_metadata"]

    storage.clear()


def test_qenvy_test_compatibility_methods():
    """Test that compatibility methods return expected values."""
    storage = QenvyTest()

    # Test get_base_dir
    base_dir = storage.get_base_dir()
    assert base_dir.is_absolute()

    # Test get_config_path
    config_path = storage.get_config_path("test")
    assert config_path.is_absolute()
    assert "test" in str(config_path)
    assert config_path.suffix == ".toml"
