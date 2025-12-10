# Auto-Initialization Implementation Specification

**Status:** Planning Complete
**Date:** 2025-12-09
**Version:** 1.0

## Problem Statement

Users encounter errors when running qen commands without having run `qen init` first:

```text
Error reading configuration: Failed to read main config: Main configuration does not exist
Hint: Run 'qen init' first to initialize qen.
```

This happens because all commands (`qen add`, `qen status`, `qen pull`, etc.) expect the main configuration file to exist at `$XDG_CONFIG_HOME/qen/main/config.toml`.

**User Impact:** Poor first-run experience - users must manually run `qen init` before any other command works.

## Solution Overview

Implement automatic initialization that:

1. Detects when main config doesn't exist
2. Automatically finds meta repository and extracts GitHub organization
3. Creates configuration silently in the background
4. Provides clear error messages when auto-init cannot work

## Architecture

### Core Component: `ensure_initialized()` Helper Function

**Location:** `src/qen/init_utils.py` (NEW FILE)

**Purpose:** Single entry point for all commands to guarantee configuration exists

**Function Signature:**

```python
def ensure_initialized(
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
    verbose: bool = False,
) -> QenConfig:
    """Ensure qen is initialized, auto-initializing if possible.

    Returns:
        QenConfig instance (guaranteed to have main config)

    Raises:
        click.Abort: If auto-init cannot be performed
    """
```

**Implementation Logic:**

```python
# 1. Create QenConfig instance
config = QenConfig(...)

# 2. Check if config exists - if yes, return immediately
if config.main_config_exists():
    return config

# 3. Attempt auto-initialization
if verbose:
    click.echo("Configuration not found. Auto-initializing...")

try:
    # Import here to avoid circular dependency
    from .commands.init import init_qen

    # Call existing init logic
    init_qen(verbose=False, ...)

    if verbose:
        click.echo("✓ Auto-initialized qen configuration")

    return config

except (NotAGitRepoError, MetaRepoNotFoundError) as e:
    # Cannot auto-init - provide helpful error message
    click.echo("Error: qen is not initialized.", err=True)
    click.echo(f"Reason: {e}", err=True)
    click.echo()
    click.echo("To initialize qen:", err=True)
    click.echo("  1. Navigate to your meta repository", err=True)
    click.echo("  2. Run: qen init", err=True)
    click.echo()
    click.echo("Or specify meta repo explicitly:", err=True)
    click.echo("  qen --meta /path/to/meta <command>", err=True)
    raise click.Abort() from e

except (AmbiguousOrgError, GitError) as e:
    # Cannot auto-init - ambiguous state
    click.echo("Error: Cannot auto-initialize qen.", err=True)
    click.echo(f"Reason: {e}", err=True)
    click.echo()
    click.echo("Please run 'qen init' manually to configure.", err=True)
    raise click.Abort() from e
```

## Implementation Plan

### Phase 1: Create Core Module

**File:** `src/qen/init_utils.py`

**Tasks:**

1. Create new file with proper imports
2. Implement `ensure_initialized()` function
3. Add comprehensive docstring
4. Handle all error cases with helpful messages

**Lines of Code:** ~100 lines

### Phase 2: Update Commands

Replace config initialization pattern in all command files:

**Commands to Update:**

| File | Lines | Current Pattern | Priority |
|------|-------|----------------|----------|
| [add.py](src/qen/commands/add.py) | 117-133 | QenConfig + check | High |
| [pull.py](src/qen/commands/pull.py) | 537-552 | QenConfig + check | High |
| [status.py](src/qen/commands/status.py) | ~307-320 | QenConfig + check | High |
| [sh.py](src/qen/commands/sh.py) | 45-57 | QenConfig + check | High |
| [workspace.py](src/qen/commands/workspace.py) | 232-248 | QenConfig + check | High |
| [commit.py](src/qen/commands/commit.py) | ~506-520 | QenConfig + check | Medium |
| [push.py](src/qen/commands/push.py) | ~262-275 | QenConfig + check | Medium |
| [pr.py](src/qen/commands/pr.py) | Multiple | QenConfig + check | Medium |
| [init.py](src/qen/commands/init.py) | 166-179 | Manual auto-init | Low |

