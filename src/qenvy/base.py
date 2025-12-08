"""
Abstract base class for configuration management with business logic.

This module provides QenvyBase, which contains ALL business logic for
configuration management including validation, inheritance, and profile operations.
Storage implementations only need to implement the raw storage primitives.
"""

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .exceptions import (
    CircularInheritanceError,
    ConfigValidationError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
)
from .types import (
    ConfigMetadata,
    MergeResult,
    ProfileConfig,
    ProfileInfo,
    ValidationResult,
)


class QenvyBase(ABC):
    """Abstract base class for configuration management.

    This class contains ALL business logic for profile management, validation,
    and inheritance. Subclasses only need to implement the raw storage primitives.

    The separation of concerns:
    - QenvyBase: Business logic, validation, inheritance, profile management
    - Subclasses: Storage primitives (filesystem, database, etc.)
    """

    def __init__(self, secure_fields: list[str] | None = None):
        """Initialize base configuration manager.

        Args:
            secure_fields: List of field paths that contain secrets
                          (e.g., ["api.key", "db.password"])
                          Used for documentation and validation, not storage decisions.
        """
        self.secure_fields = secure_fields or []

    # ====================================================================
    # Abstract Storage Primitives (to be implemented by subclasses)
    # ====================================================================

    @abstractmethod
    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read raw profile configuration without validation.

        Args:
            profile: Profile name

        Returns:
            Raw profile configuration

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If read operation fails
        """
        ...

    @abstractmethod
    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write raw profile configuration without validation.

        Args:
            profile: Profile name
            config: Configuration to write

        Raises:
            StorageError: If write operation fails
        """
        ...

    @abstractmethod
    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile and all associated data.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If delete operation fails
        """
        ...

    @abstractmethod
    def _list_profiles_raw(self) -> list[str]:
        """List all profile names.

        Returns:
            List of profile names (may be empty)

        Raises:
            StorageError: If list operation fails
        """
        ...

    @abstractmethod
    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        ...

    # ====================================================================
    # Public Profile Operations (with business logic)
    # ====================================================================

    def read_profile(self, profile: str, resolve_inheritance: bool = True) -> ProfileConfig:
        """Read profile configuration with optional inheritance resolution.

        Args:
            profile: Profile name
            resolve_inheritance: If True, resolve inheritance chain (default: True)

        Returns:
            Profile configuration (merged if inheritance is resolved)

        Raises:
            ProfileNotFoundError: If profile does not exist
            CircularInheritanceError: If circular inheritance is detected
            StorageError: If read operation fails
        """
        if not self._profile_exists_raw(profile):
            raise ProfileNotFoundError(profile, self._build_profile_not_found_error(profile))

        config = self._read_profile_raw(profile)

        if resolve_inheritance and "inherits" in config:
            merge_result = self._resolve_inheritance(profile)
            return merge_result.config

        return config

    def write_profile(
        self,
        profile: str,
        config: ProfileConfig,
        validate: bool = True,
        update_metadata: bool = True,
    ) -> None:
        """Write profile configuration with validation and metadata updates.

        Args:
            profile: Profile name
            config: Configuration to write
            validate: If True, validate configuration before writing (default: True)
            update_metadata: If True, update metadata timestamps (default: True)

        Raises:
            ConfigValidationError: If validation fails
            StorageError: If write operation fails
        """
        # Deep copy to avoid modifying caller's config
        config_copy = deepcopy(config)

        # Validate configuration
        if validate:
            validation = self.validate_config(config_copy, profile)
            if not validation.valid:
                raise ConfigValidationError(validation.errors)

        # Update metadata
        if update_metadata:
            config_copy = self._update_metadata(config_copy, profile)

        # Write to storage
        self._write_profile_raw(profile, config_copy)

    def create_profile(
        self,
        profile: str,
        config: ProfileConfig | None = None,
        overwrite: bool = False,
    ) -> None:
        """Create a new profile with optional initial configuration.

        Args:
            profile: Profile name
            config: Initial configuration (default: empty dict)
            overwrite: If True, overwrite existing profile (default: False)

        Raises:
            ProfileAlreadyExistsError: If profile exists and overwrite is False
            ConfigValidationError: If validation fails
            StorageError: If write operation fails
        """
        if not overwrite and self._profile_exists_raw(profile):
            raise ProfileAlreadyExistsError(profile)

        initial_config = config or {}
        self.write_profile(profile, initial_config, validate=True, update_metadata=True)

    def delete_profile(self, profile: str) -> None:
        """Delete a profile.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If delete operation fails
        """
        if not self._profile_exists_raw(profile):
            raise ProfileNotFoundError(profile)

        self._delete_profile_raw(profile)

    def list_profiles(self) -> list[str]:
        """List all available profiles.

        Returns:
            List of profile names (may be empty)
        """
        return sorted(self._list_profiles_raw())

    def profile_exists(self, profile: str) -> bool:
        """Check if a profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        return self._profile_exists_raw(profile)

    def get_profile_info(self, profile: str) -> ProfileInfo:
        """Get information about a profile.

        Args:
            profile: Profile name

        Returns:
            ProfileInfo with profile details
        """
        exists = self._profile_exists_raw(profile)
        config_path = self._get_profile_path(profile)

        metadata = None
        if exists:
            try:
                config = self._read_profile_raw(profile)
                metadata = config.get("_metadata")
            except Exception:
                pass  # Metadata is optional

        return ProfileInfo(
            name=profile,
            exists=exists,
            config_path=str(config_path),
            metadata=metadata,
        )

    # ====================================================================
    # Inheritance Resolution
    # ====================================================================

    def _resolve_inheritance(self, profile: str) -> MergeResult:
        """Resolve profile inheritance chain and merge configurations.

        Args:
            profile: Profile name

        Returns:
            MergeResult with merged configuration and inheritance chain

        Raises:
            ProfileNotFoundError: If any profile in chain does not exist
            CircularInheritanceError: If circular inheritance is detected
        """
        inheritance_chain: list[str] = []
        visited: set[str] = set()

        # Build inheritance chain (from base to derived)
        current = profile
        chain_stack: list[str] = []

        while True:
            if current in visited:
                raise CircularInheritanceError(current, chain_stack)

            visited.add(current)
            chain_stack.append(current)

            if not self._profile_exists_raw(current):
                raise ProfileNotFoundError(current, self._build_profile_not_found_error(current))

            config = self._read_profile_raw(current)
            parent = config.get("inherits")

            if not parent:
                # Reached base of inheritance chain
                break

            current = parent

        # Reverse to get base-to-derived order
        inheritance_chain = list(reversed(chain_stack))

        # Merge configurations from base to derived
        merged_config: ProfileConfig = {}
        merged_metadata: ConfigMetadata = {}

        for profile_name in inheritance_chain:
            config = self._read_profile_raw(profile_name)

            # Extract and merge metadata separately
            if "_metadata" in config:
                metadata = config.pop("_metadata")
                merged_metadata.update(metadata)

            # Deep merge configuration
            merged_config = self._deep_merge(merged_config, config)

        return MergeResult(
            config=merged_config,
            inheritance_chain=inheritance_chain,
            metadata=merged_metadata,
        )

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary (new instance)
        """
        result = deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dicts
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override value
                result[key] = deepcopy(value)

        return result

    # ====================================================================
    # Validation
    # ====================================================================

    def validate_config(
        self, config: ProfileConfig, profile: str | None = None
    ) -> ValidationResult:
        """Validate configuration structure and values.

        Args:
            config: Configuration to validate
            profile: Optional profile name for context

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult.success()

        # Check for reserved keys
        reserved_keys = {"_metadata"}
        for key in config.keys():
            if key.startswith("_") and key not in reserved_keys:
                result.add_warning(f"Key '{key}' starts with underscore (reserved prefix)")

        # Validate inheritance reference
        if "inherits" in config:
            parent = config["inherits"]
            if not isinstance(parent, str):
                result.add_error(f"'inherits' must be a string, got {type(parent).__name__}")
            elif profile and parent == profile:
                result.add_error(f"Profile '{profile}' cannot inherit from itself")
            elif parent and not self._profile_exists_raw(parent):
                result.add_error(f"Parent profile '{parent}' does not exist")

        # Validate metadata structure if present
        if "_metadata" in config:
            metadata = config["_metadata"]
            if not isinstance(metadata, dict):
                result.add_error(f"'_metadata' must be a dict, got {type(metadata).__name__}")
            else:
                # Validate metadata fields
                for key, value in metadata.items():
                    if not isinstance(key, str):
                        result.add_error(f"Metadata key must be string, got {type(key).__name__}")
                    if not isinstance(value, str | int | float | bool | type(None)):
                        result.add_warning(
                            f"Metadata value '{key}' has non-primitive type {type(value).__name__}"
                        )

        return result

    # ====================================================================
    # Metadata Management
    # ====================================================================

    def _update_metadata(self, config: ProfileConfig, profile: str) -> ProfileConfig:
        """Update configuration metadata with timestamps.

        Args:
            config: Configuration to update
            profile: Profile name

        Returns:
            Configuration with updated metadata (new instance)
        """
        config_copy = deepcopy(config)
        now = datetime.now(UTC).isoformat()

        if "_metadata" not in config_copy:
            config_copy["_metadata"] = {}

        metadata = config_copy["_metadata"]

        # Set created timestamp if not present
        if "created" not in metadata:
            metadata["created"] = now

        # Always update modified timestamp
        metadata["modified"] = now

        return config_copy

    # ====================================================================
    # Helper Methods
    # ====================================================================

    def _build_profile_not_found_error(self, profile: str) -> str:
        """Build helpful error message when profile is not found.

        Subclasses can override this to add context-specific information.

        Args:
            profile: Profile name that was not found

        Returns:
            Formatted error message
        """
        available = self._list_profiles_raw()
        if available:
            profiles_list = "\n".join(f"  - {p}" for p in sorted(available))
            return f"Profile not found: {profile}\n\nAvailable profiles:\n{profiles_list}"
        else:
            return f"Profile not found: {profile}\n\nNo profiles exist yet. Create one with create_profile()."

    @abstractmethod
    def _get_profile_path(self, profile: str) -> Any:
        """Get the path/identifier for a profile's configuration.

        This is used for informational purposes (e.g., ProfileInfo).
        The return type is Any to accommodate different storage backends.

        Args:
            profile: Profile name

        Returns:
            Path or identifier for the profile
        """
        ...

    @abstractmethod
    def get_base_dir(self) -> Any:
        """Get the base directory for configuration storage.

        Returns:
            Base directory path or identifier
        """
        ...

    def get_config_path(self, profile: str) -> Any:
        """Get the configuration path for a specific profile.

        Args:
            profile: Profile name

        Returns:
            Configuration path or identifier for the profile
        """
        return self._get_profile_path(profile)
