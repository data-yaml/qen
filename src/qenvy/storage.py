"""
Filesystem storage implementation for configuration management.

This module provides QenvyConfig, a concrete implementation of QenvyBase
that stores configurations in the filesystem using platformdirs for
platform-native directory resolution.
"""

import os
import tempfile
from pathlib import Path

from platformdirs import user_config_path

from .base import QenvyBase
from .exceptions import AtomicWriteError, BackupError, ProfileNotFoundError, StorageError
from .formats import get_format_handler
from .types import ProfileConfig


class QenvyConfig(QenvyBase):
    """Filesystem-based configuration storage using platformdirs.

    This class provides ONLY filesystem storage primitives. All business logic
    (validation, inheritance, profile management) is inherited from QenvyBase.

    Directory Structure (platform-specific via platformdirs):
        Linux:   ~/.config/{app_name}/
        macOS:   ~/Library/Application Support/{app_name}/
        Windows: %APPDATA%\\{app_name}\\

        Example structure:
        {config_dir}/
        ├── default/
        │   └── config.toml (or config.json)
        └── dev/
            └── config.toml (or config.json)

    Features:
        - Platform-native config directories (via platformdirs)
        - Respects XDG_CONFIG_HOME when set (Linux)
        - Atomic writes using temp files + rename
        - Automatic backups before overwriting
        - Pluggable format support (TOML, JSON)
    """

    def __init__(
        self,
        app_name: str,
        base_dir: Path | str | None = None,
        format: str = "toml",
        secure_fields: list[str] | None = None,
    ):
        """Initialize filesystem configuration storage.

        Args:
            app_name: Application name (used for directory name)
            base_dir: Base configuration directory (default: platform-native config dir)
            format: Configuration format ('toml' or 'json', default: 'toml')
            secure_fields: List of field paths that contain secrets

        Raises:
            FormatError: If format is not supported
        """
        super().__init__(secure_fields=secure_fields)
        self.app_name = app_name
        self.format_handler = get_format_handler(format)

        # Resolve base directory
        if base_dir is None:
            self.base_dir = user_config_path(app_name)
        else:
            self.base_dir = Path(base_dir)

        # Ensure base directory exists
        self._ensure_base_dir_exists()

    # ====================================================================
    # Storage Primitives Implementation
    # ====================================================================

    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read raw profile configuration from filesystem.

        Args:
            profile: Profile name

        Returns:
            Raw profile configuration

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If read operation fails
        """
        config_path = self._get_config_path(profile)

        if not config_path.exists():
            raise ProfileNotFoundError(profile, self._build_profile_not_found_error(profile))

        try:
            return self.format_handler.read(config_path)
        except Exception as e:
            raise StorageError("read", str(config_path), str(e)) from e

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write raw profile configuration to filesystem with atomic write.

        Args:
            profile: Profile name
            config: Configuration to write

        Raises:
            StorageError: If write operation fails
        """
        # Ensure profile directory exists
        profile_dir = self._get_profile_dir(profile)
        profile_dir.mkdir(parents=True, exist_ok=True)

        config_path = self._get_config_path(profile)

        # Create backup if file exists
        if config_path.exists():
            self._create_backup(config_path)

        # Atomic write using temp file + rename
        self._atomic_write(config_path, config)

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile directory and all contents.

        Args:
            profile: Profile name

        Raises:
            ProfileNotFoundError: If profile does not exist
            StorageError: If delete operation fails
        """
        profile_dir = self._get_profile_dir(profile)

        if not profile_dir.exists():
            raise ProfileNotFoundError(profile)

        try:
            # Remove entire profile directory
            for item in profile_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    # Recursively remove subdirectories
                    import shutil

                    shutil.rmtree(item)

            profile_dir.rmdir()
        except Exception as e:
            raise StorageError("delete", str(profile_dir), str(e)) from e

    def _list_profiles_raw(self) -> list[str]:
        """List all profiles by scanning filesystem.

        Returns:
            List of profile names
        """
        if not self.base_dir.exists():
            return []

        profiles = []
        for item in self.base_dir.iterdir():
            if item.is_dir():
                # Check if profile has a config file
                config_path = item / f"config{self.format_handler.get_extension()}"
                if config_path.exists():
                    profiles.append(item.name)

        return profiles

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists on filesystem.

        Args:
            profile: Profile name

        Returns:
            True if profile exists
        """
        config_path = self._get_config_path(profile)
        return config_path.exists()

    def _get_profile_path(self, profile: str) -> Path:
        """Get the configuration file path for a profile.

        Args:
            profile: Profile name

        Returns:
            Path to configuration file
        """
        return self._get_config_path(profile)

    # ====================================================================
    # Filesystem Helpers
    # ====================================================================

    def _ensure_base_dir_exists(self) -> None:
        """Ensure base configuration directory exists."""
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError("create directory", str(self.base_dir), str(e)) from e

    def _get_profile_dir(self, profile: str) -> Path:
        """Get the directory path for a profile.

        Args:
            profile: Profile name

        Returns:
            Path to profile directory
        """
        return self.base_dir / profile

    def _get_config_path(self, profile: str) -> Path:
        """Get the configuration file path for a profile.

        Args:
            profile: Profile name

        Returns:
            Path to configuration file
        """
        return self._get_profile_dir(profile) / f"config{self.format_handler.get_extension()}"

    def _create_backup(self, path: Path) -> None:
        """Create backup of existing file.

        Args:
            path: Path to file to backup

        Raises:
            BackupError: If backup creation fails
        """
        backup_path = path.with_suffix(path.suffix + ".backup")
        try:
            backup_path.write_bytes(path.read_bytes())
        except Exception as e:
            raise BackupError(str(path), str(e)) from e

    def _atomic_write(self, path: Path, config: ProfileConfig) -> None:
        """Atomically write configuration using temp file + rename.

        Args:
            path: Destination path
            config: Configuration to write

        Raises:
            AtomicWriteError: If atomic write fails
        """
        # Create temp file in same directory as target (ensures same filesystem)
        try:
            # Use a predictable temp file pattern for debugging
            temp_fd, temp_path_str = tempfile.mkstemp(
                suffix=self.format_handler.get_extension(),
                prefix=".config.tmp-",
                dir=path.parent,
                text=False,
            )
            temp_path = Path(temp_path_str)

            try:
                # Close fd immediately - format handler will reopen
                os.close(temp_fd)

                # Write to temp file
                self.format_handler.write(temp_path, config)

                # Atomic rename
                temp_path.replace(path)
            except Exception as e:
                # Clean up temp file on failure
                if temp_path.exists():
                    temp_path.unlink()
                raise e
        except Exception as e:
            raise AtomicWriteError(str(path), str(e)) from e

    # ====================================================================
    # Utility Methods
    # ====================================================================

    def get_base_dir(self) -> Path:
        """Get the base configuration directory.

        Returns:
            Path to base directory
        """
        return self.base_dir

    def get_profile_dir(self, profile: str) -> Path:
        """Get the directory for a specific profile.

        Args:
            profile: Profile name

        Returns:
            Path to profile directory
        """
        return self._get_profile_dir(profile)

    def get_config_path(self, profile: str) -> Path:
        """Get the configuration file path for a profile.

        Args:
            profile: Profile name

        Returns:
            Path to configuration file
        """
        return self._get_config_path(profile)
