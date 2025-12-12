# Integration Test Strategy for Per-Project Meta Architecture

**Date:** 2025-12-11
**Status:** Recommendation
**Context:** PR #10 implemented per-project meta architecture. All 6 init integration tests pass. 33 other integration tests need updating.

---

## Executive Summary

**Recommendation: FIX, don't delete and rewrite**

The current integration tests are well-structured and follow correct testing philosophy (NO MOCKS). They just need systematic updates to work with per-project metas instead of meta prime.

**Key Insight:** Your `test_init.py` fixes establish the correct pattern. Apply this same pattern to all other tests.

---

## Why Fix Instead of Rewrite?

### Tests Are Well-Designed

1. **Real operations** - No mocks, real git commands, real GitHub API
2. **Good coverage** - Test happy paths, edge cases, error handling
3. **Clear documentation** - Docstrings explain what each test validates
4. **Proven patterns** - Standard PR optimization (fast, stable tests)

### The Changes Are Mechanical

All failing tests have the **same root cause**: they look for project directories in `meta_repo/proj/` instead of `per_project_meta/proj/`.

The fix is a **simple, systematic pattern**:

```python
# OLD (meta prime):
proj_dir = meta_repo / "proj" / branch_name
repo_path = proj_dir / "repos" / "qen-test"

# NEW (per-project meta):
per_project_meta = meta_repo.parent / f"meta-{project_name}"
proj_dir = per_project_meta / "proj" / branch_name
repo_path = proj_dir / "repos" / "qen-test"
```

### Rewriting Would Lose Value

- **Time investment**: 8 test files, ~972 lines of well-crafted tests
- **Domain knowledge**: Tests encode understanding of edge cases
- **Standard PR optimization**: Already implemented (3s vs 26s speedup)
- **Risk**: New tests might miss edge cases the current tests catch

---

## Test Files That Need Updates

### Category 1: Direct Path Fixes (Simple)

These tests just need path updates to use per-project meta:

1. **test_add.py** (8 tests) - Add repos to per-project meta
   - Change: `proj_dir = meta_repo / "proj" / ...` → `per_project_meta / "proj" / ...`
   - Complexity: LOW (mechanical find/replace pattern)

2. **test_status.py** (7 tests) - Check status in per-project meta
   - Change: Same path update pattern
   - Complexity: LOW

3. **test_rm_real.py** (10 tests) - Remove repos from per-project meta
   - Change: Same path update pattern
   - Complexity: LOW

4. **test_qen_wrapper.py** (5 tests) - Test wrapper in per-project meta
   - Change: Same path update pattern
   - Complexity: LOW

### Category 2: Standard PR Fixes (Moderate)

These tests use optimized standard PRs and need:

- Path updates to per-project meta
- Helper function updates

5. **test_pull.py** (3 tests) - Pull into per-project meta
   - Change: Update `setup_test_project_optimized()` helper
   - Change: Path updates in each test
   - Complexity: MODERATE (helper function shared)

### Category 3: Already Working (No Changes)

6. **test_init.py** (6 tests) - ✅ Already fixed in PR #10
7. **test_pr_status.py** (3 tests) - ✅ Uses standard PRs, likely works
8. **test_github_schema.py** (2 tests) - ✅ Direct GitHub API, no meta path deps
9. **test_branch_checking.py** (1 test) - ⚠️ ERROR, needs investigation

---

## The Fix Pattern (Template)

### Step 1: Update Test Setup

```python
# In every test that creates a project:

# AFTER this line:
result = run_qen(
    ["init", "test-project", "--yes"],
    temp_config_dir,
    cwd=meta_repo,
)
assert result.returncode == 0

# ADD these lines to get per-project meta path:
date_prefix = datetime.now().strftime("%y%m%d")
branch_name = f"{date_prefix}-test-project"
per_project_meta = meta_repo.parent / "meta-test-project"
```

### Step 2: Update Project Directory References

```python
# OLD:
proj_dir = None
for item in (meta_repo / "proj").iterdir():
    if item.is_dir() and "test-project" in item.name:
        proj_dir = item
        break

# NEW:
proj_dir = per_project_meta / "proj" / branch_name
assert proj_dir.exists(), f"Project directory not found: {proj_dir}"
```

### Step 3: Update Repository Path References

