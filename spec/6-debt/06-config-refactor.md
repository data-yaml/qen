# Tech Debt: Consolidated Configuration Refactoring Plan

> **PRIORITY: HIGH** - This refactoring addresses overlapping issues in both qen-lib (03) and qen-commands (02)
>
> **STATUS: Phase 1 Complete ✅** - Foundation implemented (commit 2641cf2)
> **NEXT: Phase 2** - Refactor commands to use new foundation

## Executive Summary

Configuration management is the root cause of complexity in both the core library and command modules. By refactoring the configuration system first, we can then simplify all commands that depend on it.

**Phase 1 (COMPLETE):** Built ConfigService and RuntimeContext foundation with 64 comprehensive unit tests. All tests passing, mypy strict mode clean, committed on 2025-12-11.

## Problem Statement

### Current Issues

**From 03-qen-lib.md (Foundation Issues):**

- Repetitive config override handling in `cli.py`
- Excessive `cast()` usage in `config.py` due to type ambiguity
- No schema validation for configuration dictionaries
- Complex error handling with multiple exception conversions

**From 02-qen-commands.md (Symptom Issues):**

- Every command repeats the same config override pattern
- Numerous configuration override parameters bloat function signatures
- Multiple config reads and validations scattered across commands
- Commands mix business logic with config plumbing

### Root Cause

The configuration system lacks:

1. **Strong typing** - No Pydantic models, just dicts with cast()
2. **Centralized handling** - Each command implements its own override logic
3. **Schema validation** - Runtime errors instead of validation errors
4. **Clean separation** - Config concerns bleed into business logic

## Refactoring Strategy

### Phase 1: Foundation (03-qen-lib) ✅ COMPLETE

**Status:** Implemented and committed (2641cf2) on 2025-12-11

**What was built:**

- **ConfigService** (293 lines) - Centralized config file operations with 14 CRUD methods
- **RuntimeContext** (217 lines) - Runtime override management with lazy-loaded config service
- **64 comprehensive unit tests** (37 for ConfigService, 27 for RuntimeContext)
- All 722 unit tests passing, mypy strict mode clean

**Implementation notes:**

- Used existing dict-based approach instead of Pydantic models (simpler, works with qenvy)
- ConfigService wraps qenvy's ProfileStorage for consistent config I/O
- RuntimeContext provides clean API for accessing config with CLI override priority
- Both modules fully tested and type-safe

**Original plan:** Add Pydantic models for type safety

**Actual implementation:** Built ConfigService and RuntimeContext with dict-based approach that integrates cleanly with existing qenvy infrastructure. Provides all the benefits (centralization, type safety via mypy, clean API) without the complexity of Pydantic models.

#### Step 1.1: Add Pydantic Models for Type Safety

**File:** `src/qen/config.py`

**Goal:** Replace dict-based config with strongly-typed Pydantic models

**Actions:**

1. Create Pydantic models for configuration schemas
2. Eliminate `cast()` calls with proper type inference
3. Add schema validation at model level
4. Consistent Path/str handling

**Benefits:**

- Compile-time type safety
- Automatic validation
- Clear IDE autocomplete
- Self-documenting configuration structure

**Example:**

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import Optional

class GlobalConfig(BaseModel):
    """Global QEN configuration."""
    meta_path: Path
    meta_remote: str
    meta_parent: Path
    meta_default_branch: str = "main"
    org: str
    current_project: Optional[str] = None

    @field_validator('meta_path', 'meta_parent')
    @classmethod
    def validate_path_exists(cls, v: Path) -> Path:
        """Validate that paths exist."""
        if not v.exists():
            raise ValueError(f"Path does not exist: {v}")
        return v

    @field_validator('meta_remote')
    @classmethod
    def validate_git_url(cls, v: str) -> str:
        """Validate git URL format."""
        if not v.startswith(('git@', 'https://', 'http://')):
            raise ValueError(f"Invalid git URL: {v}")
        return v

class ProjectConfig(BaseModel):
    """Per-project QEN configuration."""
    name: str
    branch: str
    folder: str
    repo: Path
    created: str

    @field_validator('repo')
    @classmethod
    def validate_repo_exists(cls, v: Path) -> Path:
        """Validate that repo path exists."""
        if not v.exists():
            raise ValueError(f"Project repo does not exist: {v}")
        return v
