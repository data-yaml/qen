# Command Initialization Inconsistency Analysis

## Problem Summary

QEN commands use two different initialization patterns that have subtle behavioral differences, leading to bugs where commands fail to find `pyproject.toml` files. This is particularly evident in the `commit` command failing while `status` works correctly.

**User-Reported Bug:**

```bash
$ ./qen status
# Works correctly - finds pyproject.toml and displays status

$ ./qen commit
Error: Failed to load repositories: pyproject.toml not found in /Users/ernest/GitHub/meta/proj/251209-tabulator-extra-cols
# Fails - uses wrong path (meta prime instead of per-project meta)
```

## Root Cause

Two initialization patterns coexist:

### Pattern 1: `ensure_initialized()` + `ensure_correct_branch()` (OLD)

Used by: `commit`, `push`, `pull`, `sh`, `rm`, `workspace`, `add` (partially)

**Code Path:**

```python
# commit.py:573
config = ensure_initialized(
    config_dir=overrides.get("config_dir"),
    meta_path_override=overrides.get("meta_path"),
    current_project_override=overrides.get("current_project"),
    verbose=False,
)
ensure_correct_branch(config, verbose=False)

# Get project info
main_config = config.read_main_config()
target_project = main_config.get("current_project")
project_config = config.read_project_config(target_project)
per_project_meta = Path(project_config["repo"])
project_dir = per_project_meta / project_config["folder"]
```

**Problem:** This pattern works correctly for path resolution, but doesn't properly handle the RuntimeContext abstraction.

### Pattern 2: `RuntimeContext` (NEW)

Used by: `status`, `init`, `pr` (partially), `add` (partially)

**Code Path:**

```python
# status.py:469
runtime_ctx = ctx.obj.get("runtime_context")

# Get project config
config_service = ctx.config_service
project_config = config_service.read_project_config(target_project)
per_project_meta = Path(project_config["repo"])
project_dir = per_project_meta / project_config["folder"]
```

**Advantage:** Cleaner abstraction, better separation of concerns, properly handles CLI overrides.

### The Bug Source

The bug appears to be a **misreported error message** rather than an actual path resolution bug:

1. Both patterns use the same path resolution logic:

   ```python
   per_project_meta = Path(project_config["repo"])
   project_dir = per_project_meta / project_config["folder"]
   ```

2. The error message in `pyproject_utils.py:63` shows the path passed to `load_repos_from_pyproject()`:

   ```python
   raise PyProjectNotFoundError(f"pyproject.toml not found in {project_dir}")
   ```

3. If the error says `/Users/ernest/GitHub/meta/proj/251209-tabulator-extra-cols`, this means:
   - Either `project_config["repo"]` = `/Users/ernest/GitHub/meta` (wrong!)
   - Or the project config wasn't loaded correctly

## Commands Audit

### Using `ensure_initialized()` Pattern (7 commands)

| Command | File | Lines | Notes |
|---------|------|-------|-------|
| `commit` | `commands/commit.py` | 573-581 | Uses old pattern |
| `push` | `commands/push.py` | 264-274 | Uses old pattern |
| `pull` | `commands/pull.py` | 538+ | Uses old pattern |
| `sh` | `commands/sh.py` | 63+ | Uses old pattern |
| `rm` | `commands/rm.py` | 428+ | Uses old pattern |
| `workspace` | `commands/workspace.py` | 234+ | Uses old pattern |
| `add` | `commands/add.py` | 136+ | Hybrid: creates RuntimeContext but also calls ensure_initialized |

### Using `RuntimeContext` Pattern (3 commands)

| Command | File | Lines | Notes |
|---------|------|-------|-------|
| `status` | `commands/status.py` | 469-471 | Pure RuntimeContext |
| `init` | `commands/init.py` | Multiple | Pure RuntimeContext |
| `pr` | `commands/pr.py` | 561-585 | Hybrid: supports both patterns for tests |

