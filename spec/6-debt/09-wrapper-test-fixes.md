# Tech Debt: Wrapper Test Failures

> **PRIORITY: HIGH** - 6 integration tests failing due to per-project meta architecture mismatch. These tests expect wrapper scripts under `real_test_repo/proj/` but per-project meta puts projects elsewhere.

## Executive Summary

After implementing integration test refactoring (spec 08), 6 tests in `test_qen_wrapper.py` and `test_branch_checking.py` are failing. All failures stem from the same root cause: these tests use `real_test_repo` (data-yaml/qen-test) but expect to find project structures that only exist in per-project meta clones.

**Current State:**
- ✅ 39/45 integration tests passing (87%)
- ❌ 6 tests failing with same pattern: wrapper script not found at expected path
- ❌ Tests assume projects live in `real_test_repo/proj/{branch}/`
- ❌ Reality: projects live in `meta-{project}/proj/{branch}/` (per-project meta clone)

**Root Cause:**
The per-project meta architecture (spec 5-clone) introduced separation between:
1. **Meta prime** - User's main meta repository
2. **Per-project meta** - Cloned meta repositories in `meta-{project}/` siblings

Tests using `real_test_repo` (GitHub's qen-test) create projects but look for them in the wrong location.

## Failing Tests

All 6 failing tests follow the same pattern:

### 1. test_branch_checking.py::test_qen_config_switches_branch

**Location**: `tests/integration/test_branch_checking.py:17`

**Error**:
```text
AssertionError: Wrapper script not found: /tmp/pytest-.../qen-test/proj/251212-test-...-proj1/qen
```

**Problem**:
- Test runs `qen --meta real_test_repo init proj1`
- Expects wrapper at `real_test_repo/proj/{branch}/qen`
- Reality: wrapper is at `{meta_parent}/meta-proj1/proj/{branch}/qen`

### 2. test_qen_wrapper.py::test_qen_wrapper_generation

**Location**: `tests/integration/test_qen_wrapper.py:26`

**Error**:
```text
AssertionError: Wrapper script not found: /tmp/pytest-.../qen-test/proj/251212-test-...-wrapper-test/qen
```

**Problem**: Same as #1 - looking in `real_test_repo/proj/` instead of per-project meta.

### 3. test_qen_wrapper.py::test_qen_wrapper_help_command

**Location**: `tests/integration/test_qen_wrapper.py:112`

**Error**: Same pattern - wrapper not found in `real_test_repo/proj/`

### 4-5. test_qen_wrapper.py::test_qen_wrapper_works_from_different_cwd[parent/arbitrary]

**Location**: `tests/integration/test_qen_wrapper.py:185` (parametrized test)

**Error**: Same pattern for both parameter values (parent, arbitrary)

### 6. test_qen_wrapper.py::test_qen_wrapper_project_context

**Location**: `tests/integration/test_qen_wrapper.py:238`

**Error**: Same pattern - expects wrapper1 and wrapper2 in `real_test_repo/proj/`

## Architecture Analysis

### Current Per-Project Meta Flow

When you run `qen --meta /path/to/meta init myproject`:

```text
1. Read meta prime: /path/to/meta
2. Extract meta_remote, meta_parent from meta prime config
3. Clone to: {meta_parent}/meta-myproject/
4. Create branch: YYMMDD-myproject
5. Create project dir: {meta_parent}/meta-myproject/proj/YYMMDD-myproject/
6. Create wrapper: {meta_parent}/meta-myproject/proj/YYMMDD-myproject/qen
```

### What Tests Expect (Wrong)

```text
1. Use real_test_repo: /tmp/pytest-.../qen-test
2. Run: qen --meta real_test_repo init myproject
3. Look for wrapper: real_test_repo/proj/YYMMDD-myproject/qen ❌ WRONG PATH
```

### Why This Fails

The `--meta` flag specifies the **meta prime** to use for extracting configuration, but:
- Per-project meta clones are created as **siblings** to meta prime
- Clones use `meta_parent` from meta prime's config
- `real_test_repo` is a temp directory, so clones go to `{meta_parent}/meta-{project}/`
- Tests look in the wrong place: they check `real_test_repo/proj/` instead of the sibling clone

### Path Resolution Logic

From spec 5-clone:

```python
# Global config (extracted from meta prime)
meta_path = "/Users/ernest/GitHub/meta"  # Meta prime
meta_remote = "git@github.com:org/meta.git"
meta_parent = "/Users/ernest/GitHub"  # Where clones go
meta_default_branch = "main"

# Project config (for specific project)
name = "myproject"
repo = "/Users/ernest/GitHub/meta-myproject"  # Per-project meta clone (SIBLING)
branch = "251210-myproject"
folder = "proj/251210-myproject"
```

**Key Point**: `repo` field in project config points to the per-project meta clone, NOT to meta prime.

## Solution Options

### Option 1: Fix Tests to Use Per-Project Meta Paths ⭐ RECOMMENDED

**Approach**: Update failing tests to look for wrapper scripts in the correct per-project meta location.

**Changes Needed**:

1. **After creating project**, calculate per-project meta path:
   ```python
   # Instead of:
   project_dir = real_test_repo / "proj" / branch_name
   qen_wrapper = project_dir / "qen"

   # Do:
   per_project_meta = real_test_repo.parent / f"meta-{project_name}"
   project_dir = per_project_meta / "proj" / branch_name
   qen_wrapper = project_dir / "qen"
   ```

2. **Use helper function** from `tests/integration/helpers.py`:
   ```python
   from tests.integration.helpers import create_test_project

   # This returns (per_project_meta, project_dir) tuple
   per_project_meta, project_dir = create_test_project(
       real_test_repo,
       project_name,
       temp_config_dir,
   )
   qen_wrapper = project_dir / "qen"
   ```

3. **For multiple projects** (test_qen_wrapper_project_context):
   ```python
   # Create two projects
   _, project1_dir = create_test_project(real_test_repo, "proj1", temp_config_dir)
   _, project2_dir = create_test_project(real_test_repo, "proj2", temp_config_dir)

   wrapper1 = project1_dir / "qen"
   wrapper2 = project2_dir / "qen"
   ```

**Pros**:
- ✅ Tests match production architecture
- ✅ Uses existing helper functions
- ✅ Minimal changes (6 test functions)
- ✅ No changes to production code
- ✅ Tests validate actual user behavior

**Cons**:
- ❌ Slightly more complex test setup
- ❌ Need to track per-project meta paths

**Estimated Effort**: 2-3 hours

### Option 2: Use Simplified Test Setup (tmp_meta_repo fixture)

**Approach**: Switch failing tests from `real_test_repo` to `tmp_meta_repo` fixture which doesn't use per-project meta.

**Changes Needed**:

1. Replace `real_test_repo` fixture with `tmp_meta_repo` in 6 tests
2. Update test to work with local temp directory instead of remote GitHub repo
3. Tests would work with simple git repo instead of real GitHub integration

**Pros**:
- ✅ Simple path resolution (no per-project meta)
- ✅ Faster tests (no GitHub interaction)

**Cons**:
- ❌ **LOSES REAL GITHUB INTEGRATION** - violates NO MOCKS principle
- ❌ Tests no longer validate production wrapper behavior
- ❌ Doesn't test actual `qen --meta <repo>` flow users experience
- ❌ Against integration test philosophy

**Estimated Effort**: 1-2 hours

**Verdict**: ❌ NOT RECOMMENDED - violates integration test principles

### Option 3: Add Helper to Find Wrapper Automatically

**Approach**: Create a helper function that finds the wrapper script regardless of architecture.

**Changes Needed**:

1. Add helper to `tests/integration/helpers.py`:
   ```python
   def find_project_wrapper(
       meta_repo: Path,
       project_name: str,
   ) -> Path:
       """Find wrapper script for a project, handling per-project meta architecture.

       Looks in both:
       - Per-project meta: {meta_repo.parent}/meta-{project}/proj/{branch}/qen
       - Meta prime: {meta_repo}/proj/{branch}/qen (legacy)

       Returns path to wrapper script.
       Raises FileNotFoundError if not found.
       """
       from datetime import datetime

       date_prefix = datetime.now().strftime("%y%m%d")
       branch_name = f"{date_prefix}-{project_name}"

       # Try per-project meta first (current architecture)
       per_project_meta = meta_repo.parent / f"meta-{project_name}"
       per_project_wrapper = per_project_meta / "proj" / branch_name / "qen"
       if per_project_wrapper.exists():
           return per_project_wrapper

       # Try meta prime (shouldn't exist in new architecture)
       meta_prime_wrapper = meta_repo / "proj" / branch_name / "qen"
       if meta_prime_wrapper.exists():
           return meta_prime_wrapper

       raise FileNotFoundError(
           f"Wrapper not found for project {project_name}. "
           f"Tried: {per_project_wrapper}, {meta_prime_wrapper}"
       )
   ```

2. Update 6 tests to use helper:
   ```python
   # Instead of:
   project_dir = real_test_repo / "proj" / branch_name
   qen_wrapper = project_dir / "qen"
   assert qen_wrapper.exists()

   # Do:
   qen_wrapper = find_project_wrapper(real_test_repo, project_name)
   # Automatically finds wrapper in correct location
   ```

**Pros**:
- ✅ Encapsulates architecture complexity
- ✅ Handles both old and new architectures
- ✅ Reusable for future tests
- ✅ Clear error messages when wrapper not found

**Cons**:
- ❌ Hides important architectural details from tests
- ❌ Extra abstraction layer
- ❌ Doesn't expose per-project meta path for other test needs

**Estimated Effort**: 3-4 hours

### Option 4: Update qen CLI to Support --meta-parent Override

**Approach**: Allow tests to specify where per-project metas should be cloned.

**Changes Needed**:

1. Add `--meta-parent` flag to qen CLI:
   ```python
   @click.option('--meta-parent', type=click.Path(),
                 help='Override meta_parent for per-project meta clones')
   def init(project_name, meta_parent, ...):
       if meta_parent:
           # Clone to specified parent instead of using meta prime's config
           per_project_meta = Path(meta_parent) / f"meta-{project_name}"
   ```

2. Update tests to use `--meta-parent`:
   ```python
   result = run_qen([
       "--meta", str(real_test_repo),
       "--meta-parent", str(real_test_repo.parent),  # Put clones as siblings
       "init", project_name, "--yes"
   ], temp_config_dir)

   # Now wrapper is predictably at:
   per_project_meta = real_test_repo.parent / f"meta-{project_name}"
   project_dir = per_project_meta / "proj" / branch_name
   qen_wrapper = project_dir / "qen"
   ```

**Pros**:
- ✅ Tests have explicit control over clone location
- ✅ Useful for production use cases too
- ✅ Clear separation of concerns

**Cons**:
- ❌ Requires production code changes
- ❌ Adds complexity to CLI surface area
- ❌ Not addressing the real issue (tests looking in wrong place)
- ❌ Over-engineering for a test problem

**Estimated Effort**: 4-5 hours

**Verdict**: ❌ NOT RECOMMENDED - over-engineering

## Recommended Solution

**Option 1: Fix Tests to Use Per-Project Meta Paths**

This is the cleanest solution because:
1. ✅ Tests match production architecture exactly
2. ✅ No changes to production code needed
3. ✅ Uses existing helper functions from Phase 1 refactoring
4. ✅ Minimal changes (only 6 test functions)
5. ✅ Validates actual user workflows

## Implementation Plan

### Step 1: Update test_branch_checking.py (1 test)

**File**: `tests/integration/test_branch_checking.py`

**Current code** (lines 17-50):
```python
def test_qen_config_switches_branch(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    # ... project creation ...

    # ❌ WRONG: Looking in meta prime
    project_dir = tmp_meta_repo / "proj" / f"{date_prefix}-{proj1}"
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.exists(), f"Wrapper not found: {qen_wrapper}"
```

**Fixed code**:
```python
from tests.integration.helpers import create_test_project

def test_qen_config_switches_branch(
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
) -> None:
    # Create first project - returns per-project meta path
    per_project_meta1, project_dir1 = create_test_project(
        tmp_meta_repo,
        proj1,
        temp_config_dir,
    )

    # ✅ CORRECT: Wrapper is in per-project meta
    qen_wrapper1 = project_dir1 / "qen"
    assert qen_wrapper1.exists(), f"Wrapper not found: {qen_wrapper1}"

    # Create second project
    per_project_meta2, project_dir2 = create_test_project(
        tmp_meta_repo,
        proj2,
        temp_config_dir,
    )

    qen_wrapper2 = project_dir2 / "qen"
    assert qen_wrapper2.exists(), f"Wrapper not found: {qen_wrapper2}"
```

### Step 2: Update test_qen_wrapper.py::test_qen_wrapper_generation (1 test)

**File**: `tests/integration/test_qen_wrapper.py`

**Current code** (lines 26-75):
```python
def test_qen_wrapper_generation(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
) -> None:
    project_name = f"{unique_prefix}-wrapper-test"
    result = run_qen([
        "--meta", str(real_test_repo),
        "init", project_name, "--yes"
    ], temp_config_dir)

    # ❌ WRONG: Looking in real_test_repo
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    project_dir = real_test_repo / "proj" / branch_name
    qen_wrapper = project_dir / "qen"
```

**Fixed code**:
```python
from tests.integration.helpers import create_test_project

def test_qen_wrapper_generation(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
) -> None:
    project_name = f"{unique_prefix}-wrapper-test"

    # ✅ Use helper - returns correct paths
    per_project_meta, project_dir = create_test_project(
        real_test_repo,
        project_name,
        temp_config_dir,
    )

    # Track branch for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # ✅ CORRECT: Wrapper is in per-project meta
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.exists(), f"Wrapper not found: {qen_wrapper}"
```

### Step 3: Update test_qen_wrapper.py::test_qen_wrapper_help_command (1 test)

**Same pattern as Step 2** - replace manual path calculation with `create_test_project()` helper.

### Step 4: Update test_qen_wrapper.py::test_qen_wrapper_works_from_different_cwd (1 parametrized test)

**File**: `tests/integration/test_qen_wrapper.py:185`

**Current code**:
```python
def test_qen_wrapper_works_from_different_cwd(
    cwd_type: str,
    test_suffix: str,
    real_test_repo: Path,
    # ...
) -> None:
    project_name = f"{unique_prefix}-{test_suffix}"
    result = run_qen([...], temp_config_dir)

    # ❌ WRONG: Looking in real_test_repo
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    project_dir = real_test_repo / "proj" / branch_name
    qen_wrapper = project_dir / "qen"
```

**Fixed code**:
```python
from tests.integration.helpers import create_test_project

def test_qen_wrapper_works_from_different_cwd(
    cwd_type: str,
    test_suffix: str,
    real_test_repo: Path,
    # ...
) -> None:
    project_name = f"{unique_prefix}-{test_suffix}"

    # ✅ Use helper - returns correct paths
    per_project_meta, project_dir = create_test_project(
        real_test_repo,
        project_name,
        temp_config_dir,
    )

    # Track branch for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    cleanup_branches.append(branch_name)

    # ✅ CORRECT: Wrapper is in per-project meta
    qen_wrapper = project_dir / "qen"
    assert qen_wrapper.exists(), f"Wrapper not found: {qen_wrapper}"

    # Rest of test (cwd determination and wrapper execution) stays the same
```

### Step 5: Update test_qen_wrapper.py::test_qen_wrapper_project_context (1 test)

**File**: `tests/integration/test_qen_wrapper.py:238`

**Current code**:
```python
def test_qen_wrapper_project_context(
    real_test_repo: Path,
    # ...
) -> None:
    project1_name = f"{unique_prefix}-context-1"
    project2_name = f"{unique_prefix}-context-2"

    result1 = run_qen([...], temp_config_dir)
    result2 = run_qen([...], temp_config_dir)

    # ❌ WRONG: Looking in real_test_repo
    date_prefix = datetime.now().strftime("%y%m%d")
    branch1_name = f"{date_prefix}-{project1_name}"
    branch2_name = f"{date_prefix}-{project2_name}"

    project1_dir = real_test_repo / "proj" / branch1_name
    project2_dir = real_test_repo / "proj" / branch2_name

    wrapper1 = project1_dir / "qen"
    wrapper2 = project2_dir / "qen"
```

**Fixed code**:
```python
from tests.integration.helpers import create_test_project

def test_qen_wrapper_project_context(
    real_test_repo: Path,
    # ...
) -> None:
    project1_name = f"{unique_prefix}-context-1"
    project2_name = f"{unique_prefix}-context-2"

    # ✅ Use helper for both projects
    per_project_meta1, project1_dir = create_test_project(
        real_test_repo,
        project1_name,
        temp_config_dir,
    )

    per_project_meta2, project2_dir = create_test_project(
        real_test_repo,
        project2_name,
        temp_config_dir,
    )

    # Track branches for cleanup
    date_prefix = datetime.now().strftime("%y%m%d")
    branch1_name = f"{date_prefix}-{project1_name}"
    branch2_name = f"{date_prefix}-{project2_name}"
    cleanup_branches.extend([branch1_name, branch2_name])

    # ✅ CORRECT: Wrappers are in per-project metas
    wrapper1 = project1_dir / "qen"
    wrapper2 = project2_dir / "qen"
    assert wrapper1.exists(), f"wrapper1 not created at {wrapper1}"
    assert wrapper2.exists(), f"wrapper2 not created at {wrapper2}"
```

## Success Criteria

### Quantitative Metrics
- [ ] All 45 integration tests pass (100% pass rate)
- [ ] No new test failures introduced
- [ ] Test execution time unchanged (±5%)
- [ ] No changes to production code

### Qualitative Improvements
- [ ] Tests validate actual per-project meta architecture
- [ ] Test code uses consistent patterns (create_test_project helper)
- [ ] Wrapper script location logic is explicit and documented
- [ ] Tests fail with clear error messages showing actual vs expected paths

### Validation Tests
- [ ] Run `./poe test-integration` - all 45 tests pass
- [ ] Run `./poe test-integration tests/integration/test_qen_wrapper.py` - all 5 tests pass
- [ ] Run `./poe test-integration tests/integration/test_branch_checking.py` - test passes
- [ ] Verify pre-commit hooks still pass
- [ ] Manual review of changes for clarity

## Dependencies and Blockers

### Dependencies
- **Phase 1 completion** - `create_test_project()` helper exists in `tests/integration/helpers.py` ✅
- **Understanding of per-project meta** - See spec 5-clone ✅

### Potential Blockers
1. **Helper function needs enhancement**
   - Current `create_test_project()` may need updates if it doesn't return all needed paths
   - Mitigation: Review helper function first, update if needed

2. **Cleanup logic complexity**
   - Tests need to cleanup branches in per-project meta, not meta prime
   - Mitigation: Update cleanup_branches fixture to handle per-project meta paths

3. **Test isolation**
   - Multiple tests creating projects in same temp directory
   - Mitigation: Use unique project names (already done with unique_prefix fixture)

## Related Issues

### Related Specs
- `spec/5-clone/02-qen-clone-design.md` - Per-project meta architecture design
- `spec/5-clone/03-qen-clone-spec.md` - Per-project meta implementation spec
- `spec/6-debt/08-integration-tests.md` - Integration test tech debt (parent spec)

### Related Code
- `tests/integration/helpers.py` - Git and project setup helpers (Phase 1)
- `tests/integration/test_qen_wrapper.py` - 5 failing tests
- `tests/integration/test_branch_checking.py` - 1 failing test
- `src/qen/commands/init.py` - Per-project meta creation logic

## Metadata

**Document Created**: 2025-12-12
**Parent Spec**: spec/6-debt/08-integration-tests.md
**Failing Tests**: 6 (test_qen_wrapper.py: 5, test_branch_checking.py: 1)
**Priority**: High (blocks 100% test pass rate)
**Estimated Effort**: 2-3 hours
**Impact**: High (enables 100% test pass rate) / Low (no production changes)

---

*Spec written by Claude Sonnet 4.5 based on integration test refactoring results*
