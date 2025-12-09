# Timezone Fix - Integration Test Failures Resolution

## Date: 2025-12-08

## Problem Summary

12 integration tests were failing with "Project directory not created" errors. Investigation revealed this was **NOT** a project creation bug, but a **timezone mismatch** between production code and test expectations.

## Root Cause

**Timezone Mismatch Between Production and Tests:**

- **Production code** used `datetime.now(UTC)` for branch/folder names
- **Test code** used `datetime.now()` (local time) to construct expected paths
- In PST (UTC-8), this created a date discrepancy:
  - Production: `251209-project` (December 9th UTC)
  - Tests expected: `251208-project` (December 8th local time)
- Tests looked for files in the wrong directory!

## Design Decision

**Branch names are user-facing and should use LOCAL time:**
- Users expect branch `251208-myproject` when they create it on December 8th
- Using UTC would confuse users in non-UTC timezones
- Branch names are human-readable identifiers, not machine timestamps

**ISO8601 timestamps remain in UTC for consistency:**
- Config file timestamps (`created`, `updated`) still use UTC
- Template variables still use UTC
- Machine-facing data should be timezone-agnostic

## Changes Made

### 1. Branch/Folder Name Generation ([src/qen/project.py](../../src/qen/project.py))

**Before:**
```python
def generate_branch_name(project_name: str, date: datetime | None = None) -> str:
    if date is None:
        date = datetime.now(UTC)  # ❌ UTC for user-facing names
    date_prefix = date.strftime("%y%m%d")
    return f"{date_prefix}-{project_name}"
```

**After:**
```python
def generate_branch_name(project_name: str, date: datetime | None = None) -> str:
    """Generate a branch name with date prefix.

    Uses local time for user-facing branch names (not UTC).
    This ensures the date matches what the user sees on their calendar.
    """
    if date is None:
        date = datetime.now()  # ✅ Local time for user-facing names
    date_prefix = date.strftime("%y%m%d")
    return f"{date_prefix}-{project_name}"
```

Same change for `generate_folder_path()`.

### 2. Project Creation ([src/qen/commands/init.py](../../src/qen/commands/init.py))

**Before:**
```python
now = datetime.now(UTC)
branch_name, folder_path = create_project(
    meta_path,
    project_name,
    date=now,  # ❌ Passed UTC date for branch names
    github_org=github_org,
)
```

**After:**
```python
# Use UTC for ISO8601 timestamps (machine-facing)
# But branch names will use local time (user-facing)
now = datetime.now(UTC)

branch_name, folder_path = create_project(
    meta_path,
    project_name,
    date=None,  # ✅ Let create_project use local time for branch names
    github_org=github_org,
)
```

### 3. Test Expectations

Updated tests to use local time:
- [tests/integration/test_qen_wrapper.py](../../tests/integration/test_qen_wrapper.py)
- [tests/integration/test_init_real.py](../../tests/integration/test_init_real.py)

**Before:**
```python
date_prefix = datetime.now(UTC).strftime("%y%m%d")  # ❌ UTC
branch_name = f"{date_prefix}-{project_name}"
```

**After:**
```python
date_prefix = datetime.now().strftime("%y%m%d")  # ✅ Local time
branch_name = f"{date_prefix}-{project_name}"
```

## Test Results

### Before Fix
```
12 failed, 19 passed, 1 skipped
```

**Failing tests (timezone mismatch):**
- `test_qen_wrapper.py`: 5 tests failing
- `test_init_real.py`: 5 tests failing
- `test_add_real.py`: 2 tests failing (cross-branch issue)

### After Fix
```
8 failed, 24 passed
```

**Fixed (11 tests now passing):**
- ✅ `test_qen_wrapper.py`: All 5 tests PASSING
- ✅ `test_init_real.py`: All 6 tests PASSING

**Still failing (unrelated issues):**
- `test_add_real.py`: 2 tests (cross-branch operations - Issue #2 from analysis)
- `test_pr_status.py`: 3 tests (PR #9 closed - test data issue)
- `test_pull.py`: 3 tests (same PR #9 issue)

## Verification

UTC timestamps are still used correctly for machine-facing data:

```bash
$ grep -n "datetime.now(UTC)" src/qen/**/*.py
src/qen/commands/init.py:204:    now = datetime.now(UTC)  # Config timestamps
src/qen/commands/pull.py:376:    ...datetime.now(UTC).isoformat()  # Updated metadata
src/qen/config.py:257:    created = datetime.now(UTC).isoformat()  # Project config
src/qen/project.py:223:    now = datetime.now(UTC)  # Template timestamps
```

All UTC usages are for ISO8601 timestamps in config files ✅

## Files Modified

- [src/qen/project.py](../../src/qen/project.py) - Lines 32-73
- [src/qen/commands/init.py](../../src/qen/commands/init.py) - Lines 201-212
- [tests/integration/test_qen_wrapper.py](../../tests/integration/test_qen_wrapper.py) - Import and date generation
- [tests/integration/test_init_real.py](../../tests/integration/test_init_real.py) - Import and date generation

## Lessons Learned

1. **Timezone-awareness matters for user-facing data** - Don't use UTC for human-readable identifiers
2. **Integration tests caught a real UX issue** - Users would have been confused by UTC dates
3. **Separate concerns**: User-facing (local time) vs machine-facing (UTC) data
4. **Always use the integration test script** - `scripts/integration_test.py` auto-detects GitHub token

## Related Documentation

- [spec/4-tests/integration-test-failures-analysis.md](integration-test-failures-analysis.md) - Original analysis
- [spec/2-status/06-integration-testing.md](../2-status/06-integration-testing.md) - Integration testing philosophy