**Old Pattern (before):**

```python
config = QenConfig(
    config_dir=config_dir,
    storage=storage,
    meta_path_override=meta_path_override,
    current_project_override=current_project_override,
)

if not config.main_config_exists():
    click.echo("Error: qen is not initialized. Run 'qen init' first.", err=True)
    raise click.Abort()

try:
    main_config = config.read_main_config()
except QenConfigError as e:
    click.echo(f"Error reading configuration: {e}", err=True)
    raise click.Abort() from e
```

**New Pattern (after):**

```python
from ..init_utils import ensure_initialized

config = ensure_initialized(
    config_dir=config_dir,
    storage=storage,
    meta_path_override=meta_path_override,
    current_project_override=current_project_override,
    verbose=verbose,
)

# Config is now guaranteed to exist
main_config = config.read_main_config()
```

**Changes per file:** Replace ~10-15 lines with ~5-7 lines

### Phase 3: Testing

#### New Test File: `tests/unit/qen/test_init_utils.py`

**Test Cases:**

1. **`test_ensure_initialized_config_exists`**
   - Config already exists
   - Should return immediately without calling `init_qen`
   - Verify no side effects

2. **`test_ensure_initialized_auto_init_success`**
   - Config doesn't exist
   - Mock successful auto-init
   - Verify `init_qen` called with correct parameters
   - Verify returns QenConfig instance

3. **`test_ensure_initialized_not_in_git_repo`**
   - Config doesn't exist
   - Mock `NotAGitRepoError`
   - Verify helpful error message shown
   - Verify `click.Abort` raised

4. **`test_ensure_initialized_no_meta_repo_found`**
   - Config doesn't exist
   - Mock `MetaRepoNotFoundError`
   - Verify helpful error message shown
   - Verify `click.Abort` raised

5. **`test_ensure_initialized_ambiguous_org`**
   - Config doesn't exist
   - Mock `AmbiguousOrgError`
   - Verify error message asks user to run `qen init` manually
   - Verify `click.Abort` raised

6. **`test_ensure_initialized_with_meta_override`**
   - Config doesn't exist
   - Provide `meta_path_override`
   - Verify override passed to `init_qen`
   - Verify auto-init succeeds

7. **`test_ensure_initialized_verbose_mode`**
   - Config doesn't exist
   - verbose=True
   - Verify progress messages shown
   - Verify success message shown

8. **`test_ensure_initialized_git_error`**
   - Config doesn't exist
   - Mock general `GitError`
   - Verify error handling

#### Update Existing Command Tests

For each command in `tests/unit/qen/commands/test_*.py`:

1. **Update fixtures** to mock `ensure_initialized` instead of `QenConfig`
2. **Add test:** `test_<command>_auto_initializes` - Verify auto-init called
3. **Add test:** `test_<command>_auto_init_fails` - Verify graceful error handling

**Example:**

```python
def test_add_auto_initializes(mocker, tmp_path):
    """Test that add command auto-initializes if config missing."""
    mock_ensure = mocker.patch("qen.commands.add.ensure_initialized")
    mock_config = mocker.Mock()
    mock_config.read_main_config.return_value = {
        "meta_path": str(tmp_path),
        "org": "test-org",
        "current_project": "test-project"
    }
    mock_ensure.return_value = mock_config

    # Run command
    result = add_repository("test-repo", ...)

    # Verify auto-init was called
    mock_ensure.assert_called_once()
```

## User Experience

### Scenario 1: Config Already Exists (Normal Operation)

```bash
$ qen status
Project: my-project
Branch: 251209-my-project
...
```

**Behavior:** No message, command proceeds immediately

### Scenario 2: First Run - Auto-Init Success

```bash
$ cd ~/GitHub/my-meta-repo
$ qen status
Project: my-project
Branch: 251209-my-project
...
```

