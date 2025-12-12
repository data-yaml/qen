"""RuntimeContext for managing runtime overrides and config access."""

from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_config_dir

from qen.config import QenConfig


class RuntimeContextError(Exception):
    """Base exception for runtime context errors."""

    pass


@dataclass
class RuntimeContext:
    """Runtime context that manages overrides and provides clean config access.

    This class encapsulates runtime overrides (from CLI options) and provides
    helper methods for accessing configuration. It lazy-loads the QenConfig
    to avoid unnecessary initialization.

    Attributes:
        config_dir: Configuration directory path
        current_project_override: Runtime project override (None = use config)
        meta_path_override: Runtime meta path override (None = use config)
    """

    config_dir: Path
    current_project_override: str | None = None
    meta_path_override: Path | None = None
    _config_service: QenConfig = field(init=False, repr=False, default=None)  # type: ignore

    @staticmethod
    def from_cli(config_dir: str | None, meta: str | None, proj: str | None) -> "RuntimeContext":
        """Create RuntimeContext from CLI string options.

        Args:
            config_dir: Configuration directory path (None = use XDG default)
            meta: Meta repository path override (None = use config)
            proj: Current project name override (None = use config)

        Returns:
            RuntimeContext instance
        """
        return RuntimeContext(
            config_dir=Path(config_dir) if config_dir else Path(user_config_dir("qen")),
            current_project_override=proj,
            meta_path_override=Path(meta) if meta else None,
        )

    @property
    def config_service(self) -> QenConfig:
        """Get QenConfig instance, lazy-loading on first access.

        Returns:
            QenConfig instance

        Note:
            The QenConfig is cached after first access.
        """
        if self._config_service is None:
            self._config_service = QenConfig(
                config_dir=self.config_dir,
                meta_path_override=self.meta_path_override,
                current_project_override=self.current_project_override,
            )
        return self._config_service

    def get_current_project(self) -> str:
        """Get current project name from override or config.

        Returns:
            Current project name

        Raises:
            RuntimeContextError: If no current project is set
        """
        # Check override first
        if self.current_project_override:
            return self.current_project_override

        # Fall back to config
        try:
            config = self.config_service.read_main_config()
            project = config.get("current_project")
            if not project:
                raise RuntimeContextError(
                    "No current project set. Use 'qen config <project>' to set one, "
                    "or use --proj option."
                )
            if not isinstance(project, str):
                raise RuntimeContextError(
                    f"Invalid current_project in config: expected str, got {type(project).__name__}"
                )
            return project
        except RuntimeContextError:
            raise
        except Exception as e:
            raise RuntimeContextError(f"Failed to get current project: {e}") from e

    def get_meta_path(self) -> Path:
        """Get meta repository path from override or config.

        Returns:
            Path to meta repository

        Raises:
            RuntimeContextError: If meta_path is not configured
        """
        # Check override first
        if self.meta_path_override:
            return self.meta_path_override

        # Fall back to config
        try:
            config = self.config_service.read_main_config()
            meta_path = config.get("meta_path")
            if not meta_path:
                raise RuntimeContextError("meta_path not configured. Run 'qen init' to configure.")
            if not isinstance(meta_path, str):
                raise RuntimeContextError(
                    f"Invalid meta_path in config: expected str, got {type(meta_path).__name__}"
                )
            return Path(meta_path)
        except RuntimeContextError:
            raise
        except Exception as e:
            raise RuntimeContextError(f"Failed to get meta_path: {e}") from e

    def get_project_root(self) -> Path:
        """Get per-project meta clone path from project config.

        Returns:
            Path to per-project meta repository clone

        Raises:
            RuntimeContextError: If project config cannot be read or repo field is missing
        """
        project_name = self.get_current_project()

        try:
            project_config = self.config_service.read_project_config(project_name)
            repo_path = project_config.get("repo")
            if not repo_path:
                raise RuntimeContextError(
                    f"Project '{project_name}' config missing 'repo' field. "
                    f"Run 'qen init {project_name}' to reinitialize."
                )
            if not isinstance(repo_path, str):
                raise RuntimeContextError(
                    f"Invalid repo path in config: expected str, got {type(repo_path).__name__}"
                )
            return Path(repo_path)
        except RuntimeContextError:
            raise
        except Exception as e:
            raise RuntimeContextError(
                f"Failed to get project root for '{project_name}': {e}"
            ) from e

    def get_project_pyproject(self) -> Path:
        """Get path to project's pyproject.toml file.

        Returns:
            Path to pyproject.toml in project folder

        Raises:
            RuntimeContextError: If project folder cannot be determined
        """
        project_name = self.get_current_project()

        try:
            project_config = self.config_service.read_project_config(project_name)
            repo_path = project_config.get("repo")
            folder = project_config.get("folder")

            if not repo_path or not folder:
                raise RuntimeContextError(
                    f"Project '{project_name}' config incomplete. Missing 'repo' or 'folder' field."
                )

            if not isinstance(repo_path, str):
                raise RuntimeContextError(
                    f"Invalid repo path in config: expected str, got {type(repo_path).__name__}"
                )
            if not isinstance(folder, str):
                raise RuntimeContextError(
                    f"Invalid folder in config: expected str, got {type(folder).__name__}"
                )

            project_dir = Path(repo_path) / folder
            return project_dir / "pyproject.toml"
        except RuntimeContextError:
            raise
        except Exception as e:
            raise RuntimeContextError(
                f"Failed to get project pyproject.toml for '{project_name}': {e}"
            ) from e