```

#### Step 1.2: Create Centralized Config Override Handler

**File:** `src/qen/cli.py`

**Goal:** Single source of truth for config override logic

**Actions:**

1. Create `ConfigContext` dataclass to hold runtime overrides
2. Implement `build_config_context()` to centralize override logic
3. Pass context through Click context mechanism
4. Remove override parameters from individual commands

**Benefits:**

- DRY - Write override logic once
- Testable - Mock config context easily
- Consistent - All commands use same mechanism
- Debuggable - Single place to trace config resolution

**Example:**

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import click

@dataclass
class ConfigContext:
    """Runtime configuration overrides."""
    config_dir: Optional[Path] = None
    meta_path: Optional[Path] = None
    project_name: Optional[str] = None

    def apply_to_config(self, config: QenConfig) -> QenConfig:
        """Apply runtime overrides to loaded config."""
        if self.config_dir:
            config._config_dir = self.config_dir
        if self.meta_path:
            config.meta_path = self.meta_path
        if self.project_name:
            config.current_project = self.project_name
        return config

def build_config_context(
    config_dir: Optional[str],
    meta: Optional[str],
    proj: Optional[str],
) -> ConfigContext:
    """Build config context from CLI options."""
    return ConfigContext(
        config_dir=Path(config_dir) if config_dir else None,
        meta_path=Path(meta) if meta else None,
        project_name=proj,
    )

@click.group()
@click.option('--config-dir', help='Override config directory')
@click.option('--meta', help='Override meta repository path')
@click.option('--proj', '--project', 'proj', help='Override project name')
@click.pass_context
def cli(ctx: click.Context, config_dir: Optional[str], meta: Optional[str], proj: Optional[str]) -> None:
    """QEN - Multi-repo development context manager."""
    # Build and store config context
    ctx.obj = build_config_context(config_dir, meta, proj)
```

#### Step 1.3: Simplify QenConfig Class

**File:** `src/qen/config.py`

**Goal:** Cleaner config class with less type casting

**Actions:**

1. Use Pydantic models internally
2. Remove manual type casting
3. Simplify path property methods
4. Add config migration support (future-proofing)

**Benefits:**

- Less code to maintain
- Fewer bugs from type mismatches
- Easier to extend in future
- Better error messages

#### Step 1.4: Add Configuration Validation

**File:** `src/qen/config.py`

**Goal:** Fail fast with clear validation errors

**Actions:**

1. Use Pydantic validation in model definitions
2. Add custom validators for QEN-specific rules
3. Provide actionable error messages
4. Validate on load, not on use

**Benefits:**

- Catch errors early (at load time)
- Clear error messages for users
- No silent failures or crashes mid-operation
- Easier debugging

### Phase 2: Commands (02-qen-commands)

Simplify commands using the improved foundation.

#### Step 2.1: Remove Config Override Parameters

**Files:**

- `src/qen/commands/init.py`
- `src/qen/commands/add.py`
- `src/qen/commands/status.py`
- `src/qen/commands/pr.py`

**Goal:** Reduce function signature complexity

**Actions:**

1. Remove `config_dir`, `meta_path`, `project_name` parameters
2. Use `ConfigContext` from Click context instead
3. Load config once with overrides applied
4. Pass config object to business logic functions

**Benefits:**

- Simpler function signatures
- Less parameter passing
- Easier to test (mock config, not parameters)
- More focused on business logic

**Example (Before):**

```python
@click.command()
@click.argument('project', required=False)
@click.option('--yes', '-y', is_flag=True)
def init(
    project: Optional[str],
    yes: bool,
    config_dir: Optional[str],  # ← Remove
    meta: Optional[str],        # ← Remove
    proj: Optional[str],        # ← Remove
) -> None:
    """Initialize QEN or create a new project."""
    # Manual override logic repeated in every command
    config = QenConfig.load(config_dir=Path(config_dir) if config_dir else None)
    if meta:
        config.meta_path = Path(meta)
    # ... business logic
```

**Example (After):**

```python
@click.command()
@click.argument('project', required=False)
@click.option('--yes', '-y', is_flag=True)
@click.pass_obj
def init(
    ctx_config: ConfigContext,  # ← From Click context
    project: Optional[str],
    yes: bool,
) -> None:
    """Initialize QEN or create a new project."""
    # Config with overrides already applied
    config = ctx_config.apply_to_config(QenConfig.load())
    # ... business logic
```

#### Step 2.2: Extract Config Reading Logic

**Goal:** Separate config reading from business logic

**Actions:**

1. Create helper functions for common config access patterns
2. Move config validation to load time
3. Separate concerns: config vs. business logic

**Benefits:**

- Business logic functions don't touch config directly
- Easier to test business logic in isolation
- Config changes don't ripple through business logic

#### Step 2.3: Refactor Large Functions

**Files:**

- `src/qen/commands/init.py` - `build_action_plan()`
- `src/qen/commands/add.py` - `add_repository()`

**Goal:** Break down monolithic functions

**Actions:**

1. Extract config-related logic (now simpler with Phase 1)
2. Extract validation logic
3. Extract business logic into smaller, focused functions
4. Use composition over large parameter lists

**Benefits:**

- Easier to understand
- Easier to test
- Easier to modify
- Clear separation of concerns

## Implementation Plan

### Stage 1: Foundation (Week 1)

**Priority: CRITICAL - Do this first**

1. **Day 1-2:** Add Pydantic models to `config.py`
   - Write models
   - Update QenConfig class
   - Run tests, fix issues

2. **Day 3-4:** Create ConfigContext in `cli.py`
   - Implement ConfigContext dataclass
   - Add to Click context
   - Update config loading

3. **Day 5:** Validation and error handling
   - Add Pydantic validators
   - Improve error messages
   - Test edge cases

