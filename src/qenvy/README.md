# qenvy

A lightweight, type-safe Python library for cross-platform configuration management.

## Features

- **Profile-based configuration** - Organize configs by environment (dev, staging, prod)
- **Profile inheritance** - Extend base configurations with deep merge
- **Multiple formats** - TOML (default) and JSON support
- **Platform-native directories** - Uses OS-appropriate config locations via platformdirs
- **Atomic writes** - Safe file operations with automatic backups
- **Type safety** - Full Python 3.12+ type hints
- **Zero config** - Works out of the box with sensible defaults

## Installation

```bash
pip install qenvy
```

Or add to your `pyproject.toml`:

```toml
dependencies = [
    "qenvy>=0.1.0",
]
```

## Quick Start

```python
from qenvy import QenvyConfig

# Create a config manager for your app
config = QenvyConfig("myapp")

# Write a configuration profile
config.write_profile("default", {
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "myapp_db"
    },
    "api": {
        "timeout": 30,
        "retries": 3
    },
    "_metadata": {
        "version": "1.0.0",
        "created_at": "2025-12-05T00:00:00Z",
        "updated_at": "2025-12-05T00:00:00Z",
        "source": "wizard"
    }
})

# Read the configuration
data = config.read_profile("default")
print(data["database"]["host"])  # localhost

# List all profiles
profiles = config.list_profiles()
print(profiles)  # ['default']
```

## Configuration Storage

By default, qenvy stores configurations in platform-native directories:

- Linux: `~/.config/myapp/`
- macOS: `~/Library/Application Support/myapp/`
- Windows: `%APPDATA%\myapp\`

On Linux, respects `XDG_CONFIG_HOME` environment variable if set.

### Directory Structure

```
{config_dir}/myapp/
├── default/
│   ├── config.toml
│   └── config.toml.backup
├── dev/
│   └── config.toml
└── prod/
    └── config.toml
```

## Profile Inheritance

Profiles can inherit from other profiles using the `_inherits` key:

```python
# Create a base profile
config.write_profile("base", {
    "database": {
        "host": "localhost",
        "port": 5432,
        "pool_size": 10
    },
    "cache": {
        "ttl": 3600
    },
    "_metadata": {...}
})

# Create a dev profile that inherits from base
config.write_profile("dev", {
    "_inherits": "base",
    "database": {
        "host": "dev.example.com",  # Override host
        "name": "myapp_dev"          # Add new field
    },
    "debug": True,                   # Add new top-level field
    "_metadata": {...}
})

# Read with inheritance - deep merges base and dev
dev_config = config.read_profile_with_inheritance("dev")
print(dev_config)
# {
#     "database": {
#         "host": "dev.example.com",  # From dev (override)
#         "port": 5432,                # From base
#         "pool_size": 10,             # From base
#         "name": "myapp_dev"          # From dev (new)
#     },
#     "cache": {
#         "ttl": 3600                  # From base
#     },
#     "debug": True,                   # From dev (new)
#     "_metadata": {...}
# }
```

### Multi-level Inheritance

Inheritance chains are fully supported:

```python
config.write_profile("base", {...})
config.write_profile("staging", {"_inherits": "base", ...})
config.write_profile("prod", {"_inherits": "staging", ...})

# Resolves: prod -> staging -> base
prod_config = config.read_profile_with_inheritance("prod")
```

Circular inheritance is detected and raises `CircularInheritanceError`.

## Format Support

### TOML (Default)

```python
from qenvy import QenvyConfig, ConfigFormat

config = QenvyConfig("myapp", format=ConfigFormat.TOML)
config.write_profile("default", {...})
# Creates: {config_dir}/myapp/default/config.toml
```

### JSON

```python
config = QenvyConfig("myapp", format=ConfigFormat.JSON)
config.write_profile("default", {...})
# Creates: {config_dir}/myapp/default/config.json
```

## Advanced Usage

### Custom Base Directory

```python
from pathlib import Path

config = QenvyConfig("myapp", base_dir=Path("/etc/myapp"))
```

### Custom Config Filename

```python
config = QenvyConfig("myapp", config_filename="settings.toml")
```

### Profile Management

```python
# Check if profile exists
if config.profile_exists("prod"):
    data = config.read_profile("prod")

