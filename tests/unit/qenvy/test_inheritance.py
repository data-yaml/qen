"""
Tests for qenvy profile inheritance.

Tests inheritance features including:
- Single-level inheritance
- Multi-level inheritance chains
- Circular inheritance detection
- Deep merge behavior
"""

from pathlib import Path

import pytest

from qenvy.exceptions import CircularInheritanceError, ProfileNotFoundError
from qenvy.storage import QenvyConfig


@pytest.fixture
def qenvy(tmp_path: Path) -> QenvyConfig:
    """Provide QenvyConfig instance with temporary directory."""
    return QenvyConfig("test-app", base_dir=tmp_path / "config")


class TestSingleLevelInheritance:
    """Test single-level profile inheritance."""

    def test_inherit_from_base_profile(self, qenvy: QenvyConfig) -> None:
        """Test inheriting configuration from a base profile."""
        # Create base profile
        base_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
            },
            "debug": False,
        }
        qenvy.create_profile("base", config=base_config)

        # Create derived profile
        dev_config = {
            "inherits": "base",
            "debug": True,
        }
        qenvy.create_profile("dev", config=dev_config)

        # Read with inheritance resolution
        resolved = qenvy.read_profile("dev", resolve_inheritance=True)

        assert resolved["database"]["host"] == "localhost"
        assert resolved["database"]["port"] == 5432
        assert resolved["debug"] is True  # Overridden

    def test_inherit_without_override(self, qenvy: QenvyConfig) -> None:
        """Test inheriting without overriding any values."""
        base_config = {"key1": "value1", "key2": "value2"}
        qenvy.create_profile("base", config=base_config)

        derived_config = {"inherits": "base"}
        qenvy.create_profile("derived", config=derived_config)

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["key1"] == "value1"
        assert resolved["key2"] == "value2"

    def test_inherit_adds_new_keys(self, qenvy: QenvyConfig) -> None:
        """Test that derived profile can add new keys."""
        base_config = {"existing": "value"}
        qenvy.create_profile("base", config=base_config)

        derived_config = {
            "inherits": "base",
            "new_key": "new_value",
        }
        qenvy.create_profile("derived", config=derived_config)

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["existing"] == "value"
        assert resolved["new_key"] == "new_value"

    def test_read_without_resolution(self, qenvy: QenvyConfig) -> None:
        """Test reading profile without resolving inheritance."""
        qenvy.create_profile("base", config={"base_key": "base_value"})

        derived_config = {
            "inherits": "base",
            "derived_key": "derived_value",
        }
        qenvy.create_profile("derived", config=derived_config)

        # Read without resolution
        raw = qenvy.read_profile("derived", resolve_inheritance=False)

        assert "inherits" in raw
        assert raw["inherits"] == "base"
        assert "derived_key" in raw
        assert "base_key" not in raw  # Not merged


class TestMultiLevelInheritance:
    """Test multi-level inheritance chains."""

    def test_two_level_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test two-level inheritance chain."""
        # Base profile
        qenvy.create_profile("base", config={"level": "base", "from_base": True})

        # Middle profile
        qenvy.create_profile(
            "middle",
            config={
                "inherits": "base",
                "level": "middle",
                "from_middle": True,
            },
        )

        # Derived profile
        qenvy.create_profile(
            "derived",
            config={
                "inherits": "middle",
                "level": "derived",
            },
        )

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["level"] == "derived"  # Most derived wins
        assert resolved["from_base"] is True
        assert resolved["from_middle"] is True

    def test_three_level_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test three-level inheritance chain."""
        qenvy.create_profile("base", config={"a": 1, "b": 1, "c": 1, "d": 1})
        qenvy.create_profile("middle1", config={"inherits": "base", "b": 2, "c": 2})
        qenvy.create_profile("middle2", config={"inherits": "middle1", "c": 3})
        qenvy.create_profile("derived", config={"inherits": "middle2", "d": 4})

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["a"] == 1  # From base
        assert resolved["b"] == 2  # From middle1
        assert resolved["c"] == 3  # From middle2
        assert resolved["d"] == 4  # From derived

    def test_inheritance_chain_order(self, qenvy: QenvyConfig) -> None:
        """Test that inheritance chain is resolved in correct order."""
        qenvy.create_profile("base", config={"value": "base"})
        qenvy.create_profile("middle", config={"inherits": "base", "value": "middle"})
        qenvy.create_profile("derived", config={"inherits": "middle"})

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        # Middle overrides base, derived inherits from middle
        assert resolved["value"] == "middle"


