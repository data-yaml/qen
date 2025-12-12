# Integration Test Fixture Refactoring Plan

**Date:** 2025-12-11
**Status:** Planning
**Context:** 30+ integration tests are failing because they duplicate meta repo setup logic with incorrect remote URLs. Tests need a shared fixture that handles per-project meta architecture correctly.

---

## Problem Analysis

### Current State (Anti-Pattern)

Every test in `test_add.py`, `test_status.py`, and `test_rm_real.py` duplicates this setup:

```python
# Create temporary meta repo
meta_repo = tmp_path / "meta"
meta_repo.mkdir()

# Initialize meta repo with git
subprocess.run(["git", "init", "-b", "main"], cwd=meta_repo, ...)
subprocess.run(["git", "config", "user.name", "Test User"], cwd=meta_repo, ...)
subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=meta_repo, ...)

# Create initial commit
meta_toml = meta_repo / "meta.toml"
meta_toml.write_text('[meta]\nname = "test-org"\n')
subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, ...)
subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=meta_repo, ...)

# Add remote (WRONG - uses HTTPS URL that doesn't exist)
subprocess.run(
    ["git", "remote", "add", "origin", "https://github.com/data-yaml/test-meta.git"],
    cwd=meta_repo, ...
)

# Initialize qen global config
result = run_qen(["init"], temp_config_dir, cwd=meta_repo)

# Create a project
result = run_qen(["init", "test-project", "--yes"], temp_config_dir, cwd=meta_repo)

# Find the project directory (complex iteration logic)
proj_dir = None
for item in (meta_repo / "proj").iterdir():
    if item.is_dir() and "test-project" in item.name:
        proj_dir = item
        break
```

**This is copy-pasted ~30 times across the codebase!**

### Why Tests Fail

`qen init <project>` now clones from the `origin` remote URL to create per-project meta clones. The tests set up:

