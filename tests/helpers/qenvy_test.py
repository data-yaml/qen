"""In-memory QenvyConfig implementation for testing.

Provides an in-memory storage backend that implements the same interface
as QenvyConfig but stores all data in dictionaries instead of files.

This eliminates the need to manipulate XDG_CONFIG_HOME or clear platformdirs caches.
"""

from pathlib import Path

from qenvy.base import QenvyBase
from qenvy.exceptions import ProfileNotFoundError
from qenvy.formats import TOMLHandler
from qenvy.types import ProfileConfig


class QenvyTest(QenvyBase):
    """In-memory configuration storage for testing.

    Extends QenvyBase with dict-based storage primitives.
    All business logic (validation, inheritance) is inherited from QenvyBase,
    ensuring identical behavior to the production filesystem implementation.

    Example:
        ```python
        storage = QenvyTest()

        # Write and read profiles
        storage.write_profile("test", {"key": "value"})
        config = storage.read_profile("test")

        # Clear all data after test
        storage.clear()
        ```
    """

    def __init__(self, app_name: str = "qen", format: str = "toml"):
        """Initialize in-memory storage.

        Args:
            app_name: Application name (for compatibility)
            format: Configuration format (for compatibility)
        """
        self.app_name = app_name
        self.format_handler = TOMLHandler() if format == "toml" else None
        self._profiles: dict[str, ProfileConfig] = {}

    def clear(self) -> None:
        """Clear all stored data (useful for test cleanup)."""
        self._profiles.clear()

    # Public methods for compatibility with QenvyConfig

    def get_base_dir(self) -> Path:
        """Return a fake base directory for compatibility.

        Returns:
            Path to fake directory (not actually used)
        """
        return Path("/tmp/qen-test")

    def get_config_path(self, profile: str) -> Path:
        """Return a fake config path for compatibility.

        Args:
            profile: Profile name

        Returns:
            Path to fake config file (not actually used)
        """
        return Path(f"/tmp/qen-test/{profile}/config.toml")

    # Storage Primitives Implementation (In-Memory)

    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read raw profile from memory without validation.

        Args:
            profile: Profile name

        Returns:
            Deep copy of profile configuration

        Raises:
            ProfileNotFoundError: If profile not found
        """
        if profile not in self._profiles:
            raise ProfileNotFoundError(profile)

        # Return deep copy to prevent mutations
        import copy

        return copy.deepcopy(self._profiles[profile])

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write raw profile to memory without validation.

        Args:
            profile: Profile name
            config: Configuration to write
        """
        import copy

        self._profiles[profile] = copy.deepcopy(config)

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile from memory.

        Args:
            profile: Profile name
        """
        self._profiles.pop(profile, None)

    def _list_profiles_raw(self) -> list[str]:
        """List all profile names from memory.

        Returns:
            Sorted list of profile names
        """
        return sorted(self._profiles.keys())

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists in memory.

        Args:
            profile: Profile name

        Returns:
            True if profile exists
        """
        return profile in self._profiles

    def _get_profile_path(self, profile: str) -> Path:
        """Return a fake path for compatibility.

        Args:
            profile: Profile name

        Returns:
            Path to fake config file (not actually used)
        """
        return Path(f"/tmp/qen-test/{profile}/config.toml")
