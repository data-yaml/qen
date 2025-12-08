# CLI Overrides: Design Decisions

## Core Principle

**Separation of Concerns**: UI layer (Click) and business logic (commands) must remain decoupled.

## Key Design Decisions

### 1. QenConfig is Already the Abstraction

**Current state:**

- `QenConfig.__init__()` already accepts `config_dir` override
- `QenConfig.__init__()` already accepts `storage` override (for testing)

**Decision:**

- Extend QenConfig constructor with runtime overrides
- Keep QenConfig as the single source of configuration truth
- NO new context helper module needed

### 2. Runtime Overrides vs Persistent Config

**Problem:** `--meta` and `--proj` flags should NOT persist to disk

**Decision:**

```python
class QenConfig:
    def __init__(
        self,
        config_dir: Path | None = None,      # Already exists
        storage: QenvyBase | None = None,    # Already exists
        meta_path_override: Path | None = None,       # NEW - runtime only
        current_project_override: str | None = None,  # NEW - runtime only
    ):
```

**Behavior:**

- Overrides apply to `read_main_config()` output
- Overrides never written to disk
- Commands see overridden values transparently

### 3. CLI Layer Responsibilities

**What CLI does:**

1. Parse flags (`--config-dir`, `--meta`, `--proj`)
2. Store in `ctx.obj["config_overrides"]` dict
3. Pass to QenConfig constructor in each command

**What CLI does NOT do:**

- Pass Click context to business logic
- Create Click-specific helper functions
- Leak UI framework into commands

### 4. Command Pattern

**Each command function:**

```python
@click.command()
@click.pass_context
def status_command(ctx: click.Context, verbose: bool) -> None:
    # Extract overrides from context
    overrides = ctx.obj.get("config_overrides", {})

    # Create config with overrides
    config = QenConfig(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )

    # Call business logic (no Click dependency)
    show_project_status(config, verbose=verbose)
```

**Business logic remains pure:**

```python
def show_project_status(config: QenConfig, verbose: bool = False) -> None:
    # NO Click imports
    # NO ctx parameter
    # Works in tests, CLI, and as library
    main_config = config.read_main_config()  # Overrides already applied
    # ... rest of logic
```

## Implementation Tasks

### Task 1: Extend QenConfig

- Add `meta_path_override` and `current_project_override` to `__init__`
- Store as private attributes
- Apply overrides in `read_main_config()` method
- Add tests for override behavior

### Task 2: Update CLI Layer

- Add global options to `@click.group()` in `cli.py`
- Store flags in `ctx.obj["config_overrides"]` dict
- NO other CLI changes needed

### Task 3: Update Commands

- Each command extracts `config_overrides` from `ctx.obj`
- Each command passes overrides to `QenConfig()` constructor
- Pattern is mechanical - same for all commands

### Task 4: Tests

- Existing tests work unchanged (backward compatible)
- New tests for CLI flags use CliRunner
- New tests for overrides use QenConfig constructor directly

## Non-Goals

**What we are NOT doing:**

- ❌ Creating a context helper module
- ❌ Passing Click context to business logic
- ❌ Creating `get_config_from_context()` functions
- ❌ Making business logic depend on UI framework
- ❌ Breaking backward compatibility
- ❌ Requiring tests to use Click

## Success Criteria

1. ✅ CLI accepts `--config-dir`, `--meta`, `--proj` flags
2. ✅ Overrides don't persist to disk
3. ✅ Existing tests pass unchanged
4. ✅ Business logic has zero Click dependencies
5. ✅ Can use commands as library functions
6. ✅ Type checking passes
