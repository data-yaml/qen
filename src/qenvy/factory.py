"""
Storage backend factory for configuration management.

This module provides factory functions for creating storage backends
based on environment variables or explicit configuration.
"""

import os
from pathlib import Path
from typing import Any

from .base import QenvyBase
from .storage import QenvyConfig


def create_storage(
    app_name: str,
    storage_type: str | None = None,
    config_dir: Path | str | None = None,
    **kwargs: Any,
) -> QenvyBase:
    """Create storage backend based on type.

    Args:
        app_name: Application name
        storage_type: "filesystem" or "parameter-store" (default: from QENVY_STORAGE env)
        config_dir: Config directory (filesystem only)
        **kwargs: Backend-specific options (e.g., region, prefix, kms_key_id)

    Returns:
        Storage backend instance

    Environment Variables:
        QENVY_STORAGE: Storage backend type ("filesystem" or "parameter-store")

    Examples:
        # Use default (filesystem)
        storage = create_storage("my-app")

        # Explicitly use filesystem
        storage = create_storage("my-app", storage_type="filesystem")

        # Use Parameter Store
        storage = create_storage("my-app", storage_type="parameter-store")

        # Use Parameter Store with custom region
        storage = create_storage("my-app", storage_type="parameter-store", region="us-west-2")

        # Use environment variable
        os.environ["QENVY_STORAGE"] = "parameter-store"
        storage = create_storage("my-app")  # Will use Parameter Store
    """
    if storage_type is None:
        storage_type = os.getenv("QENVY_STORAGE", "filesystem")

    if storage_type == "parameter-store":
        # Lazy import to avoid requiring boto3 for filesystem-only users
        from .parameter_store import ParameterStoreConfig

        return ParameterStoreConfig(app_name=app_name, **kwargs)
    else:
        return QenvyConfig(app_name=app_name, base_dir=config_dir, **kwargs)