# List all profiles
profiles = config.list_profiles()

# Delete a profile (cannot delete 'default')
config.delete_profile("old-profile")
```

### Validation

```python
# Validate before reading
result = config.validate_profile(config_data)
if not result.is_valid:
    print("Errors:", result.errors)
    print("Warnings:", result.warnings)
```

### Custom Validation

Extend `QenvyConfig` to add application-specific validation:

```python
from qenvy import QenvyConfig, ValidationResult, ProfileConfig

class MyAppConfig(QenvyConfig):
    def validate_profile(self, config: ProfileConfig) -> ValidationResult:
        # Call parent validation
        result = super().validate_profile(config)

        # Add custom validation
        if "database" not in config:
            result.errors.append("Missing required section: database")
            result.is_valid = False
        elif "host" not in config["database"]:
            result.errors.append("Missing database.host")
            result.is_valid = False

        if config.get("api", {}).get("timeout", 0) > 300:
            result.warnings.append("API timeout is very high")

        return result
```

## Safety Features

### Atomic Writes

All writes use atomic operations (write to temp file, then rename):

```python
config.write_profile("prod", {...})
# 1. Writes to .config.toml.tmp-<random>
# 2. Renames to config.toml (atomic)
# 3. Previous config.toml moved to config.toml.backup
```

### Automatic Backups

Before overwriting any file, qenvy creates a `.backup` copy:

```
{config_dir}/myapp/default/
├── config.toml
└── config.toml.backup  # Previous version
```

## API Reference

### QenvyConfig

Main configuration manager class.

**Constructor:**

```python
QenvyConfig(
    app_name: str,
    *,
    base_dir: Path | str | None = None,
    format: ConfigFormat = ConfigFormat.TOML,
    config_filename: str | None = None,
    ensure_dir: bool = True
)
```

**Methods:**

- `read_profile(profile: str) -> ProfileConfig`
- `write_profile(profile: str, config: ProfileConfig) -> None`
- `delete_profile(profile: str) -> None`
- `list_profiles() -> list[str]`
- `profile_exists(profile: str) -> bool`
- `read_profile_with_inheritance(profile: str, base_profile: str | None = None) -> ProfileConfig`
- `validate_profile(config: ProfileConfig) -> ValidationResult`
- `get_base_dir() -> Path`
- `get_profile_path(profile: str) -> Path`

### Types

- `ProfileConfig` - `dict[str, Any]` - Profile configuration data
- `ConfigFormat` - Enum with `TOML` and `JSON` values
- `ConfigSource` - Enum: `WIZARD`, `MANUAL`, `CLI`, `API`
- `ValidationResult` - Dataclass with `is_valid`, `errors`, `warnings`
- `ConfigMetadata` - TypedDict with version, timestamps, source

### Exceptions

All exceptions inherit from `QenvyError`:

- `ProfileNotFoundError` - Profile does not exist
- `ProfileAlreadyExistsError` - Profile already exists
- `ConfigValidationError` - Invalid configuration
- `CircularInheritanceError` - Circular inheritance detected
- `FormatError` - Format parsing/serialization error
- `StorageError` - Storage operation error
- `AtomicWriteError` - Atomic write operation failed
- `BackupError` - Backup creation failed

## Architecture

qenvy uses a two-class architecture:

1. **QenvyBase** (abstract) - Business logic (validation, inheritance, merging)
2. **QenvyConfig** (concrete) - Storage primitives (read, write, delete)

This separation allows for:
- Easy testing with in-memory implementations
- Alternative storage backends (S3, etcd, etc.)
- Clean separation of concerns

## Design Principles

- **Cross-platform** - Platform-native config directories via platformdirs
- **Type safety** - Full type hints for IDE support
- **Simplicity** - Minimal API surface
- **Extensibility** - Protocol-based for custom implementations
- **Safety** - Atomic writes, backups, validation
- **Pythonic** - Idiomatic Python 3.12+ code

## Requirements

- Python 3.12+
- platformdirs >= 4.0.0
- tomli-w >= 1.0.0
- tomli >= 2.0.0 (Python < 3.11)

## License

MIT

## Credits

Modeled after the TypeScript configuration library from the [benchling-webhook](https://github.com/quiltdata/benchling-webhook) project.
