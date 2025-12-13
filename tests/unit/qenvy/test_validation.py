"""
Tests for qenvy configuration validation.

Tests validation features including:
- Metadata validation
- Configuration structure validation
- Custom validators
- Validation error messages
"""

from pathlib import Path

import pytest

from qenvy.exceptions import ConfigValidationError
from qenvy.storage import QenvyConfig
from qenvy.types import ValidationResult


@pytest.fixture
def qenvy(tmp_path: Path) -> QenvyConfig:
    """Provide QenvyConfig instance with temporary directory."""
    return QenvyConfig("test-app", base_dir=tmp_path / "config")


class TestBasicValidation:
    """Test basic configuration validation."""

    def test_validate_empty_config(self, qenvy: QenvyConfig) -> None:
        """Test validating an empty configuration."""
        result = qenvy.validate_config({})
        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_simple_config(self, qenvy: QenvyConfig) -> None:
        """Test validating a simple valid configuration."""
        config = {
            "key": "value",
            "number": 42,
            "nested": {"key": "value"},
        }
        result = qenvy.validate_config(config)
        assert result.valid is True

    def test_validation_result_success(self) -> None:
        """Test ValidationResult.success() factory."""
        result = ValidationResult.success()
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_validation_result_failure(self) -> None:
        """Test ValidationResult.failure() factory."""
        result = ValidationResult.failure("error1", "error2")
        assert result.valid is False
        assert result.errors == ["error1", "error2"]


class TestInheritanceValidation:
    """Test validation of inheritance relationships."""

    def test_validate_valid_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test validating valid inheritance reference."""
        qenvy.create_profile("base", config={"key": "value"})

        config = {"inherits": "base"}
        result = qenvy.validate_config(config, profile="derived")

        assert result.valid is True

    def test_validate_nonexistent_parent(self, qenvy: QenvyConfig) -> None:
        """Test validation fails when parent profile doesn't exist."""
        config = {"inherits": "nonexistent"}
        result = qenvy.validate_config(config, profile="derived")

        assert result.valid is False
        assert any("does not exist" in err for err in result.errors)

    def test_validate_self_inheritance(self, qenvy: QenvyConfig) -> None:
        """Test validation fails for self-inheritance."""
        qenvy.create_profile("self", config={})

        config = {"inherits": "self"}
        result = qenvy.validate_config(config, profile="self")

        assert result.valid is False
        assert any("cannot inherit from itself" in err for err in result.errors)

    def test_validate_inherits_wrong_type(self, qenvy: QenvyConfig) -> None:
        """Test validation fails when 'inherits' is not a string."""
        config = {"inherits": 123}
        result = qenvy.validate_config(config)

        assert result.valid is False
        assert any("must be a string" in err for err in result.errors)

    def test_validate_inherits_list(self, qenvy: QenvyConfig) -> None:
        """Test validation fails when 'inherits' is a list."""
        config = {"inherits": ["base1", "base2"]}
        result = qenvy.validate_config(config)

        assert result.valid is False
        assert any("must be a string" in err for err in result.errors)


class TestMetadataValidation:
    """Test validation of _metadata field."""

    def test_validate_valid_metadata(self, qenvy: QenvyConfig) -> None:
        """Test validating valid metadata."""
        config = {
            "_metadata": {
                "created": "2024-01-01T00:00:00Z",
                "modified": "2024-01-01T00:00:00Z",
                "version": "1.0",
            },
        }
        result = qenvy.validate_config(config)

        assert result.valid is True

    def test_validate_metadata_not_dict(self, qenvy: QenvyConfig) -> None:
        """Test validation fails when _metadata is not a dict."""
        config = {"_metadata": "not a dict"}
        result = qenvy.validate_config(config)

        assert result.valid is False
        assert any("must be a dict" in err for err in result.errors)

    def test_validate_metadata_non_string_key(self, qenvy: QenvyConfig) -> None:
        """Test validation fails for non-string metadata keys."""
        config = {
            "_metadata": {
                123: "value",  # Non-string key
            },
        }
        result = qenvy.validate_config(config)

        assert result.valid is False
        assert any("must be string" in err for err in result.errors)

    def test_validate_metadata_complex_value(self, qenvy: QenvyConfig) -> None:
        """Test warning for complex metadata values."""
        config = {
            "_metadata": {
                "simple": "string",
                "complex": {"nested": "dict"},  # Complex type
            },
        }
        result = qenvy.validate_config(config)

        assert result.valid is True  # Still valid, just a warning
        assert len(result.warnings) > 0
        assert any("non-primitive" in warn for warn in result.warnings)


