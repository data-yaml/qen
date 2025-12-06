"""
qenvy - Cross-platform configuration management library.

A modern Python library for managing profile-based configurations with
inheritance, validation, and atomic writes. Built on platformdirs for
platform-native directory resolution.

Example:
    >>> from qenvy import QenvyConfig
    >>> config = QenvyConfig("myapp")
    >>> config.create_profile("default", {"database": "prod.db"})
    >>> config.write_profile("dev", {"inherits": "default", "database": "dev.db"})
    >>> dev_config = config.read_profile("dev")
    >>> print(dev_config["database"])
    'dev.db'
"""

from .base import QenvyBase
from .exceptions import (
    AtomicWriteError,
    BackupError,
    CircularInheritanceError,
    ConfigValidationError,
    FormatError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    QenvyError,
    StorageError,
)
from .formats import FormatHandler, JSONHandler, TOMLHandler, get_format_handler
from .protocols import IConfigStorage
from .storage import QenvyConfig
from .types import (
    ConfigMetadata,
    MergeResult,
    ProfileConfig,
    ProfileInfo,
    ValidationResult,
)

__version__ = "0.1.0"

__all__ = [
    # Main classes
    "QenvyConfig",
    "QenvyBase",
    # Exceptions
    "QenvyError",
    "ProfileNotFoundError",
    "ProfileAlreadyExistsError",
    "ConfigValidationError",
    "CircularInheritanceError",
    "FormatError",
    "StorageError",
    "AtomicWriteError",
    "BackupError",
    # Types
    "ProfileConfig",
    "ConfigMetadata",
    "ValidationResult",
    "ProfileInfo",
    "MergeResult",
    # Protocols
    "IConfigStorage",
    # Format handlers
    "FormatHandler",
    "TOMLHandler",
    "JSONHandler",
    "get_format_handler",
]
