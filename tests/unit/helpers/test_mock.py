"""Helpers for creating mock objects."""

from typing import Any
from unittest.mock import Mock


def create_test_config() -> Any:
    """Create a mock QenConfig for testing.

    Returns:
        A mocker.Mock with QenConfig spec and custom behavior
    """
    config = Mock(spec=["read_main_config", "read_project_config"])

    def _read_main_config_mock(default: dict | None = None) -> dict:
        """Configurable main config mock."""
        return default or {"current_project": None, "meta_path": "/tmp/meta"}

    config.read_main_config.side_effect = _read_main_config_mock

    return config