- `origin` = `https://github.com/data-yaml/test-meta.git` (doesn't exist!)

Result: Clone fails with "Repository not found"

### What Works

`test_init.py` has this correct pattern:

```python
# Use file:// URL for local cloning (fast, no network)
subprocess.run(
    ["git", "remote", "add", "origin", f"file://{meta_dir}"],
    cwd=meta_dir, ...
)

# Also add a fake github remote for org extraction
subprocess.run(
    ["git", "remote", "add", "github", "https://github.com/test-org/test-meta.git"],
    cwd=meta_dir, ...
)
```

This allows:
✅ Fast local cloning via `file://` protocol
✅ Org extraction from GitHub URL format
✅ No network dependencies
✅ No authentication required

---

## Solution: Shared Fixture Architecture

### Design Principles

1. **Single Source of Truth**: One fixture creates meta repos correctly
2. **DRY**: Eliminate 100+ lines of duplicated setup code
3. **Reusable**: Works for all test scenarios (add, status, rm, pull)
4. **Composable**: Tests can customize project names as needed
5. **Correct**: Uses `file://` URLs like test_init.py
6. **Fast**: Local cloning is much faster than network operations

### Fixture Hierarchy

```
tmp_path (pytest built-in)
    ↓
temp_config_dir (existing fixture)
    ↓
tmp_meta_repo (NEW - creates meta prime with correct remotes)
    ↓
test_project (NEW - creates project in per-project meta)
```

---

## Implementation Plan

### Step 1: Create `tmp_meta_repo` Fixture

**Location:** `tests/conftest.py`

**Purpose:** Create a meta prime repository with correct remote configuration

**What it does:**

1. Creates temporary directory for meta repo
2. Initializes git with `main` branch
3. Configures git user (name/email)
4. Creates `meta.toml` file
5. Makes initial commit
6. **Sets up TWO remotes:**
   - `origin` = `file://{meta_dir}` (for cloning)
   - `github` = `https://github.com/test-org/test-meta.git` (for org extraction)
7. Returns `Path` to meta prime

**Signature:**

```python
@pytest.fixture
def tmp_meta_repo(tmp_path: Path) -> Path:
    """Create a temporary meta prime repository with correct remote setup."""
```

**Key Differences from Current Code:**

- Uses `file://` URL for origin remote (enables local cloning)
- Adds second remote for org extraction
- Single location means one place to fix/maintain

### Step 2: Create `test_project` Fixture

**Location:** `tests/conftest.py`

**Purpose:** Create a project in per-project meta clone, ready for testing

**What it does:**

1. Takes `tmp_meta_repo`, `temp_config_dir`, and `project_name` as parameters
2. Runs `qen init` (global config)
3. Runs `qen init <project>` (creates per-project meta clone)
4. Uses `get_per_project_meta_path()` helper to find paths
5. Returns tuple: `(meta_prime, per_project_meta, project_dir)`

**Signature:**

```python
@pytest.fixture
def test_project(
    tmp_meta_repo: Path,
    temp_config_dir: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path]:
    """Create a test project in per-project meta clone.

    Returns:
        Tuple of (meta_prime_path, per_project_meta_path, project_dir_path)
    """
```

**How tests customize project name:**

```python
@pytest.mark.parametrize("project_name", ["my-test"])
def test_something(test_project, project_name):
    meta_prime, per_project_meta, proj_dir = test_project
```

Or using indirect parametrization:

```python
@pytest.fixture
def project_name(request):
    return getattr(request, 'param', 'test-project')

def test_something(test_project):
    # Uses default name 'test-project'
```

### Step 3: Update All Tests Systematically

**Files to update:**

- `tests/integration/test_add.py` (8 tests)
- `tests/integration/test_status.py` (7 tests)
- `tests/integration/test_rm_real.py` (10 tests via helper)

**Pattern for each test:**

**Before:**

```python
def test_something(tmp_path: Path, temp_config_dir: Path):
    # 50+ lines of setup
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()
    # ... more setup ...

    # Test logic
    result = run_qen(["add", ...], temp_config_dir, cwd=meta_repo)
```

**After:**

```python
def test_something(test_project, temp_config_dir: Path):
    meta_prime, per_project_meta, proj_dir = test_project

    # Test logic (no setup needed!)
    result = run_qen(["add", ...], temp_config_dir, cwd=meta_prime)
```

**Lines saved per test:** ~45 lines
**Total lines eliminated:** ~1,200 lines

### Step 4: Update Helper Functions

**File:** `tests/integration/test_rm_real.py`

The `setup_rm_test_project()` helper can be **deleted entirely**. All tests can use the new fixture directly.

**Before:**

```python
def setup_rm_test_project(tmp_path, temp_config_dir, project_suffix):
    # 60 lines of setup
    ...
    return meta_repo, project_dir

def test_rm_by_index(tmp_path, temp_config_dir):
    meta_repo, project_dir = setup_rm_test_project(...)
```

**After:**

```python
def test_rm_by_index(test_project, temp_config_dir):
    meta_prime, per_project_meta, proj_dir = test_project
    # Start testing immediately
```

### Step 5: Update test_init.py (Optional)

**File:** `tests/integration/test_init.py`

Currently has its own `tmp_meta_repo` fixture. Can:

- **Option A:** Keep it (already works, uses same pattern)
- **Option B:** Switch to shared fixture (more consistent)

**Recommendation:** Keep it for now. It uses `file://` URLs correctly and doesn't need changes.

---

## Migration Strategy

### Phase 1: Create Fixtures (Est: 30 min)

1. Add `tmp_meta_repo` fixture to conftest.py
2. Add `test_project` fixture to conftest.py
3. Write fixture tests to verify they work

### Phase 2: Migrate test_add.py (Est: 45 min)

1. Update all 8 tests to use new fixture
2. Delete duplicated setup code
3. Run tests, verify they pass
4. Commit changes

### Phase 3: Migrate test_status.py (Est: 30 min)

1. Update all 7 tests to use new fixture
2. Delete duplicated setup code
3. Run tests, verify they pass
4. Commit changes

### Phase 4: Migrate test_rm_real.py (Est: 30 min)

1. Delete `setup_rm_test_project()` helper
2. Update all 10 tests to use new fixture
3. Run tests, verify they pass
4. Commit changes

### Phase 5: Validation (Est: 15 min)

1. Run full integration test suite
2. Verify all 39 tests pass
3. Verify no mocks were introduced
4. Update documentation

**Total Estimated Time:** 2.5 hours

---

## Benefits

### Immediate Benefits

✅ **Fixes all 30 failing tests** by using correct `file://` URLs
✅ **Eliminates 1,200+ lines** of duplicated code
✅ **Single point of maintenance** for meta repo setup
✅ **Faster tests** (local cloning vs network simulation)
✅ **Easier to understand** - setup is centralized

### Long-Term Benefits

✅ **Future tests are trivial** - just use the fixture
✅ **Changes propagate automatically** - fix once, all tests benefit
✅ **Consistent test quality** - everyone uses same setup
✅ **Follows pytest best practices** - fixtures for setup

### Code Quality Metrics

- **Lines of code:** -1,200 lines (-60%)
- **Duplication:** 0 (was: 30 copies)
- **Test maintainability:** High (single source of truth)
- **Test speed:** Faster (local file:// cloning)

---

## Alternative Approaches Considered

### Alternative 1: Fix URLs in place

**Approach:** Change HTTPS URLs to `file://` URLs in all 30 tests

**Pros:**

- Minimal changes
- Tests still work

**Cons:**

- Still 30 copies of setup code
- Still 1,200 lines of duplication
- Future tests will copy broken pattern
- Maintenance nightmare

**Decision:** ❌ Rejected (doesn't fix root cause)

### Alternative 2: Class-based fixtures

**Approach:** Use pytest class fixtures with setup/teardown

**Pros:**

- OOP approach
- State encapsulation

**Cons:**

- More complex than function fixtures
- Less idiomatic pytest
- Harder to compose

**Decision:** ❌ Rejected (over-engineered)

### Alternative 3: Parametrized factory fixture

**Approach:** Create factory function that returns configured fixtures

**Pros:**

- Very flexible
- Can customize everything

**Cons:**

- More complex
- Harder to understand
- Not needed for our use case

**Decision:** ❌ Rejected (unnecessary complexity)

---

## Success Criteria

### Must Have

- [ ] All 39 integration tests pass
- [ ] No mocks introduced (tests still use REAL operations)
- [ ] Duplicated setup code eliminated
- [ ] Tests run in <30 seconds total

### Should Have

- [ ] Fixtures well-documented with docstrings
- [ ] Example usage in fixture docstrings
- [ ] Commit messages explain changes

### Nice to Have

- [ ] Update AGENTS.md with new fixture pattern
- [ ] Add example test showing fixture usage

---

## Risk Assessment

### Low Risk: Breaking Existing Tests

- **Mitigation:** Migrate one file at a time
- **Verification:** Run tests after each file
- **Rollback:** Git revert if issues arise

### Low Risk: Fixture Complexity

- **Mitigation:** Keep fixtures simple and focused
- **Verification:** Write fixture tests first
- **Documentation:** Clear docstrings

### Low Risk: Test Isolation

- **Mitigation:** Use `tmp_path` (auto-cleanup)
- **Verification:** Tests don't share state
- **Pytest handles:** Fixture lifecycle

---

## Implementation Notes

### File:// URL Format

```python
# Correct
f"file://{absolute_path}"

# Examples
file:///tmp/pytest-123/meta
file:///Users/ernest/tmp/meta
```

### Remote Configuration Pattern

```python
# Origin for cloning (local)
git remote add origin file://{meta_dir}

# GitHub for org extraction (no cloning, just parsing)
git remote add github https://github.com/test-org/test-meta.git
```

### Fixture Dependency Chain

```
tmp_path (pytest)
    → tmp_meta_repo (creates meta prime)
        → test_project (creates per-project meta)
            → test (uses project)
```

### Test Parametrization Example

```python
# Custom project name per test
@pytest.mark.parametrize("project_name", ["proj-a", "proj-b"])
def test_with_custom_name(test_project, project_name):
    meta_prime, per_project_meta, proj_dir = test_project
    assert project_name in str(proj_dir)
```

---

## Conclusion

This refactoring:

1. **Fixes the immediate problem** (failing tests with wrong URLs)
2. **Eliminates technical debt** (1,200 lines of duplication)
3. **Establishes best practice** (shared fixtures)
4. **Improves maintainability** (single source of truth)
5. **Speeds up tests** (local cloning)

The investment is ~2.5 hours for long-term payoff in code quality and maintainability.

**Recommended approach:** Proceed with implementation in phases, one file at a time.
