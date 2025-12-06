"""
Tests for qenvy format handlers.

Tests format handling including:
- TOML parsing and serialization
- JSON parsing and serialization
- Format error handling
- Format handler registry
"""

from pathlib import Path

import pytest

from qenvy.exceptions import FormatError
from qenvy.formats import (
    JSONHandler,
    TOMLHandler,
    get_format_handler,
)


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide temporary directory for test files."""
    return tmp_path


class TestTOMLHandler:
    """Test TOML format handler."""

    def test_toml_read_simple(self, temp_dir: Path) -> None:
        """Test reading simple TOML file."""
        toml_file = temp_dir / "test.toml"
        toml_file.write_text(
            """
            key = "value"
            number = 42
            """
        )

        handler = TOMLHandler()
        config = handler.read(toml_file)

        assert config["key"] == "value"
        assert config["number"] == 42

    def test_toml_read_nested(self, temp_dir: Path) -> None:
        """Test reading nested TOML structure."""
        toml_file = temp_dir / "nested.toml"
        toml_file.write_text(
            """
            [database]
            host = "localhost"
            port = 5432

            [database.options]
            ssl = true
            timeout = 30
            """
        )

        handler = TOMLHandler()
        config = handler.read(toml_file)

        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert config["database"]["options"]["ssl"] is True
        assert config["database"]["options"]["timeout"] == 30

    def test_toml_write_simple(self, temp_dir: Path) -> None:
        """Test writing simple TOML file."""
        toml_file = temp_dir / "output.toml"
        config = {
            "key": "value",
            "number": 42,
            "boolean": True,
        }

        handler = TOMLHandler()
        handler.write(toml_file, config)

        assert toml_file.exists()

        # Read back and verify
        loaded = handler.read(toml_file)
        assert loaded["key"] == "value"
        assert loaded["number"] == 42
        assert loaded["boolean"] is True

    def test_toml_write_nested(self, temp_dir: Path) -> None:
        """Test writing nested TOML structure."""
        toml_file = temp_dir / "nested.toml"
        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "options": {
                    "ssl": True,
                    "timeout": 30,
                },
            },
        }

        handler = TOMLHandler()
        handler.write(toml_file, config)

        loaded = handler.read(toml_file)
        assert loaded["database"]["host"] == "localhost"
        assert loaded["database"]["options"]["ssl"] is True

    def test_toml_roundtrip(self, temp_dir: Path) -> None:
        """Test TOML write/read roundtrip preserves data."""
        toml_file = temp_dir / "roundtrip.toml"
        original = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        handler = TOMLHandler()
        handler.write(toml_file, original)
        loaded = handler.read(toml_file)

        assert loaded == original

    def test_toml_read_invalid_file(self, temp_dir: Path) -> None:
        """Test reading invalid TOML raises FormatError."""
        toml_file = temp_dir / "invalid.toml"
        toml_file.write_text("this is not valid TOML {{{")

        handler = TOMLHandler()

        with pytest.raises(FormatError) as exc_info:
            handler.read(toml_file)

        assert exc_info.value.format_name == "TOML"
        assert "TOML" in str(exc_info.value)

    def test_toml_read_nonexistent_file(self, temp_dir: Path) -> None:
        """Test reading nonexistent file raises FormatError."""
        handler = TOMLHandler()

        with pytest.raises(FormatError):
            handler.read(temp_dir / "nonexistent.toml")

    def test_toml_get_extension(self) -> None:
        """Test TOML handler returns correct extension."""
        handler = TOMLHandler()
        assert handler.get_extension() == ".toml"


class TestJSONHandler:
    """Test JSON format handler."""

    def test_json_read_simple(self, temp_dir: Path) -> None:
        """Test reading simple JSON file."""
        json_file = temp_dir / "test.json"
        json_file.write_text(
            """
            {
                "key": "value",
                "number": 42
            }
            """
        )

        handler = JSONHandler()
        config = handler.read(json_file)

        assert config["key"] == "value"
        assert config["number"] == 42

    def test_json_read_nested(self, temp_dir: Path) -> None:
        """Test reading nested JSON structure."""
        json_file = temp_dir / "nested.json"
        json_file.write_text(
            """
            {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "options": {
                        "ssl": true,
                        "timeout": 30
                    }
                }
            }
            """
        )

        handler = JSONHandler()
        config = handler.read(json_file)

        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432
        assert config["database"]["options"]["ssl"] is True

    def test_json_write_simple(self, temp_dir: Path) -> None:
        """Test writing simple JSON file."""
        json_file = temp_dir / "output.json"
        config = {
            "key": "value",
            "number": 42,
            "boolean": True,
        }

        handler = JSONHandler()
        handler.write(json_file, config)

        assert json_file.exists()

        # Read back and verify
        loaded = handler.read(json_file)
        assert loaded["key"] == "value"
        assert loaded["number"] == 42
        assert loaded["boolean"] is True

    def test_json_write_formatted(self, temp_dir: Path) -> None:
        """Test that JSON is written with indentation."""
        json_file = temp_dir / "formatted.json"
        config = {"key": "value", "nested": {"key": "value"}}

        handler = JSONHandler(indent=2)
        handler.write(json_file, config)

        content = json_file.read_text()
        assert "\n" in content  # Should have newlines
        assert "  " in content  # Should have indentation

    def test_json_roundtrip(self, temp_dir: Path) -> None:
        """Test JSON write/read roundtrip preserves data."""
        json_file = temp_dir / "roundtrip.json"
        original = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        handler = JSONHandler()
        handler.write(json_file, original)
        loaded = handler.read(json_file)

        assert loaded == original

    def test_json_read_invalid_file(self, temp_dir: Path) -> None:
        """Test reading invalid JSON raises FormatError."""
        json_file = temp_dir / "invalid.json"
        json_file.write_text("{this is not valid JSON")

        handler = JSONHandler()

        with pytest.raises(FormatError) as exc_info:
            handler.read(json_file)

        assert exc_info.value.format_name == "JSON"
        assert "JSON" in str(exc_info.value)

    def test_json_read_nonexistent_file(self, temp_dir: Path) -> None:
        """Test reading nonexistent file raises FormatError."""
        handler = JSONHandler()

        with pytest.raises(FormatError):
            handler.read(temp_dir / "nonexistent.json")

    def test_json_get_extension(self) -> None:
        """Test JSON handler returns correct extension."""
        handler = JSONHandler()
        assert handler.get_extension() == ".json"

    def test_json_handler_custom_indent(self, temp_dir: Path) -> None:
        """Test JSON handler with custom indentation."""
        json_file = temp_dir / "custom_indent.json"
        config = {"key": {"nested": "value"}}

        handler = JSONHandler(indent=4)
        handler.write(json_file, config)

        content = json_file.read_text()
        assert "    " in content  # 4-space indentation

    def test_json_trailing_newline(self, temp_dir: Path) -> None:
        """Test that JSON files have trailing newline."""
        json_file = temp_dir / "newline.json"
        config = {"key": "value"}

        handler = JSONHandler()
        handler.write(json_file, config)

        content = json_file.read_text()
        assert content.endswith("\n")


class TestFormatRegistry:
    """Test format handler registry and factory."""

    def test_get_toml_handler(self) -> None:
        """Test getting TOML format handler."""
        handler = get_format_handler("toml")
        assert isinstance(handler, TOMLHandler)

    def test_get_json_handler(self) -> None:
        """Test getting JSON format handler."""
        handler = get_format_handler("json")
        assert isinstance(handler, JSONHandler)

    def test_get_handler_case_insensitive(self) -> None:
        """Test that format name is case-insensitive."""
        assert isinstance(get_format_handler("TOML"), TOMLHandler)
        assert isinstance(get_format_handler("Json"), JSONHandler)
        assert isinstance(get_format_handler("ToMl"), TOMLHandler)

    def test_get_unsupported_format(self) -> None:
        """Test that unsupported format raises FormatError."""
        with pytest.raises(FormatError) as exc_info:
            get_format_handler("yaml")

        assert exc_info.value.format_name == "yaml"
        assert "Unsupported format" in str(exc_info.value)
        assert "toml" in str(exc_info.value).lower()
        assert "json" in str(exc_info.value).lower()


class TestFormatHandlerInterface:
    """Test FormatHandler abstract interface."""

    def test_handler_has_read_method(self) -> None:
        """Test that format handlers implement read method."""
        toml_handler = TOMLHandler()
        json_handler = JSONHandler()

        assert hasattr(toml_handler, "read")
        assert callable(toml_handler.read)
        assert hasattr(json_handler, "read")
        assert callable(json_handler.read)

    def test_handler_has_write_method(self) -> None:
        """Test that format handlers implement write method."""
        toml_handler = TOMLHandler()
        json_handler = JSONHandler()

        assert hasattr(toml_handler, "write")
        assert callable(toml_handler.write)
        assert hasattr(json_handler, "write")
        assert callable(json_handler.write)

    def test_handler_has_get_extension_method(self) -> None:
        """Test that format handlers implement get_extension method."""
        toml_handler = TOMLHandler()
        json_handler = JSONHandler()

        assert hasattr(toml_handler, "get_extension")
        assert callable(toml_handler.get_extension)
        assert hasattr(json_handler, "get_extension")
        assert callable(json_handler.get_extension)


class TestFormatCompatibility:
    """Test compatibility between different formats."""

    def test_same_config_in_both_formats(self, temp_dir: Path) -> None:
        """Test that same config can be stored in both formats."""
        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
            },
            "debug": True,
            "items": [1, 2, 3],
        }

        toml_file = temp_dir / "config.toml"
        json_file = temp_dir / "config.json"

        toml_handler = TOMLHandler()
        json_handler = JSONHandler()

        # Write in both formats
        toml_handler.write(toml_file, config)
        json_handler.write(json_file, config)

        # Read back from both
        toml_loaded = toml_handler.read(toml_file)
        json_loaded = json_handler.read(json_file)

        # Both should match original
        assert toml_loaded == config
        assert json_loaded == config
        assert toml_loaded == json_loaded

    def test_unicode_in_both_formats(self, temp_dir: Path) -> None:
        """Test Unicode support in both formats."""
        config = {
            "message": "Hello, 世界! 🌍",
            "emoji": "🚀",
            "accents": "café naïve résumé",
        }

        toml_file = temp_dir / "unicode.toml"
        json_file = temp_dir / "unicode.json"

        toml_handler = TOMLHandler()
        json_handler = JSONHandler()

        toml_handler.write(toml_file, config)
        json_handler.write(json_file, config)

        toml_loaded = toml_handler.read(toml_file)
        json_loaded = json_handler.read(json_file)

        assert toml_loaded == config
        assert json_loaded == config


class TestFormatErrorMessages:
    """Test format error messages."""

    def test_format_error_includes_format_name(self) -> None:
        """Test that FormatError includes format name."""
        error = FormatError("TOML", "Test error message")
        assert "TOML" in str(error)
        assert error.format_name == "TOML"

    def test_format_error_includes_message(self) -> None:
        """Test that FormatError includes custom message."""
        error = FormatError("JSON", "Custom error message")
        assert "Custom error message" in str(error)

    def test_read_error_includes_path(self, temp_dir: Path) -> None:
        """Test that read errors include file path."""
        json_file = temp_dir / "error.json"
        json_file.write_text("{invalid json")

        handler = JSONHandler()

        try:
            handler.read(json_file)
            pytest.fail("Expected FormatError")
        except FormatError as e:
            error_msg = str(e)
            assert "error.json" in error_msg or str(json_file) in error_msg

    def test_write_error_includes_path(self, temp_dir: Path) -> None:
        """Test that write errors include file path."""
        # Create a directory where we expect a file
        bad_path = temp_dir / "directory"
        bad_path.mkdir()

        handler = TOMLHandler()

        try:
            # Try to write to a directory (should fail)
            handler.write(bad_path / "subdir" / "file.toml", {})
            pytest.fail("Expected FormatError")
        except FormatError as e:
            error_msg = str(e)
            # Error should mention the path or operation
            assert "file.toml" in error_msg or "Failed to write" in error_msg
