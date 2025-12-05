"""
Type definitions and data models for qenvy.

This module defines all type aliases, dataclasses, and TypedDicts used
throughout the qenvy library for type safety and clarity.
"""

from dataclasses import dataclass, field
from typing import Any, TypedDict

# Type alias for profile configuration - flexible dict structure
ProfileConfig = dict[str, Any]


class ConfigMetadata(TypedDict, total=False):
    """Metadata associated with a profile configuration.

    Attributes:
        created: ISO timestamp when profile was created
        modified: ISO timestamp when profile was last modified
        version: Configuration schema version
        description: Human-readable description of the profile
    """

    created: str
    modified: str
    version: str
    description: str


@dataclass
class ValidationResult:
    """Result of configuration validation.

    Attributes:
        valid: True if configuration is valid
        errors: List of error messages (validation failures)
        warnings: List of warning messages (non-critical issues)
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Add an error message and mark result as invalid."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(valid=True)

    @classmethod
    def failure(cls, *errors: str) -> "ValidationResult":
        """Create a failed validation result with error messages."""
        return cls(valid=False, errors=list(errors))


@dataclass
class ProfileInfo:
    """Information about a profile.

    Attributes:
        name: Profile name
        exists: True if profile exists
        config_path: Path to configuration file
        metadata: Profile metadata (if exists)
    """

    name: str
    exists: bool
    config_path: str
    metadata: ConfigMetadata | None = None


@dataclass
class MergeResult:
    """Result of merging configurations with inheritance.

    Attributes:
        config: Merged configuration
        inheritance_chain: List of profiles in inheritance order (base to derived)
        metadata: Merged metadata
    """

    config: ProfileConfig
    inheritance_chain: list[str]
    metadata: ConfigMetadata