### Hybrid Commands

**`add` command:**

- Creates RuntimeContext (line 129)
- But also calls `ensure_initialized()` (line 136)
- Inconsistent approach

**`pr` command:**

- Accepts optional `runtime_ctx` parameter
- Falls back to `ensure_initialized()` if not provided
- Intentional for backward compatibility with tests

## Validation of Path Resolution

Let me trace through what SHOULD happen with a properly configured project:

**Project Config Structure:**

```toml
# ~/.config/qen/251209-tabulator-extra-cols/config.toml
name = "251209-tabulator-extra-cols"
branch = "251209-tabulator-extra-cols"
folder = "proj/251209-tabulator-extra-cols"
repo = "/Users/ernest/GitHub/meta-251209-tabulator-extra-cols"  # Per-project meta!
created = "2025-12-09T..."
```

**Expected Resolution:**

```python
per_project_meta = Path("/Users/ernest/GitHub/meta-251209-tabulator-extra-cols")
project_dir = per_project_meta / "proj/251209-tabulator-extra-cols"
# Result: /Users/ernest/GitHub/meta-251209-tabulator-extra-cols/proj/251209-tabulator-extra-cols
```

**Actual Error Message:**

```
pyproject.toml not found in /Users/ernest/GitHub/meta/proj/251209-tabulator-extra-cols
```

This indicates the `repo` field in the project config is pointing to the OLD meta prime path!

## Likely Real Problem

The project config is **outdated** and still points to meta prime:

```toml
# Old/incorrect config:
repo = "/Users/ernest/GitHub/meta"  # ❌ Meta prime, not per-project meta!

# Should be:
repo = "/Users/ernest/GitHub/meta-251209-tabulator-extra-cols"  # ✅ Per-project meta
```

**Why status works but commit fails:** Timing issue? Race condition? Or commit is getting a different config file?

## Testing Gap

**Critical Missing Tests:**

1. **No integration tests for `commit` command** - Would have caught this bug
2. **No integration tests for `status` command** - Would verify consistency
3. **No tests validating path resolution** - Would catch per-project vs meta prime confusion
4. **No tests checking error messages** - Would catch misleading error paths

From `AGENTS.md`:

> #### IMPORTANT: Integration tests are NOT run in CI
>
> - Run them manually when changing GitHub API integration code

But we SHOULD have integration tests for core commands like `status`, `commit`, `add` even if they're not in CI!

## Impact Assessment

### High Risk Commands (No Integration Tests)

These commands manipulate git state but have no integration tests:

1. **`commit`** - Commits changes across repos
2. **`push`** - Pushes branches to remote
3. **`pull`** - Pulls changes from remote
4. **`rm`** - Removes repositories
5. **`workspace`** - Manages workspaces

### Medium Risk Commands (Partial Tests)

1. **`add`** - Has unit tests but no integration tests
2. **`pr`** - Has integration tests for PR API, but not for local state

### Low Risk Commands (Good Coverage)

1. **`status`** - Used extensively in other tests as verification
2. **`init`** - Well tested in existing integration suite

## Recommendations

### Immediate Actions (Priority 1)

1. **Debug the actual project config** - Check what `repo` field contains:

   ```bash
   cat ~/.config/qen/251209-tabulator-extra-cols/config.toml | grep repo
   ```

2. **Add validation to config loading** - Warn if `repo` path looks wrong:

   ```python
   if "meta" in repo_path and not "meta-" in repo_path:
       click.echo("Warning: repo path may be incorrect (points to meta prime)")
   ```

3. **Add integration test for commit** - See next section

### Short Term (Priority 2)

4. **Standardize on RuntimeContext pattern** - Migrate all commands to use RuntimeContext
5. **Add integration tests for all git operations** - commit, push, pull, rm
6. **Add path validation helpers** - Ensure per-project meta vs meta prime distinction

### Long Term (Priority 3)

