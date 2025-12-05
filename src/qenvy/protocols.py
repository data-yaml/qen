"""
Protocol definitions for qenvy.

This module defines protocols (structural interfaces) that define the contract
for storage implementations. Protocols enable dependency injection and testability.
"""

from typing import Protocol

from .types import ProfileConfig


class IConfigStorage(Protocol):
    """Protocol for configuration storage implementations.

    Defines the contract for storage backends (filesystem, database, etc.).
    All methods are "raw" primitives - no validation or business logic.
    """

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

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write raw profile configuration without validation.

        Args:
            profile: Profile name
            config: Configuration to write

        Raises:
            StorageError: If write operation fails
        """
        ...

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile and all associated data.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If delete operation fails
        """
        ...

    def _list_profiles_raw(self) -> list[str]:
        """List all profile names.

        Returns:
            List of profile names (may be empty)

        Raises:
            StorageError: If list operation fails
        """
        ...

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists.

        Args:
            profile: Profile name

        Returns:
            True if profile exists, False otherwise
        """
        ...