**Behavior:** Silent auto-initialization, no output unless `--verbose`

### Scenario 3: First Run with Verbose

```bash
$ cd ~/GitHub/my-meta-repo
$ qen status --verbose
Configuration not found. Auto-initializing...
✓ Auto-initialized qen configuration
Project: my-project
Branch: 251209-my-project
...
```

**Behavior:** Shows progress, then proceeds

### Scenario 4: Auto-Init Fails - Not in Git Repo

```bash
$ cd /tmp
$ qen status
Error: qen is not initialized.
Reason: Not in a git repository.

To initialize qen:
  1. Navigate to your meta repository
  2. Run: qen init

Or specify meta repo explicitly:
  qen --meta /path/to/meta status
```

**Behavior:** Clear error with actionable guidance

### Scenario 5: Auto-Init Fails - Ambiguous Organization

```bash
$ cd ~/GitHub/my-meta-repo
$ qen status
Error: Cannot auto-initialize qen.
Reason: Multiple organizations detected in git remotes.

Please run 'qen init' manually to configure.
```

**Behavior:** Asks user to manually initialize

## Edge Cases

### Edge Case 1: Not in Git Repository

**Trigger:** User runs command outside any git repository

**Behavior:**

- Auto-init fails with `NotAGitRepoError`
- Show error: "Not in a git repository"
- Guide user to navigate to meta repo or use `--meta`

**Test:** `test_ensure_initialized_not_in_git_repo`

### Edge Case 2: In Git Repo But Not Meta Repo

**Trigger:** User in git repo without `proj/` directory

**Behavior:**

- Auto-init fails with `MetaRepoNotFoundError`
- Show error explaining meta repo requirements
- Guide user to correct location

**Test:** `test_ensure_initialized_no_meta_repo_found`

### Edge Case 3: Multiple Organizations in Git Remotes

**Trigger:** Meta repo has remotes from different GitHub organizations

**Behavior:**

- Auto-init fails with `AmbiguousOrgError`
- Ask user to run `qen init` manually to select org
- Cannot auto-determine which org to use

**Test:** `test_ensure_initialized_ambiguous_org`

### Edge Case 4: Auto-Init Success But No Current Project

**Trigger:** First run auto-inits, but no project created yet

**Behavior:**

- Config created successfully (meta_path, org stored)
- Command proceeds, may fail with "No active project"
- This is expected - user needs to run `qen init <project>`

**Test:** Existing command tests should handle this

### Edge Case 5: `--meta` Override Points to Non-Git Directory

**Trigger:** User provides `--meta /invalid/path`

**Behavior:**

- Auto-init fails with `NotAGitRepoError`
- Show error with the invalid path
- Guide user to correct path

**Test:** `test_ensure_initialized_invalid_meta_override`

## Implementation Order

### Step 1: Core Module (HIGH PRIORITY)

1. Create `src/qen/init_utils.py`
2. Implement `ensure_initialized()` function
3. Write comprehensive docstring
4. Handle all error cases

**Estimated Time:** 1-2 hours

### Step 2: First Command Update (VALIDATION)

1. Update `src/qen/commands/add.py` (simplest case)
2. Manually test with and without existing config
3. Verify auto-init works as expected
4. Verify error messages are helpful

**Estimated Time:** 30 minutes

### Step 3: Core Tests (HIGH PRIORITY)

1. Create `tests/unit/qen/test_init_utils.py`
2. Write all 8 test cases
3. Achieve 100% coverage of `ensure_initialized()`
4. Run: `./poe test tests/unit/qen/test_init_utils.py`

**Estimated Time:** 2-3 hours

### Step 4: Remaining Commands (SYSTEMATIC)

1. Update `pull.py`
2. Update `status.py`
3. Update `sh.py`
4. Update `workspace.py`
5. Update `commit.py`
6. Update `push.py`
7. Update `pr.py` (may have multiple locations)
8. Update `init.py` (replace manual auto-init)

**Estimated Time:** 2-3 hours

