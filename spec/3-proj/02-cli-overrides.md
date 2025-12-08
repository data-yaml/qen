# CLI Configuration Overrides Specification (CORRECTED)

## Problem with Original Spec

The original spec violated separation of concerns by passing Click context objects into business logic. This is wrong because:

1. **UI framework leakage**: Business logic shouldn't know about Click
2. **Not backward compatible**: Existing tests and library usage break
3. **Tight coupling**: Can't use commands outside CLI context

## Correct Design: QenConfig Already Has the Abstraction

**QenConfig ALREADY accepts overrides in its constructor:**

```python
class QenConfig:
    def __init__(self, config_dir: Path | str | None = None, storage: QenvyBase | None = None):
        """Initialize qen configuration manager.

        Args:
            config_dir: Override default config directory
            storage: Override storage backend (for testing)
        """
```

The CLI layer should:

1. **Parse flags** (Click's job)
2. **Pass parameters** to business logic (clean function calls)
3. **Never pass Click context** into business logic

## Solution: Constructor-Based Overrides

### Level 1: Config Directory Override (ALREADY WORKS)

```python
# CLI layer parses --config-dir flag and passes it to QenConfig
config = QenConfig(config_dir=Path("/tmp/test-config"))
```

### Level 2: Meta Path & Project Overrides (NEW)

Extend QenConfig to accept runtime overrides WITHOUT writing to disk:

```python
class QenConfig:
    def __init__(
        self,
        config_dir: Path | str | None = None,
        storage: QenvyBase | None = None,
        # NEW: Runtime overrides (not persisted)
        meta_path_override: Path | None = None,
        current_project_override: str | None = None,
    ):
        """Initialize with optional runtime overrides."""
        self._meta_path_override = meta_path_override
        self._current_project_override = current_project_override
        # ... existing code

    def read_main_config(self) -> dict[str, Any]:
        """Read main config with overrides applied."""
        config = self._qenvy.read(self.MAIN_PROFILE) if self.main_config_exists() else {}

        # Apply runtime overrides (don't persist)
        if self._meta_path_override:
            config["meta_path"] = str(self._meta_path_override)
        if self._current_project_override:
            config["current_project"] = self._current_project_override

        return config
```

## Implementation Pattern

### CLI Layer (src/qen/cli.py)

```python
@click.group()
@click.option("--config-dir", type=click.Path(path_type=Path), help="Override config location")
@click.option("--meta", type=click.Path(path_type=Path), help="Override meta repository path")
@click.option("--proj", help="Override current project (one-off operation)")
@click.pass_context
def main(ctx: click.Context, config_dir: Path | None, meta: Path | None, proj: str | None) -> None:
    """qen - Organize multi-repository development work."""
    # Store CLI flags in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["config_overrides"] = {
        "config_dir": config_dir,
        "meta_path": meta,
        "current_project": proj,
    }
```

### Command Layer (src/qen/commands/*.py)

```python
@click.command()
@click.pass_context
def status_command(ctx: click.Context, verbose: bool) -> None:
    """Show status of current project."""
    # Extract overrides from context
    overrides = ctx.obj.get("config_overrides", {})

    # Pass overrides to business logic as constructor parameters
    config = QenConfig(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )

    # Business logic never sees Click context
    show_project_status(config, verbose=verbose)


def show_project_status(config: QenConfig, verbose: bool = False) -> None:
    """Business logic function - no Click dependencies."""
    main_config = config.read_main_config()  # Overrides already applied
    meta_path = Path(main_config["meta_path"])
    current_project = main_config["current_project"]

    # ... rest of business logic
```

## Key Benefits

1. **Separation of concerns**: CLI and business logic are decoupled
2. **Backward compatible**: Existing code still works (overrides are optional)
3. **Testable**: Can test business logic without Click framework
4. **Library-friendly**: Can import and use functions directly
5. **Clean API**: QenConfig constructor is the single point of configuration

## Testing Strategy

### Unit Tests (No Click Required)

```python
def test_status_with_overrides(tmp_path):
    """Test business logic directly - no CLI involved."""
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()

    # Create config with overrides using constructor
    config = QenConfig(
        config_dir=tmp_path / "config",
        meta_path_override=meta_dir,
        current_project_override="test-project",
    )

    # Test business logic directly
    show_project_status(config, verbose=False)
```

### Integration Tests (With CLI)

```python
def test_cli_status_with_flags(cli_runner, tmp_path):
    """Test CLI with flags."""
    result = cli_runner.invoke(main, [
        "--config-dir", str(tmp_path / "config"),
        "--meta", str(tmp_path / "meta"),
        "--proj", "test-project",
        "status"
    ])
    assert result.exit_code == 0
```

## Implementation Steps

1. **Extend QenConfig constructor** - Add `meta_path_override` and `current_project_override` parameters
2. **Update QenConfig.read_main_config()** - Apply overrides to returned config dict
3. **Update cli.py** - Add global options and store in ctx.obj
4. **Update commands** - Extract overrides from ctx.obj and pass to QenConfig constructor
5. **Tests work automatically** - Backward compatible, existing tests pass

## What NOT To Do

❌ **Don't pass Click context into business logic**

```python
def show_project_status(ctx: click.Context):  # BAD
    config = get_config_from_context(ctx)      # BAD
```

✅ **Do pass configuration as parameters**

```python
def show_project_status(config: QenConfig):    # GOOD
    # Business logic doesn't know about Click
```

❌ **Don't create Click-specific helper functions**

```python
def get_config_from_context(ctx: click.Context) -> QenConfig:  # BAD
    # Tight coupling to Click framework
```

✅ **Do use constructor parameters**

```python
config = QenConfig(
    config_dir=config_dir,
    meta_path_override=meta_path,
    current_project_override=project_name,
)  # GOOD - Clean dependency injection
```
