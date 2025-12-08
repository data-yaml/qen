# CLI Configuration Overrides - Requirements & Design

## Requirements

### User Scenarios

#### **Scenario 1: Alternate Config Directory**

```bash
qen --config-dir /tmp/test-config status
```

- Read/write config from alternate location
- Use case: Testing, isolated environments

#### **Scenario 2: Override Meta Repository**

```bash
qen --meta qen-test status
```

- Use different meta repo without config file
- Use case: Testing against qen-test, one-off operations

#### **Scenario 3: Override Current Project**

```bash
qen --proj my-feature add org/repo
```

- Execute command for specific project without changing stored config
- Use case: One-off operations, testing

#### **Combined Usage**

```bash
qen --meta /tmp/meta --proj test-proj status
```

- Both overrides work together
- Overrides apply for single command execution only
- Never persist to disk

## Design Decisions

### 1. QenConfig is the Configuration Abstraction

**Current State:**

- `QenConfig.__init__()` already accepts `config_dir` parameter
- `QenConfig.__init__()` already accepts `storage` parameter (for testing)

**Design:**

- Extend `QenConfig.__init__()` with runtime override parameters
- `QenConfig.read_main_config()` applies overrides to returned dict
- Overrides are runtime-only, never written to disk
- Users use `config` command to view/modify persistent config

### 2. CLI Layer Responsibilities

**Click Layer (`cli.py`):**

1. Parse `--config-dir`, `--meta`, `--proj` flags
2. Store in `ctx.obj["config_overrides"]` dict
3. Make available to all relevant subcommands

**Command Layer (`commands/*.py`):**

1. Extract `config_overrides` from `ctx.obj`
2. Pass overrides to `QenConfig` constructor
3. Call business logic with configured `QenConfig` instance

**Business Logic:**

- No Click dependencies
- No awareness of CLI flags
- Works in tests, CLI, and as library

### 3. Implementation Pattern

```python
# CLI adds global options
@click.group()
@click.option("--config-dir", type=click.Path(path_type=Path))
@click.option("--meta", type=click.Path(path_type=Path))
@click.option("--proj")
@click.pass_context
def main(ctx, config_dir, meta, proj):
    ctx.ensure_object(dict)
    ctx.obj["config_overrides"] = {
        "config_dir": config_dir,
        "meta_path": meta,
        "current_project": proj,
    }

# Commands extract and pass to QenConfig
@click.command()
@click.pass_context
def status_command(ctx, verbose):
    overrides = ctx.obj.get("config_overrides", {})
    config = QenConfig(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )
    show_project_status(config, verbose=verbose)
```

## Implementation Tasks

### Task 1: Extend QenConfig Constructor

**File:** `src/qen/config.py`

Add parameters:

- `meta_path_override: Path | None = None`
- `current_project_override: str | None = None`

Store as private attributes:

- `self._meta_path_override`
- `self._current_project_override`

### Task 2: Update QenConfig.read_main_config()

**File:** `src/qen/config.py`

Apply overrides to returned config dict:

```python
def read_main_config(self) -> dict[str, Any]:
    config = self._qenvy.read(self.MAIN_PROFILE) if self.main_config_exists() else {}

    if self._meta_path_override:
        config["meta_path"] = str(self._meta_path_override)
    if self._current_project_override:
        config["current_project"] = self._current_project_override

    return config
```

### Task 3: Add Global CLI Options

**File:** `src/qen/cli.py`

Update `@click.group()` decorator:

- Add `--config-dir` option
- Add `--meta` option
- Add `--proj` option
- Store in `ctx.obj["config_overrides"]`

### Task 4: Update All Command Functions

**Files:** `src/qen/commands/*.py`

For each relevant command:

1. Add `@click.pass_context` decorator
2. Extract `config_overrides` from `ctx.obj`
3. Pass overrides to `QenConfig()` constructor

Pattern applies to:

- `init.py`
- `add.py`
- `status.py`
- `pr.py` (all PR subcommands)
- Future commands

### Task 5: Add Tests

**Unit Tests** (`tests/unit/qen/test_config.py`):

- Test `QenConfig` with `meta_path_override`
- Test `QenConfig` with `current_project_override`
- Test `read_main_config()` applies overrides correctly

**Integration Tests** (`tests/integration/test_cli_overrides.py`):

- Test `--config-dir` flag with CLI runner
- Test `--meta` flag with CLI runner
- Test `--proj` flag with CLI runner
- Test combined flags

## Success Criteria

1. ✅ `qen --config-dir /tmp/cfg status` uses alternate config
2. ✅ `qen --meta /path/to/meta status` uses alternate meta repo
3. ✅ `qen --proj test-proj add repo` operates on specified project
4. ✅ Overrides never persist to disk
5. ✅ All existing tests pass (backward compatible)
6. ✅ Business logic has zero Click dependencies
7. ✅ Type checking passes

## Non-Goals

- ❌ Persisting overrides to config files
- ❌ Creating Click-specific helper functions
- ❌ Passing Click context to business logic
- ❌ Breaking backward compatibility
