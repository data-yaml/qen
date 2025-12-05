"""
Format handlers for configuration serialization.

This module provides pluggable format handlers for reading and writing
configuration files in different formats (TOML, JSON).
"""

import json

# Use built-in tomllib (Python 3.11+)
import tomllib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .exceptions import FormatError
from .types import ProfileConfig

# tomli_w is used for writing TOML regardless of Python version
try:
    import tomli_w
except ImportError:
    tomli_w = None  # type: ignore


class FormatHandler(ABC):
    """Abstract base class for format handlers.

    Format handlers are responsible for serializing and deserializing
    configuration data to/from specific file formats.
    """

    @abstractmethod
    def read(self, path: Path) -> ProfileConfig:
        """Read configuration from file.

        Args:
            path: Path to configuration file

        Returns:
            Parsed configuration

        Raises:
            FormatError: If parsing fails
        """
        ...

    @abstractmethod
    def write(self, path: Path, config: ProfileConfig) -> None:
        """Write configuration to file.

        Args:
            path: Path to configuration file
            config: Configuration to write

        Raises:
            FormatError: If serialization fails
        """
        ...

    @abstractmethod
    def get_extension(self) -> str:
        """Get the file extension for this format (e.g., '.toml', '.json')."""
        ...


class TOMLHandler(FormatHandler):
    """TOML format handler using tomllib/tomli for reading and tomli_w for writing."""

    def read(self, path: Path) -> ProfileConfig:
        """Read TOML configuration from file.

        Args:
            path: Path to TOML file

        Returns:
            Parsed configuration

        Raises:
            FormatError: If parsing fails
        """
        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise FormatError("TOML", f"Failed to read {path}: {e}") from e

    def write(self, path: Path, config: ProfileConfig) -> None:
        """Write TOML configuration to file.

        Args:
            path: Path to TOML file
            config: Configuration to write

        Raises:
            FormatError: If serialization fails or tomli_w not installed
        """
        if tomli_w is None:
            raise FormatError(
                "TOML",
                "tomli_w is required for writing TOML files. Install with: pip install tomli-w",
            )

        try:
            with open(path, "wb") as f:
                tomli_w.dump(config, f)
        except Exception as e:
            raise FormatError("TOML", f"Failed to write {path}: {e}") from e

    def get_extension(self) -> str:
        """Get TOML file extension."""
        return ".toml"


class JSONHandler(FormatHandler):
    """JSON format handler using standard library json module."""

    def __init__(self, indent: int = 4):
        """Initialize JSON handler.

        Args:
            indent: Number of spaces for indentation (default: 4)
        """
        self.indent = indent

    def read(self, path: Path) -> ProfileConfig:
        """Read JSON configuration from file.

        Args:
            path: Path to JSON file

        Returns:
            Parsed configuration

        Raises:
            FormatError: If parsing fails
        """
        try:
            with open(path, encoding="utf-8") as f:
                result: dict[str, Any] = json.load(f)
                return result
        except Exception as e:
            raise FormatError("JSON", f"Failed to read {path}: {e}") from e

    def write(self, path: Path, config: ProfileConfig) -> None:
        """Write JSON configuration to file.

        Args:
            path: Path to JSON file
            config: Configuration to write

        Raises:
            FormatError: If serialization fails
        """
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=self.indent, ensure_ascii=False)
                f.write("\n")  # Add trailing newline
        except Exception as e:
            raise FormatError("JSON", f"Failed to write {path}: {e}") from e

    def get_extension(self) -> str:
        """Get JSON file extension."""
        return ".json"


# Default format registry
DEFAULT_FORMATS: dict[str, FormatHandler] = {
    "toml": TOMLHandler(),
    "json": JSONHandler(),
}


def get_format_handler(format_name: str) -> FormatHandler:
    """Get format handler by name.

    Args:
        format_name: Format name ('toml' or 'json')

    Returns:
        Format handler instance

    Raises:
        FormatError: If format is not supported
    """
    handler = DEFAULT_FORMATS.get(format_name.lower())
    if handler is None:
        raise FormatError(
            format_name,
            f"Unsupported format: {format_name}. Supported formats: {', '.join(DEFAULT_FORMATS.keys())}",
        )
    return handler