class TestReservedKeys:
    """Test validation of reserved key prefixes."""

    def test_underscore_prefix_warning(self, qenvy: QenvyConfig) -> None:
        """Test that underscore-prefixed keys generate warnings."""
        config = {
            "_custom_key": "value",
        }
        result = qenvy.validate_config(config)

        assert result.valid is True  # Valid but with warning
        assert len(result.warnings) > 0
        assert any("reserved prefix" in warn for warn in result.warnings)

    def test_metadata_key_allowed(self, qenvy: QenvyConfig) -> None:
        """Test that _metadata key doesn't generate warning."""
        config = {
            "_metadata": {
                "created": "2024-01-01T00:00:00Z",
            },
        }
        result = qenvy.validate_config(config)

        assert result.valid is True
        # Should not have warning about reserved prefix for _metadata
        assert not any(
            "_metadata" in warn and "reserved prefix" in warn for warn in result.warnings
        )

    def test_multiple_underscore_keys(self, qenvy: QenvyConfig) -> None:
        """Test multiple underscore-prefixed keys."""
        config = {
            "_key1": "value1",
            "_key2": "value2",
            "_metadata": {},  # This one is allowed
        }
        result = qenvy.validate_config(config)

        assert result.valid is True
        # Should have warnings for _key1 and _key2 but not _metadata
        underscore_warnings = [w for w in result.warnings if "reserved prefix" in w]
        assert len(underscore_warnings) == 2


class TestValidationOnWrite:
    """Test validation during profile write operations."""

    def test_write_with_validation_enabled(self, qenvy: QenvyConfig) -> None:
        """Test that validation runs by default on write."""
        qenvy.create_profile("base", config={"key": "value"})

        # This should succeed
        qenvy.write_profile("test", {"inherits": "base"}, validate=True)

        assert qenvy.profile_exists("test")

    def test_write_with_validation_disabled(self, qenvy: QenvyConfig) -> None:
        """Test writing with validation disabled."""
        # This would normally fail validation but should succeed with validate=False
        config = {"inherits": 123}  # Invalid type

        qenvy.write_profile("test", config, validate=False)

        assert qenvy.profile_exists("test")

    def test_write_invalid_config_raises_error(self, qenvy: QenvyConfig) -> None:
        """Test that writing invalid config raises ConfigValidationError."""
        config = {"inherits": "nonexistent"}

        with pytest.raises(ConfigValidationError) as exc_info:
            qenvy.write_profile("test", config, validate=True)

        assert len(exc_info.value.errors) > 0
        assert any("does not exist" in err for err in exc_info.value.errors)

    def test_create_profile_validates_by_default(self, qenvy: QenvyConfig) -> None:
        """Test that create_profile validates configuration."""
        config = {"inherits": "nonexistent"}

        with pytest.raises(ConfigValidationError):
            qenvy.create_profile("test", config=config)

    def test_validation_error_message(self, qenvy: QenvyConfig) -> None:
        """Test ConfigValidationError message format."""
        config = {
            "inherits": 123,  # Invalid type
            "_invalid": "value",  # Reserved prefix
        }

        try:
            qenvy.write_profile("test", config, validate=True)
            pytest.fail("Expected ConfigValidationError")
        except ConfigValidationError as e:
            error_msg = str(e)
            assert "validation failed" in error_msg.lower()
            assert len(e.errors) > 0


class TestValidationResultMethods:
    """Test ValidationResult helper methods."""

    def test_add_error_marks_invalid(self) -> None:
        """Test that add_error marks result as invalid."""
        result = ValidationResult.success()
        assert result.valid is True

        result.add_error("Test error")

        assert result.valid is False
        assert "Test error" in result.errors

    def test_add_warning_keeps_valid(self) -> None:
        """Test that add_warning doesn't change validity."""
        result = ValidationResult.success()
        assert result.valid is True

        result.add_warning("Test warning")

        assert result.valid is True  # Still valid
        assert "Test warning" in result.warnings

    def test_multiple_errors(self) -> None:
        """Test accumulating multiple errors."""
        result = ValidationResult.success()

        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_error("Error 3")

        assert result.valid is False
        assert len(result.errors) == 3
        assert "Error 1" in result.errors
        assert "Error 2" in result.errors
        assert "Error 3" in result.errors


class TestComplexValidationScenarios:
    """Test complex validation scenarios."""

    def test_validate_nested_config_structure(self, qenvy: QenvyConfig) -> None:
        """Test validating complex nested configuration."""
        config = {
            "database": {
                "primary": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {
                        "username": "admin",
                        "password": "secret",
                    },
                },
                "replicas": [
                    {"host": "replica1", "port": 5432},
                    {"host": "replica2", "port": 5432},
                ],
            },
            "cache": {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                },
            },
        }

        result = qenvy.validate_config(config)
        assert result.valid is True

    def test_validate_with_all_data_types(self, qenvy: QenvyConfig) -> None:
        """Test validation with various data types."""
        config = {
            "string": "value",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        result = qenvy.validate_config(config)
        assert result.valid is True

    def test_validate_config_with_inheritance_and_metadata(self, qenvy: QenvyConfig) -> None:
        """Test validation of config with both inheritance and metadata."""
        qenvy.create_profile("base", config={"key": "value"})

        config = {
            "inherits": "base",
            "_metadata": {
                "created": "2024-01-01T00:00:00Z",
                "description": "Test profile",
            },
            "custom_key": "custom_value",
        }

        result = qenvy.validate_config(config, profile="test")
        assert result.valid is True

    def test_validate_multiple_errors(self, qenvy: QenvyConfig) -> None:
        """Test validation with multiple errors."""
        config = {
            "inherits": 123,  # Wrong type
            "_metadata": "not a dict",  # Wrong type
            "_custom": "reserved",  # Reserved prefix (warning)
        }

        result = qenvy.validate_config(config)

        assert result.valid is False
        assert len(result.errors) >= 2  # At least 2 errors
        assert len(result.warnings) >= 1  # At least 1 warning