class TestDeepMerge:
    """Test deep merge behavior for nested dictionaries."""

    def test_deep_merge_nested_dicts(self, qenvy: QenvyConfig) -> None:
        """Test that nested dictionaries are deeply merged."""
        base_config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "options": {
                    "ssl": False,
                    "timeout": 30,
                },
            },
        }
        qenvy.create_profile("base", config=base_config)

        derived_config = {
            "inherits": "base",
            "database": {
                "host": "prod.example.com",
                "options": {
                    "ssl": True,
                },
            },
        }
        qenvy.create_profile("prod", config=derived_config)

        resolved = qenvy.read_profile("prod", resolve_inheritance=True)

        assert resolved["database"]["host"] == "prod.example.com"  # Overridden
        assert resolved["database"]["port"] == 5432  # Inherited
        assert resolved["database"]["options"]["ssl"] is True  # Overridden
        assert resolved["database"]["options"]["timeout"] == 30  # Inherited

    def test_deep_merge_preserves_types(self, qenvy: QenvyConfig) -> None:
        """Test that deep merge preserves value types."""
        base_config = {
            "settings": {
                "string": "base",
                "number": 42,
                "boolean": False,
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
            },
        }
        qenvy.create_profile("base", config=base_config)

        derived_config = {
            "inherits": "base",
            "settings": {
                "string": "derived",
                "list": [4, 5, 6],  # Lists are replaced, not merged
            },
        }
        qenvy.create_profile("derived", config=derived_config)

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["settings"]["string"] == "derived"
        assert resolved["settings"]["number"] == 42
        assert resolved["settings"]["boolean"] is False
        assert resolved["settings"]["list"] == [4, 5, 6]  # Replaced
        assert resolved["settings"]["dict"] == {"nested": "value"}

    def test_deep_merge_multiple_levels(self, qenvy: QenvyConfig) -> None:
        """Test deep merge across multiple inheritance levels."""
        qenvy.create_profile(
            "base",
            config={
                "config": {"a": 1, "b": {"x": 10, "y": 20}},
            },
        )

        qenvy.create_profile(
            "middle",
            config={
                "inherits": "base",
                "config": {"b": {"y": 25, "z": 30}},
            },
        )

        qenvy.create_profile(
            "derived",
            config={
                "inherits": "middle",
                "config": {"b": {"z": 35}, "c": 3},
            },
        )

        resolved = qenvy.read_profile("derived", resolve_inheritance=True)

        assert resolved["config"]["a"] == 1  # From base
        assert resolved["config"]["b"]["x"] == 10  # From base
        assert resolved["config"]["b"]["y"] == 25  # From middle
        assert resolved["config"]["b"]["z"] == 35  # From derived
        assert resolved["config"]["c"] == 3  # From derived