```python
# OLD:
repo_path = proj_dir / "repos" / "main" / "qen-test"

# NEW (same - no change needed once proj_dir is correct):
repo_path = proj_dir / "repos" / "main" / "qen-test"
```

### Step 4: Verify Git Operations

If test checks git operations in meta repo:

```python
# Git operations should now check per-project meta, not meta prime:

# Check branch exists in per-project meta
branches_result = subprocess.run(
    ["git", "branch", "--list", branch_name],
    cwd=per_project_meta,  # Changed from meta_repo
    capture_output=True,
    text=True,
    check=True,
)
```

---

## Implementation Tasks

### Phase 1: Quick Wins (Est: 2-3 hours)

**Task 1.1: Fix test_add.py (8 tests)**

Apply the fix pattern to all 8 tests:

- `test_add_with_full_https_url`
- `test_add_with_ssh_url`
- `test_add_with_short_format`
- `test_add_with_custom_branch`
- `test_add_with_custom_path`
- `test_add_multiple_repos_with_indices`
- `test_add_invalid_url_error_handling`
- `test_add_nonexistent_repo_error_handling`

**Pattern:**

1. After `qen init <project>`, compute per-project meta path
2. Replace `meta_repo / "proj"` with `per_project_meta / "proj"`
3. Update any git operations to use `per_project_meta`

**Task 1.2: Fix test_status.py (7 tests)**

Apply the same pattern:

- `test_status_basic_clean_repos`
- `test_status_with_modified_files`
- `test_status_verbose_mode`
- `test_status_meta_only`
- `test_status_repos_only`
- `test_status_multiple_repos_with_indices`
- `test_status_with_nonexistent_repo`

**Task 1.3: Fix test_rm_real.py (10 tests)**

Apply the same pattern to all rm tests.

**Task 1.4: Fix test_qen_wrapper.py (5 tests)**

Apply the same pattern to wrapper tests.

**Success Criteria:**

- All tests in Phase 1 pass
- Tests still use real operations (NO MOCKS)
- Tests validate per-project meta isolation

---

### Phase 2: Standard PR Tests (Est: 1-2 hours)

**Task 2.1: Fix test_pull.py helper function**

Update `setup_test_project_optimized()` helper:

```python
def setup_test_project_optimized(
    tmp_path: Path, temp_config_dir: Path, project_suffix: str
) -> tuple[Path, Path, Path]:  # ← Add per_project_meta to return
    """Create a test meta repo and project for integration testing.

    Returns:
        Tuple of (meta_repo_path, per_project_meta_path, project_dir_path)
    """
    # ... existing setup code ...

    # After creating project, compute per-project meta path
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    per_project_meta = meta_repo.parent / f"meta-{project_name}"

    # Find project directory in per-project meta
    project_dir = per_project_meta / "proj" / branch_name

    return meta_repo, per_project_meta, project_dir
```

**Task 2.2: Update all pull tests**

Update 3 tests to use the new helper return value:

- `test_pull_updates_pr_metadata_standard`
- `test_pull_with_failing_checks_standard`
- `test_pull_detects_issue_from_branch_standard`

**Task 2.3: Update clone helper**

Update `clone_standard_branch()` if it makes assumptions about paths.

**Success Criteria:**

- All pull tests pass
- Tests still use standard PRs (fast, stable)
- Tests still use real GitHub API (NO MOCKS)

---

### Phase 3: Investigation (Est: 30 min)

**Task 3.1: Investigate test_branch_checking.py ERROR**

Currently shows ERROR (not FAILED), suggesting exception before test runs.

**Investigation steps:**

1. Run test with `-vv` to see full traceback
2. Check if it's a setup fixture issue
3. Check if it needs per-project meta updates
4. Fix based on findings

**Success Criteria:**

- Test runs without ERROR
- Test either passes or shows clear FAILED reason

---

### Phase 4: Validation (Est: 30 min)

**Task 4.1: Run full integration test suite**

```bash
./poe test-integration
```

**Task 4.2: Verify test count and pass rate**

Expected results:

- 39 total integration tests
- All tests pass
- All tests still use real operations (NO MOCKS)

**Task 4.3: Update test documentation**

Add note to test files:

```python
"""
Integration tests for qen <command> using per-project meta architecture.

These tests validate the per-project meta clone model where each project
has its own physical clone of the meta repository at meta-{project}/.

NO MOCKS ALLOWED. These tests use real git operations.
"""
```

---

## File URL Approach (Already Correct)

Your use of `file://` URLs in test fixtures is **correct** and should be **kept**:

```python
# In tmp_meta_repo fixture:
subprocess.run(
    ["git", "remote", "add", "origin", f"file://{meta_dir}"],
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
```

**Why this is correct:**

- Tests the git clone mechanism (real operation)
- Tests per-project meta creation (real directory)
- Tests git operations on cloned repo (real git)
- Avoids network dependencies
- Avoids GitHub authentication requirements
- Much faster than network clones

**What it validates:**
✅ Clone functionality works
✅ Per-project meta directories are created correctly
✅ Git operations work in cloned repos
✅ Project isolation is maintained

**What it doesn't validate:**
❌ Network connectivity (not needed for these tests)
❌ GitHub authentication (not relevant for init tests)

The tests that **do** need real GitHub (like `test_pr_status.py`) already use real GitHub repos and real PRs.

---

## Verification Checklist

After completing all phases:

- [ ] All 39 integration tests pass
- [ ] No mocks introduced (tests still use real operations)
- [ ] Tests validate per-project meta isolation
- [ ] Tests use `file://` URLs for local cloning (fast, reliable)
- [ ] Tests use real GitHub API for PR/status checks
- [ ] Test documentation updated to reflect per-project meta architecture
- [ ] All tests run in reasonable time (< 30s total)

---

## Risk Assessment

### Low Risk: Simple Path Updates

- **Risk:** Breaking test coverage
- **Mitigation:** The fix pattern is mechanical and obvious
- **Verification:** Tests fail with clear path errors if wrong

### Low Risk: Loss of Test Value

- **Risk:** Tests no longer validate real behavior
- **Mitigation:** We're only changing paths, not testing philosophy
- **Verification:** All tests still use real operations (NO MOCKS)

### Low Risk: Time Investment

- **Risk:** Taking too long to fix
- **Mitigation:** Pattern is established, changes are mechanical
- **Estimate:** 4-6 hours total for all phases

---

## Alternative: Rewrite Strategy (NOT RECOMMENDED)

If you chose to rewrite instead of fix:

### What You'd Lose

1. **Test coverage** - Current tests cover many edge cases
2. **Standard PR optimization** - Already working, saves 20s+ per test
3. **Proven patterns** - Tests have caught real bugs
4. **Time investment** - ~972 lines of well-crafted tests

### What You'd Gain

1. **Clean slate** - Could reorganize test structure
2. **Consistency** - All tests written for new architecture

### Bottom Line

**Rewriting would cost more time and risk losing test coverage for minimal gain.**

---

## Recommendation Summary

✅ **FIX the existing tests using the established pattern from test_init.py**

**Rationale:**

1. Tests are well-designed and follow correct philosophy
2. The fix is mechanical and low-risk
3. Your test_init.py already proves the pattern works
4. Estimated 4-6 hours vs. unknown time to rewrite
5. No risk of losing test coverage

**Next Steps:**

1. Start with Phase 1 (test_add.py) - easiest wins
2. Verify pattern works on first file
3. Apply same pattern to remaining files
4. Update helper functions in Phase 2
5. Validate all tests pass

---

## Appendix: Test File Summary

| File | Tests | Complexity | Est Time |
|------|-------|------------|----------|
| test_init.py | 6 | ✅ DONE | - |
| test_add.py | 8 | LOW | 1h |
| test_status.py | 7 | LOW | 1h |
| test_rm_real.py | 10 | LOW | 1h |
| test_qen_wrapper.py | 5 | LOW | 30m |
| test_pull.py | 3 | MODERATE | 1h |
| test_branch_checking.py | 1 | UNKNOWN | 30m |
| test_pr_status.py | 3 | ✅ LIKELY OK | - |
| test_github_schema.py | 2 | ✅ OK | - |
| **TOTAL** | **39** | | **5-6h** |

---

## Conclusion

Your instinct to question the approach was good, but the answer is clear: **the tests are sound, they just need systematic path updates**.

The `file://` URL approach is correct. The test structure is correct. Your test_init.py fixes are correct.

**Apply the same pattern to the remaining tests and you're done.**