### Step 5: Command Tests (SYSTEMATIC)

1. Update test fixtures in each command test file
2. Add auto-init test cases
3. Verify all tests pass
4. Run: `./poe test tests/unit/qen/commands/`

**Estimated Time:** 2-3 hours

### Step 6: Integration Testing (VALIDATION)

1. Test in real environment (delete config, run commands)
2. Test with `--meta` override
3. Test error scenarios (not in git repo, etc.)
4. Verify user experience matches specification

**Estimated Time:** 1 hour

## Success Criteria

### Functional Requirements

- ✅ All commands auto-initialize when config missing
- ✅ Auto-init is silent by default
- ✅ Auto-init shows progress with `--verbose`
- ✅ Clear error messages when auto-init fails
- ✅ Works with `--meta` override
- ✅ No behavior change when config exists

### Technical Requirements

- ✅ Single `ensure_initialized()` function used by all commands
- ✅ No code duplication across commands
- ✅ 100% test coverage for `init_utils.py`
- ✅ All existing tests pass
- ✅ New tests for auto-init behavior

### User Experience Requirements

- ✅ First-run experience is seamless
- ✅ Users don't need to manually run `qen init` first
- ✅ Error messages provide actionable guidance
- ✅ Verbose mode explains what's happening

## Design Rationale

### Why This Approach?

1. **Matches Existing Pattern**
   - `init_project()` already has auto-init (lines 166-179 in init.py)
   - We're generalizing this pattern for all commands

2. **Single Point of Control**
   - One function to maintain and test
   - Easy to update error messages
   - Consistent behavior across all commands

3. **Explicit and Clear**
   - Commands explicitly call `ensure_initialized()`
   - Easy to understand control flow
   - No hidden magic in constructors

4. **Works with Overrides**
   - Seamlessly supports `--meta` runtime override
   - Passes through all configuration parameters
   - No special cases needed

5. **Excellent Error Messages**
   - Contextual guidance based on error type
   - Actionable steps for users
   - Explains what went wrong

6. **Minimal Code Changes**
   - Each command: ~10-15 lines replaced with ~5-7 lines
   - Net reduction in code
   - Improved maintainability

## Alternative Approaches Considered

### Alternative A: Auto-Init in QenConfig Constructor

**Pros:** Completely automatic, no command changes needed

**Cons:**

- Hidden behavior, harder to debug
- Difficult to provide good error messages
- Doesn't fit Click's error handling model
- Would make testing more complex

**Decision:** Rejected due to hidden behavior

### Alternative B: Decorator Pattern

**Pros:** Declarative, apply once per command

**Cons:**

- Decorator needs access to all config parameters
- Complex parameter passing
- Less explicit than direct function call

**Decision:** Rejected due to complexity

### Alternative C: Copy-Paste Auto-Init to Each Command

**Pros:** Simple, no new abstractions

**Cons:**

- Code duplication across 8+ files
- Hard to maintain consistent error messages
- Bug fixes need to be applied everywhere

**Decision:** Rejected due to duplication

## Critical Files

1. **`src/qen/init_utils.py`** - NEW - Core auto-init logic (~100 lines)
2. **`src/qen/commands/init.py`** - Contains `init_qen()` (lines 27-118) that will be reused
3. **`src/qen/commands/add.py`** - First command to update (lines 117-133)
4. **`src/qen/commands/pull.py`** - Lines 537-552 need update
5. **`src/qen/commands/status.py`** - Lines ~307-320 need update
6. **`src/qen/commands/sh.py`** - Lines 45-57 need update
7. **`src/qen/commands/workspace.py`** - Lines 232-248 need update
8. **`tests/unit/qen/test_init_utils.py`** - NEW - Test suite for auto-init

## References

- [QEN Configuration Management](../../src/qen/config.py)
- [Existing Init Implementation](../../src/qen/commands/init.py)
- [Git Utilities](../../src/qen/git_utils.py)
- [QEN Architecture Documentation](../../CLAUDE.md)
