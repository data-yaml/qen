"""Configuration management for qen using qenvy library.

This module provides qen-specific configuration management built on top of
the qenvy library. It handles:
- Main qen configuration (meta_path, org, current_project)
- Per-project configurations (name, branch, folder, created)
- XDG-compliant storage using qenvy
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qenvy import ProfileAlreadyExistsError, QenvyConfig
from qenvy.base import QenvyBase


class QenConfigError(Exception):
    """Base exception for qen configuration errors."""

    pass


class ProjectAlreadyExistsError(QenConfigError):
    """Raised when attempting to create a project that already exists."""

    def __init__(self, project_name: str, config_path: str):
        self.project_name = project_name
        self.config_path = config_path
        super().__init__(f"Project '{project_name}' already exists at {config_path}.")


class QenConfig:
    """Configuration manager for qen.

    Uses qenvy for XDG-compliant configuration storage.
    Stores configurations in $XDG_CONFIG_HOME/qen/:
    - main/config.toml: Main qen configuration
    - <project>/config.toml: Per-project configurations
    """

    MAIN_PROFILE = "main"

    def __init__(
        self,
        config_dir: Path | str | None = None,
        storage: QenvyBase | None = None,
        meta_path_override: Path | str | None = None,
        current_project_override: str | None = None,
    ):
        """Initialize qen configuration manager.

        Args:
            config_dir: Override default config directory (for testing)
            storage: Override storage backend (for testing with in-memory storage)
            meta_path_override: Runtime override for meta_path (not persisted)
            current_project_override: Runtime override for current_project (not persisted)
        """
        if storage is not None:
            # Use provided storage backend (for testing)
            self._qenvy = storage
        else:
            # Use default filesystem storage
            self._qenvy = QenvyConfig(
                app_name="qen",
                base_dir=config_dir,
                format="toml",
            )

        # Store runtime overrides (never persisted to disk)
        self._meta_path_override = Path(meta_path_override) if meta_path_override else None
        self._current_project_override = current_project_override

    def get_config_dir(self) -> Path:
        """Get the qen configuration directory.

        Returns:
            Path to configuration directory
        """
        from typing import cast

        return cast(Path, self._qenvy.get_base_dir())

    def get_main_config_path(self) -> Path:
        """Get path to main configuration file.

        Returns:
            Path to main config file
        """
        from typing import cast

        return cast(Path, self._qenvy.get_config_path(self.MAIN_PROFILE))

    def get_project_config_path(self, project_name: str) -> Path:
        """Get path to project configuration file.

        Args:
            project_name: Name of project

        Returns:
            Path to project config file
        """
        from typing import cast

        return cast(Path, self._qenvy.get_config_path(project_name))

    def main_config_exists(self) -> bool:
        """Check if main configuration exists.

        Returns:
            True if main config exists
        """
        return self._qenvy.profile_exists(self.MAIN_PROFILE)

    def project_config_exists(self, project_name: str) -> bool:
        """Check if project configuration exists.

        Args:
            project_name: Name of project

        Returns:
            True if project config exists
        """
        return self._qenvy.profile_exists(project_name)

    def read_main_config(self) -> dict[str, Any]:
        """Read main qen configuration with runtime overrides applied.

        Runtime overrides (meta_path_override, current_project_override) are applied
        to the returned config dict but never persisted to disk.

        Returns:
            Main configuration dictionary with overrides applied

        Raises:
            QenConfigError: If main config does not exist or read fails
        """
        try:
            # Read stored config
            if self.main_config_exists():
                config = self._qenvy.read_profile(self.MAIN_PROFILE, resolve_inheritance=False)
            else:
                # If no config exists and no overrides provided, raise error
                if not self._meta_path_override and not self._current_project_override:
                    raise QenConfigError(
                        "Failed to read main config: Main configuration does not exist"
                    )
                # Otherwise start with empty config (will be populated by overrides)
                config = {}

            # Apply runtime overrides (never persisted)
            if self._meta_path_override:
                config["meta_path"] = str(self._meta_path_override)
            if self._current_project_override:
                config["current_project"] = self._current_project_override

            return config
        except QenConfigError:
            # Re-raise QenConfigError without wrapping
            raise
        except Exception as e:
            raise QenConfigError(f"Failed to read main config: {e}") from e

    def write_main_config(
        self,
        meta_path: str,
        meta_remote: str,
        meta_parent: str,
        meta_default_branch: str,
        org: str,
        current_project: str | None = None,
    ) -> None:
        """Write main qen configuration.

        Args:
            meta_path: Path to meta repository
            meta_remote: Remote URL for cloning
            meta_parent: Parent directory for per-project clones
            meta_default_branch: Default branch (main/master)
            org: Organization name
            current_project: Current project name (optional)

        Raises:
            QenConfigError: If write fails
        """
        config: dict[str, Any] = {
            "meta_path": meta_path,
            "meta_remote": meta_remote,
            "meta_parent": meta_parent,
            "meta_default_branch": meta_default_branch,
            "org": org,
        }

        # Only include current_project if not None (TOML doesn't support null)
        if current_project is not None:
            config["current_project"] = current_project

        try:
            # Use create_profile with overwrite=True to allow updating
            self._qenvy.create_profile(self.MAIN_PROFILE, config, overwrite=True)
        except Exception as e:
            raise QenConfigError(f"Failed to write main config: {e}") from e

    def update_current_project(self, project_name: str | None) -> None:
        """Update the current_project field in main config.

        Args:
            project_name: Project name to set as current (or None to remove)

        Raises:
            QenConfigError: If update fails
        """
        try:
            config = self.read_main_config()
            # TOML doesn't support None, so remove key if None
            if project_name is None:
                config.pop("current_project", None)
            else:
                config["current_project"] = project_name
            self._qenvy.write_profile(
                self.MAIN_PROFILE, config, validate=True, update_metadata=True
            )
        except Exception as e:
            raise QenConfigError(f"Failed to update current_project: {e}") from e

    def read_project_config(self, project_name: str) -> dict[str, Any]:
        """Read project configuration.

        Args:
            project_name: Name of project

        Returns:
            Project configuration dictionary

        Raises:
            QenConfigError: If project config does not exist or read fails
        """
        try:
            return self._qenvy.read_profile(project_name, resolve_inheritance=False)
        except Exception as e:
            raise QenConfigError(f"Failed to read project config '{project_name}': {e}") from e

    def write_project_config(
        self,
        project_name: str,
        branch: str,
        folder: str,
        repo: str,
        created: str | None = None,
    ) -> None:
        """Write project configuration.

        Args:
            project_name: Name of project
            branch: Git branch name
            folder: Project folder path (relative to meta repo)
            repo: Absolute path to per-project meta clone
            created: ISO 8601 timestamp (default: current time)

        Raises:
            ProjectAlreadyExistsError: If project already exists
            QenConfigError: If write fails
        """
        # Check if project already exists
        if self.project_config_exists(project_name):
            config_path = self.get_project_config_path(project_name)
            raise ProjectAlreadyExistsError(project_name, str(config_path))

        # Use current time if not provided
        if created is None:
            created = datetime.now(UTC).isoformat()

        config = {
            "name": project_name,
            "branch": branch,
            "folder": folder,
            "repo": repo,
            "created": created,
        }

        try:
            self._qenvy.create_profile(project_name, config, overwrite=False)
        except ProfileAlreadyExistsError as e:
            # This should not happen because we checked above, but handle it
            config_path = self.get_project_config_path(project_name)
            raise ProjectAlreadyExistsError(project_name, str(config_path)) from e
        except Exception as e:
            raise QenConfigError(f"Failed to write project config '{project_name}': {e}") from e

    def list_projects(self) -> list[str]:
        """List all project names.

        Returns:
            List of project names (excluding main profile)
        """
        all_profiles = self._qenvy.list_profiles()
        return [p for p in all_profiles if p != self.MAIN_PROFILE]

    def delete_project_config(self, project_name: str) -> None:
        """Delete project configuration.

        Args:
            project_name: Name of project

        Raises:
            QenConfigError: If deletion fails
        """
        try:
            self._qenvy.delete_profile(project_name)
        except Exception as e:
            raise QenConfigError(f"Failed to delete project config '{project_name}': {e}") from e