class TestCircularInheritance:
    """Test circular inheritance detection."""

    def test_direct_circular_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test detection of direct circular inheritance (A -> A)."""
        # Create profile with validation disabled to allow circular reference
        qenvy.write_profile("self", {"inherits": "self"}, validate=False)

        with pytest.raises(CircularInheritanceError) as exc_info:
            qenvy.read_profile("self", resolve_inheritance=True)

        assert exc_info.value.profile == "self"

    def test_two_profile_circular_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test detection of two-profile circular inheritance (A -> B -> A)."""
        # Create profiles with validation disabled to allow circular references
        qenvy.write_profile("a", {"inherits": "b"}, validate=False)
        qenvy.write_profile("b", {"inherits": "a"}, validate=False)

        with pytest.raises(CircularInheritanceError):
            qenvy.read_profile("a", resolve_inheritance=True)

    def test_three_profile_circular_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test detection of three-profile circular inheritance (A -> B -> C -> A)."""
        # Create profiles with validation disabled to allow circular references
        qenvy.write_profile("a", {"inherits": "b"}, validate=False)
        qenvy.write_profile("b", {"inherits": "c"}, validate=False)
        qenvy.write_profile("c", {"inherits": "a"}, validate=False)

        with pytest.raises(CircularInheritanceError):
            qenvy.read_profile("a", resolve_inheritance=True)


class TestInheritanceErrors:
    """Test error handling in inheritance resolution."""

    def test_inherit_from_nonexistent_profile(self, qenvy: QenvyConfig) -> None:
        """Test inheriting from nonexistent profile raises error."""
        # Create profile with validation disabled to allow nonexistent parent reference
        qenvy.write_profile("derived", {"inherits": "nonexistent"}, validate=False)

        with pytest.raises(ProfileNotFoundError) as exc_info:
            qenvy.read_profile("derived", resolve_inheritance=True)

        assert exc_info.value.profile == "nonexistent"

    def test_inherit_chain_with_missing_middle(self, qenvy: QenvyConfig) -> None:
        """Test inheritance chain with missing middle profile."""
        qenvy.create_profile("base", config={"key": "value"})
        # Create profile with validation disabled to allow nonexistent parent reference
        qenvy.write_profile("derived", {"inherits": "middle"}, validate=False)

        with pytest.raises(ProfileNotFoundError) as exc_info:
            qenvy.read_profile("derived", resolve_inheritance=True)

        assert exc_info.value.profile == "middle"


class TestInheritanceMetadata:
    """Test metadata handling in inheritance."""

    def test_metadata_not_inherited(self, qenvy: QenvyConfig) -> None:
        """Test that _metadata is not inherited from parent profiles."""
        qenvy.create_profile("base", config={"key": "base_value"})
        base_metadata_created = qenvy.read_profile("base")["_metadata"]["created"]

        # Wait a tiny bit to ensure different timestamp
        import time

        time.sleep(0.01)

        qenvy.create_profile("derived", config={"inherits": "base"})
        derived_config = qenvy.read_profile("derived", resolve_inheritance=False)
        derived_metadata_created = derived_config["_metadata"]["created"]

        # Metadata should be different
        assert derived_metadata_created != base_metadata_created

    def test_inheritance_field_preserved(self, qenvy: QenvyConfig) -> None:
        """Test that 'inherits' field is preserved in raw read."""
        qenvy.create_profile("base", config={"key": "value"})
        qenvy.create_profile("derived", config={"inherits": "base"})

        raw = qenvy.read_profile("derived", resolve_inheritance=False)

        assert "inherits" in raw
        assert raw["inherits"] == "base"

    def test_inheritance_field_removed_after_resolution(self, qenvy: QenvyConfig) -> None:
        """Test that 'inherits' field is removed after resolution."""
        qenvy.create_profile("base", config={"key": "value"})
        qenvy.create_profile("derived", config={"inherits": "base"})

        # The inherits field should not be in the resolved config
        # but should remain in the raw config on disk
        raw = qenvy.read_profile("derived", resolve_inheritance=False)
        assert "inherits" in raw


class TestComplexInheritanceScenarios:
    """Test complex real-world inheritance scenarios."""

    def test_environment_inheritance_pattern(self, qenvy: QenvyConfig) -> None:
        """Test typical environment inheritance pattern (base -> dev/stage/prod)."""
        # Base configuration
        qenvy.create_profile(
            "base",
            config={
                "app_name": "myapp",
                "log_level": "INFO",
                "database": {
                    "pool_size": 10,
                    "timeout": 30,
                },
            },
        )

        # Development environment
        qenvy.create_profile(
            "dev",
            config={
                "inherits": "base",
                "log_level": "DEBUG",
                "database": {
                    "host": "localhost",
                    "port": 5432,
                },
            },
        )

        # Production environment
        qenvy.create_profile(
            "prod",
            config={
                "inherits": "base",
                "log_level": "WARNING",
                "database": {
                    "host": "prod.example.com",
                    "port": 5432,
                    "pool_size": 50,  # Override for production
                },
            },
        )

        dev_config = qenvy.read_profile("dev", resolve_inheritance=True)
        prod_config = qenvy.read_profile("prod", resolve_inheritance=True)

        # Dev should have debug logging
        assert dev_config["log_level"] == "DEBUG"
        assert dev_config["database"]["host"] == "localhost"
        assert dev_config["database"]["pool_size"] == 10  # Inherited

        # Prod should have warning logging and larger pool
        assert prod_config["log_level"] == "WARNING"
        assert prod_config["database"]["host"] == "prod.example.com"
        assert prod_config["database"]["pool_size"] == 50  # Overridden

    def test_feature_flag_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test feature flag inheritance pattern."""
        qenvy.create_profile(
            "base",
            config={
                "features": {
                    "feature_a": False,
                    "feature_b": False,
                    "feature_c": False,
                },
            },
        )

        qenvy.create_profile(
            "experimental",
            config={
                "inherits": "base",
                "features": {
                    "feature_a": True,
                    "feature_b": True,
                },
            },
        )

        config = qenvy.read_profile("experimental", resolve_inheritance=True)

        assert config["features"]["feature_a"] is True  # Enabled
        assert config["features"]["feature_b"] is True  # Enabled
        assert config["features"]["feature_c"] is False  # Still disabled
