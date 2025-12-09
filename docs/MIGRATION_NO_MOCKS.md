# Migration to NO MOCKS Integration Testing

## Summary

Successfully migrated QEN integration tests from mocked to real GitHub API testing strategy.

**Date:** 2025-12-06
**Status:** Complete - Awaiting qen-test repository workflow setup

## Changes Made

### 1. GitHub Actions Workflows for qen-test Repository

**Created:** `docs/qen-test-workflows/`

- `always-pass.yml` - Always passes
- `always-fail.yml` - Fails for branches with "-failing-"
- `slow-check.yml` - 35 second delay
- `README.md` - Setup instructions

**Next Step:** Deploy these to <https://github.com/data-yaml/qen-test>

### 2. Updated conftest.py

**File:** `tests/conftest.py`

**Added Real GitHub Fixtures:**

- `github_token()` - Get token from environment
- `real_test_repo()` - Clone actual qen-test repo
- `unique_prefix()` - Generate unique test branch prefix
- `cleanup_branches()` - Track and cleanup test branches

**Added Helper Functions:**

- `create_test_pr()` - Create real PR using gh CLI
- `create_pr_stack()` - Create PR stack (A→B→C)

**Kept Unit Test Fixtures:**

- `temp_git_repo()`
- `test_storage()`
- `test_config()`
- `meta_repo()`
- `child_repo()`

### 3. Rewrote Integration Tests

**File:** `tests/integration/test_pr_status_lifecycle.py`

**Removed:**

- All mock fixtures
- Mock data loading
- Subprocess mocking
- Local test repo setup

**Added:**

- `test_pr_with_passing_checks()` - Real GitHub Actions
- `test_pr_with_failing_checks()` - Branch name triggers failure
- `test_stacked_prs()` - Real PR stack creation
- `test_check_slow_progress()` - In-progress check handling

**All tests use:**

- Real `gh` CLI commands
- Real GitHub API
- Real qen-test repository
- NO MOCKS

### 4. Updated pyproject.toml

**File:** `pyproject.toml`

**Removed Tasks:**

- `setup-test-repo` - No longer needed
- `clean-test-repo` - No longer needed

**Updated Tasks:**

- `test` - Runs unit tests only (excludes integration)
- `test-unit` - Explicit unit tests only
- `test-integration` - Integration tests only (requires GITHUB_TOKEN)
- `test-all` - Run both unit and integration
- `test-cov` - Coverage for unit tests only
- `test-fast` - Fast unit tests only

**Updated Marker:**

```toml
markers = [
    "integration: marks tests as integration tests (slow, requires network, uses real GitHub API - NO MOCKS)",
]
```

### 5. Updated GitHub Actions Workflow

**File:** `.github/workflows/test.yml`

**Changes:**

- Split into separate jobs: `unit-tests` and `integration-tests`
- Unit tests: Run on all PRs, fast (10 min timeout)
- Integration tests: Run only on main branch, slower (15 min timeout)
- Integration tests require `GITHUB_TOKEN`
- Integration tests authenticate gh CLI

**Job Matrix:**

- Unit tests: Python 3.12, 3.13 on Ubuntu, macOS
- Integration tests: Python 3.12 on Ubuntu only

### 6. Updated AGENTS.md

**File:** `AGENTS.md`

**Added Section:** "Testing Philosophy"

- Unit Tests - Fast and Mocked
- Integration Tests - Real and Unmocked
- Hard requirements for integration tests
- Past production bugs explanation
- Test repository information
- Running test commands

**Updated:**

- Task table with new test commands
- Common development tasks
- Troubleshooting section
- Key reminders for AI agents

### 7. Created Documentation

**New Files:**

- `docs/INTEGRATION_TESTING.md` - Complete integration testing guide
- `docs/MIGRATION_NO_MOCKS.md` - This file
- `docs/qen-test-workflows/` - Workflows for test repository

## Files to Delete (Not Yet Done)

**Mock Infrastructure:**

- `scripts/setup_test_repo.py` - Mock test repo setup
- `scripts/clean_test_repo.py` - Mock test repo cleanup

**Reason for delay:** Want to verify new integration tests work first.

## Testing

### Unit Tests (Immediate)

```bash
# Run unit tests locally
./poe test

# Should pass without GITHUB_TOKEN
# Fast execution (< 5 minutes)
```

### Integration Tests (After qen-test Setup)

```bash
# 1. Deploy workflows to qen-test repository
# 2. Set GITHUB_TOKEN
export GITHUB_TOKEN="ghp_..."

# 3. Run integration tests
./poe test-integration

# Expected: 4 tests pass, ~2-3 minutes execution
```

## Success Criteria

- [x] conftest.py updated with real GitHub fixtures
- [x] Integration tests rewritten without mocks
- [x] pyproject.toml tasks updated
- [x] GitHub Actions workflow split into unit/integration
- [x] AGENTS.md updated with testing policy
- [x] Documentation created
- [ ] GitHub Actions workflows deployed to qen-test
- [ ] Integration tests pass in CI
- [ ] Mock infrastructure deleted

## Rollback Plan

If integration tests fail:

1. Revert conftest.py changes
2. Revert test_pr_status_lifecycle.py
3. Restore mock infrastructure scripts
4. Investigate issues with real GitHub API
5. Fix and redeploy

## Next Steps

### Immediate (Required)

1. Deploy workflows to data-yaml/qen-test repository:

   ```bash
   cd /tmp
   git clone https://github.com/data-yaml/qen-test
   cd qen-test
   mkdir -p .github/workflows
   cp /path/to/qen/docs/qen-test-workflows/*.yml .github/workflows/
   git add .github/workflows/
   git commit -m "Add GitHub Actions workflows for integration testing"
   git push origin main
   ```

2. Test locally with GITHUB_TOKEN:

   ```bash
   export GITHUB_TOKEN="ghp_..."
   ./poe test-integration
   ```

3. Verify CI passes after PR merge

### Follow-up (After Verification)

1. Delete mock infrastructure:

   ```bash
   git rm scripts/setup_test_repo.py
   git rm scripts/clean_test_repo.py
   git commit -m "Remove mock infrastructure - using real GitHub API"
   ```

2. Monitor integration test reliability for 2 weeks
3. Document any issues or improvements needed

## Risk Assessment

**Low Risk:**

- Unit tests unchanged (still use mocks)
- Integration tests marked separately
- Can run without integration tests if GITHUB_TOKEN missing
- Cleanup is best-effort (won't break tests)

**Medium Risk:**

- Dependency on external repository (qen-test)
- GitHub Actions must be enabled in qen-test
- Rate limiting possible (unlikely with auth)

**Mitigation:**

- Integration tests only run on main branch in CI
- Tests skip if GITHUB_TOKEN not set
- Unique branch names prevent conflicts
- Automatic cleanup after tests

## Timeline

- **2025-12-06:** Implementation complete
- **Next:** Deploy workflows to qen-test
- **Within 1 week:** Verify CI passes consistently
- **Within 2 weeks:** Delete mock infrastructure

## References

- **Specification:** `spec/2-status/07-repo-qen-test.md`
- **Integration Testing Guide:** `docs/INTEGRATION_TESTING.md`
- **Agent Guide:** `AGENTS.md` - Testing Philosophy
- **Test Repository:** <https://github.com/data-yaml/qen-test>