7. **Refactor common patterns** - Extract shared initialization logic
8. **Improve error messages** - Include more context about which config file was used
9. **Add config validation command** - `qen doctor` to check config health

## Integration Test Examples

### Test: Status and Commit Use Same Paths

```python
@pytest.mark.integration
def test_status_commit_consistency(temp_config_dir, real_test_repo):
    """Verify status and commit commands see same project directory."""
    # Create project
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "init", "test-project"],
        check=True,
        capture_output=True,
    )

    # Add a repo
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "add", real_test_repo],
        check=True,
    )

    # Status should work
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "status"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "test-project" in result.stdout

    # Create a change in per-project meta
    project_config_path = temp_config_dir / "test-project" / "config.toml"
    project_config = tomli.loads(project_config_path.read_text())
    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    # Create test file
    (project_dir / "test.txt").write_text("test content")

    # Commit should work and see the same directory
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "commit", "-m", "test"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "test.txt" in result.stdout or "Meta Repository" in result.stdout
```

### Test: Commit Validates Project Directory Exists

```python
@pytest.mark.integration
def test_commit_validates_project_dir(temp_config_dir):
    """Verify commit fails gracefully if project directory doesn't exist."""
    # Create malformed project config with wrong path
    project_name = "bad-project"
    project_dir = temp_config_dir / project_name
    project_dir.mkdir(parents=True)

    # Write config with non-existent repo path
    config_path = project_dir / "config.toml"
    config_path.write_text("""
name = "bad-project"
branch = "test-branch"
folder = "proj/bad-project"
repo = "/nonexistent/path/meta-bad-project"
created = "2025-01-01T00:00:00Z"
""")

    # Update main config to use this project
    main_config_path = temp_config_dir / "main" / "config.toml"
    main_config_path.parent.mkdir(parents=True, exist_ok=True)
    main_config_path.write_text("""
meta_path = "/some/path"
meta_remote = "git@github.com:org/meta.git"
meta_parent = "/some/parent"
meta_default_branch = "main"
org = "test-org"
current_project = "bad-project"
""")

    # Commit should fail with clear error
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "commit", "-m", "test"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "does not exist" in result.stderr or "not found" in result.stderr
```

## Success Criteria

1. ✅ All commands use consistent RuntimeContext pattern
2. ✅ Integration tests exist for: status, commit, add, push, pull, rm
3. ✅ Error messages clearly indicate which config file and path was used
4. ✅ Config validation catches meta prime vs per-project meta mistakes
5. ✅ `qen doctor` command validates all project configs

## Files to Review/Modify

### Commands to Migrate to RuntimeContext

1. `src/qen/commands/commit.py` - Remove ensure_initialized, use RuntimeContext
2. `src/qen/commands/push.py` - Remove ensure_initialized, use RuntimeContext
3. `src/qen/commands/pull.py` - Remove ensure_initialized, use RuntimeContext
4. `src/qen/commands/sh.py` - Remove ensure_initialized, use RuntimeContext
5. `src/qen/commands/rm.py` - Remove ensure_initialized, use RuntimeContext
6. `src/qen/commands/workspace.py` - Remove ensure_initialized, use RuntimeContext
7. `src/qen/commands/add.py` - Remove ensure_initialized, pure RuntimeContext

### New Integration Tests to Create

1. `tests/integration/test_commit.py` - Full commit command integration tests
2. `tests/integration/test_status.py` - Full status command integration tests
3. `tests/integration/test_add.py` - Full add command integration tests
4. `tests/integration/test_consistency.py` - Cross-command consistency tests

### Utilities to Add

1. `src/qen/validation.py` - Config validation helpers
2. `src/qen/commands/doctor.py` - Health check command

## Next Steps

1. Run diagnostic on user's actual config to confirm root cause
2. Write integration test that reproduces the bug
3. Fix the bug (likely config validation issue)
4. Begin RuntimeContext migration for remaining commands
5. Add comprehensive integration tests for all git operations
