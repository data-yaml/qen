"""Configuration service for centralized config file operations.

This module provides the ConfigService class that centralizes all configuration
file operations using qenvy's ProfileStorage backend. It provides a clean API
for reading, writing, updating, and deleting both global and project configurations.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from qenvy import ProfileAlreadyExistsError, QenvyConfig
from qenvy.base import QenvyBase

from ..config import ProjectAlreadyExistsError, QenConfigError


class ConfigService:
    """Service for centralized configuration file operations.

    This class wraps qenvy's QenvyConfig to provide a clean, type-safe API for
    all configuration operations in qen. It handles both global qen configuration
    and per-project configurations.

    Attributes:
        MAIN_PROFILE: Profile name for main qen configuration ("main")
    """

    MAIN_PROFILE = "main"

    def __init__(
        self,
        config_dir: Path | str | None = None,
        storage: QenvyBase | None = None,
    ):
        """Initialize the configuration service.

        Args:
            config_dir: Override default config directory (for testing)
            storage: Override storage backend (for testing with in-memory storage)
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

    def get_config_dir(self) -> Path:
        """Get the qen configuration directory.

        Returns:
            Path to configuration directory
        """
        return cast(Path, self._qenvy.get_base_dir())

    def load_global_config(self) -> dict[str, Any]:
        """Load main qen configuration.

        Returns:
            Main configuration dictionary

        Raises:
            QenConfigError: If main config does not exist or read fails
        """
        try:
            if not self._qenvy.profile_exists(self.MAIN_PROFILE):
                raise QenConfigError("Main configuration does not exist. Run 'qen init' first.")
            return self._qenvy.read_profile(self.MAIN_PROFILE, resolve_inheritance=False)
        except QenConfigError:
            # Re-raise QenConfigError without wrapping
            raise
        except Exception as e:
            raise QenConfigError(f"Failed to read main config: {e}") from e

    def save_global_config(self, config: dict[str, Any]) -> None:
        """Save main qen configuration.

        Args:
            config: Configuration dictionary to save

        Raises:
            QenConfigError: If write fails
        """
        try:
            # Use create_profile with overwrite=True to allow updating
            self._qenvy.create_profile(self.MAIN_PROFILE, config, overwrite=True)
        except Exception as e:
            raise QenConfigError(f"Failed to write main config: {e}") from e

    def load_project_config(self, project_name: str) -> dict[str, Any]:
        """Load project configuration.

        Args:
            project_name: Name of project

        Returns:
            Project configuration dictionary

        Raises:
            QenConfigError: If project config does not exist or read fails
        """
        try:
            if not self._qenvy.profile_exists(project_name):
                raise QenConfigError(f"Project '{project_name}' does not exist")
            return self._qenvy.read_profile(project_name, resolve_inheritance=False)
        except QenConfigError:
            # Re-raise QenConfigError without wrapping
            raise
        except Exception as e:
            raise QenConfigError(f"Failed to read project config '{project_name}': {e}") from e

    def save_project_config(self, project_name: str, config: dict[str, Any]) -> None:
        """Save project configuration.

        Args:
            project_name: Name of project
            config: Configuration dictionary to save

        Raises:
            ProjectAlreadyExistsError: If project already exists and overwrite=False
            QenConfigError: If write fails
        """
        # Ensure name field matches project_name
        config["name"] = project_name

        # Add created timestamp if not present
        if "created" not in config:
            config["created"] = datetime.now(UTC).isoformat()

        try:
            # Check if project already exists
            if self._qenvy.profile_exists(project_name):
                # Update existing project
                self._qenvy.write_profile(project_name, config, validate=True, update_metadata=True)
            else:
                # Create new project
                self._qenvy.create_profile(project_name, config, overwrite=False)
        except ProfileAlreadyExistsError as e:
            # This should not happen because we checked above, but handle it
            config_path = self._qenvy.get_config_path(project_name)
            raise ProjectAlreadyExistsError(project_name, str(config_path)) from e
        except Exception as e:
            raise QenConfigError(f"Failed to write project config '{project_name}': {e}") from e

    def update_current_project(self, project_name: str) -> None:
        """Update the current_project field in main config.

        Args:
            project_name: Project name to set as current

        Raises:
            QenConfigError: If update fails
        """
        try:
            config = self.load_global_config()
            config["current_project"] = project_name
            self._qenvy.write_profile(
                self.MAIN_PROFILE, config, validate=True, update_metadata=True
            )
        except Exception as e:
            raise QenConfigError(f"Failed to update current_project: {e}") from e

    def get_meta_path(self) -> Path:
        """Get meta_path from global config.

        Returns:
            Path to meta repository

        Raises:
            QenConfigError: If meta_path not found in config
        """
        config = self.load_global_config()
        if "meta_path" not in config:
            raise QenConfigError("meta_path not found in global config")
        return Path(config["meta_path"])

    def get_meta_remote(self) -> str:
        """Get meta_remote from global config.

        Returns:
            Remote URL for cloning

        Raises:
            QenConfigError: If meta_remote not found in config
        """
        config = self.load_global_config()
        if "meta_remote" not in config:
            raise QenConfigError("meta_remote not found in global config")
        return cast(str, config["meta_remote"])

    def get_meta_parent(self) -> Path:
        """Get meta_parent from global config.

        Returns:
            Parent directory for per-project clones

        Raises:
            QenConfigError: If meta_parent not found in config
        """
        config = self.load_global_config()
        if "meta_parent" not in config:
            raise QenConfigError("meta_parent not found in global config")
        return Path(config["meta_parent"])

    def list_projects(self) -> list[str]:
        """List all project names.

        Returns:
            List of project names (excluding main profile)
        """
        all_profiles = self._qenvy.list_profiles()
        return [p for p in all_profiles if p != self.MAIN_PROFILE]

    def get_project_repo_path(self, project_name: str) -> Path:
        """Get the repo path for a project.

        Args:
            project_name: Name of project

        Returns:
            Path to per-project meta clone

        Raises:
            QenConfigError: If project not found or repo field missing
        """
        config = self.load_project_config(project_name)
        if "repo" not in config:
            raise QenConfigError(f"repo not found in project config '{project_name}'")
        return Path(config["repo"])

    def get_project_branch(self, project_name: str) -> str:
        """Get the branch name for a project.

        Args:
            project_name: Name of project

        Returns:
            Branch name

        Raises:
            QenConfigError: If project not found or branch field missing
        """
        config = self.load_project_config(project_name)
        if "branch" not in config:
            raise QenConfigError(f"branch not found in project config '{project_name}'")
        return cast(str, config["branch"])

    def get_project_folder(self, project_name: str) -> str:
        """Get the folder path for a project.

        Args:
            project_name: Name of project

        Returns:
            Project folder path (relative to repo)

        Raises:
            QenConfigError: If project not found or folder field missing
        """
        config = self.load_project_config(project_name)
        if "folder" not in config:
            raise QenConfigError(f"folder not found in project config '{project_name}'")
        return cast(str, config["folder"])

    def project_exists(self, project_name: str) -> bool:
        """Check if a project configuration exists.

        Args:
            project_name: Name of project

        Returns:
            True if project config exists
        """
        return self._qenvy.profile_exists(project_name)

    def delete_project(self, project_name: str) -> None:
        """Delete a project configuration.

        Args:
            project_name: Name of project to delete

        Raises:
            QenConfigError: If deletion fails
        """
        try:
            self._qenvy.delete_profile(project_name)
        except Exception as e:
            raise QenConfigError(f"Failed to delete project config '{project_name}': {e}") from e
