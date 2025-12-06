"""
Custom exceptions for qenvy configuration management.

This module defines all custom exceptions used throughout the qenvy library
for clear and specific error handling.
"""


class QenvyError(Exception):
    """Base exception for all qenvy errors."""

    pass


class ProfileNotFoundError(QenvyError):
    """Raised when a profile does not exist."""

    def __init__(self, profile: str, message: str | None = None):
        self.profile = profile
        super().__init__(message or f"Profile not found: {profile}")


class ProfileAlreadyExistsError(QenvyError):
    """Raised when attempting to create a profile that already exists."""

    def __init__(self, profile: str):
        self.profile = profile
        super().__init__(f"Profile already exists: {profile}")


class ConfigValidationError(QenvyError):
    """Raised when configuration validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        error_msg = "\n".join(f"  - {err}" for err in errors)
        super().__init__(f"Configuration validation failed:\n{error_msg}")


class CircularInheritanceError(QenvyError):
    """Raised when circular inheritance is detected in profile hierarchy."""

    def __init__(self, profile: str, chain: list[str]):
        self.profile = profile
        self.chain = chain
        chain_str = " -> ".join(chain + [profile])
        super().__init__(f"Circular inheritance detected: {chain_str}")


class FormatError(QenvyError):
    """Raised when configuration format parsing fails."""

    def __init__(self, format_name: str, message: str):
        self.format_name = format_name
        super().__init__(f"{format_name} format error: {message}")


class StorageError(QenvyError):
    """Raised when filesystem storage operations fail."""

    def __init__(self, operation: str, path: str, message: str):
        self.operation = operation
        self.path = path
        super().__init__(f"Storage error during {operation} at {path}: {message}")


class AtomicWriteError(StorageError):
    """Raised when atomic write operation fails."""

    def __init__(self, path: str, message: str):
        super().__init__("atomic write", path, message)


class BackupError(StorageError):
    """Raised when backup creation fails."""

    def __init__(self, path: str, message: str):
        super().__init__("backup", path, message)