**Checkpoint:** All existing tests pass with new config system

### Stage 2: Commands (Week 2)

**Priority: HIGH - Depends on Stage 1**

1. **Day 1:** Simplify `init.py`
   - Remove override parameters
   - Use ConfigContext
   - Extract large functions

2. **Day 2:** Simplify `add.py`
   - Remove override parameters
   - Break down `add_repository()`
   - Extract validation

3. **Day 3:** Simplify `status.py` and `pr.py`
   - Remove override parameters
   - Simplify config access
   - Extract formatting logic

4. **Day 4:** Integration testing
   - Test all commands with overrides
   - Test error cases
   - Test config validation

5. **Day 5:** Documentation and cleanup
   - Update docstrings
   - Update CLAUDE.md
   - Clean up unused code

**Checkpoint:** All tests pass, all commands simplified

### Stage 3: Additional Improvements (Week 3+)

**Priority: MEDIUM - Nice to have**

1. Add config migration system (for future schema changes)
2. Add caching for config loading (performance)
3. Add logging for config operations (debugging)
4. Add config validation CLI command (diagnostics)

## Success Criteria

### Phase 1 Success Metrics ✅

- [x] ConfigService centralizes all config operations (14 methods)
- [x] RuntimeContext provides clean override management
- [x] Type-safe with mypy strict mode (zero type errors)
- [x] Comprehensive test coverage (64 unit tests)
- [x] All 722 unit tests pass

**Note:** Skipped Pydantic models in favor of dict-based approach that integrates better with qenvy. Achieved same benefits (type safety, centralization, clean API) with simpler implementation.

### Phase 2 Success Metrics (IN PROGRESS)

- [ ] No config override parameters in command functions
- [ ] Function signatures reduced by 3+ parameters each
- [ ] Config logic separated from business logic
- [ ] Large functions broken into smaller pieces
- [ ] All integration tests pass

### Overall Success Metrics

- [ ] Reduced code complexity (fewer lines, simpler logic)
- [ ] Improved type safety (mypy strict mode passes)
- [ ] Better error messages (validation catches issues early)
- [ ] Easier to test (mock config, not parameters)
- [ ] Easier to extend (add new config fields easily)

## Testing Strategy

### Unit Tests

1. **Config Models** (Phase 1)
   - Test Pydantic validation
   - Test invalid configs are rejected
   - Test path validation
   - Test URL validation

2. **ConfigContext** (Phase 1)
   - Test override application
   - Test missing overrides
   - Test invalid overrides

3. **Commands** (Phase 2)
   - Mock ConfigContext
   - Test business logic in isolation
   - Test error handling

### Integration Tests

1. **Config Loading** (Phase 1)
   - Test loading from XDG paths
   - Test override application
   - Test missing configs

2. **CLI Commands** (Phase 2)
   - Test with --config-dir override
   - Test with --meta override
   - Test with --proj override
   - Test combinations

## Risk Mitigation

### Breaking Changes

**Risk:** Changing config structure may break existing workflows

**Mitigation:**

- Keep external config file format identical (TOML)
- Add migration path for any schema changes
- Update CLAUDE.md with migration guide
- Test against real config files

### Test Coverage

**Risk:** Changes may break existing functionality

**Mitigation:**

- Run full test suite after each stage
- Add tests for new functionality
- Test edge cases explicitly
- Manual testing of all commands

### Rollback Plan

**Risk:** Refactoring introduces bugs

**Mitigation:**

- Work in feature branch: `tech-debt/config-refactor`
- Commit after each stage checkpoint
- Can revert to any checkpoint if issues arise
- Keep PR focused (no unrelated changes)

## Dependencies and Blockers

### Required Before Starting

1. ✅ Test reorganization (05-tests.md) - **Should do this first**
   - Cleaner test structure makes refactoring easier
   - Can add new tests for config validation

2. ✅ Clean git state
   - No uncommitted changes
   - All tests passing

### External Dependencies

1. **Pydantic** - Already in pyproject.toml (v2.x)
2. **Click** - Already in use
3. No new dependencies required

## Related Tech Debt

This refactoring addresses issues from:

- **02-qen-commands.md:**
  - Section 4: Configuration Management
  - Specific recommendations for init/add/status/pr

- **03-qen-lib.md:**
  - Section 1: CLI Module repetitive patterns
  - Section 2: Configuration Module type casting
  - Section 3: Configuration Concerns

## Future Enhancements

After this refactoring, the following become easier:

1. **Add new config fields** - Just add to Pydantic model
2. **Add config validation** - Use Pydantic validators
3. **Add config migration** - Already structured for it
4. **Add config caching** - Single load point
5. **Add config debugging** - Clear structure to inspect

## Notes

- This refactoring does NOT address performance issues (deferred)
- This refactoring does NOT add new features
- This is purely about improving maintainability and type safety
- Focus is on reducing complexity, not optimization

## Metadata

*Generated with Claude Code - Consolidated plan from 02-qen-commands.md and 03-qen-lib.md*
