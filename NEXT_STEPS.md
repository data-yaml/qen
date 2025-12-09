# Next Steps: Complete Integration Test Optimization

## Current Status

✅ **Code Implementation Complete**
- Helper functions added to `tests/conftest.py`
- Constants defined in `tests/integration/constants.py`
- Optimized tests created in `test_pull.py` and `test_pr_status.py`
- Old slow tests deleted (`test_pull_lifecycle.py` and `test_pr_status_lifecycle.py`)
- pytest configuration updated in `pyproject.toml`

⏳ **Standard PRs Need to Be Created** (One-Time Setup)

## Step 1: Create Standard Reference PRs

The optimized tests require 6 permanent reference PRs in the `data-yaml/qen-test` repository.

### Quick Setup Commands

```bash
# Clone qen-test repository
cd /tmp
git clone https://github.com/data-yaml/qen-test
cd qen-test

# Configure git (use your credentials)
git config user.email "ernest@quilt.bio"
git config user.name "Ernest Prabhakar"

# PR #7: Passing Checks
git checkout main && git pull
git checkout -b ref-passing-checks
echo "# Reference: Passing Checks" > test-data/ref-passing.txt
git add test-data/ref-passing.txt
git commit -m "Add reference PR for passing checks"
git push -u origin ref-passing-checks
gh pr create --base main --head ref-passing-checks \
  --title "Reference: Passing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

# PR #8: Failing Checks (note the "-failing-" pattern)
git checkout main
git checkout -b ref-failing-checks
echo "# Reference: Failing Checks" > test-data/ref-failing.txt
git add test-data/ref-failing.txt
git commit -m "Add reference PR for failing checks"
git push -u origin ref-failing-checks
gh pr create --base main --head ref-failing-checks \
  --title "Reference: Failing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

# PR #9: Issue Pattern
git checkout main
git checkout -b ref-issue-456-test
echo "# Reference: Issue Pattern" > test-data/ref-issue.txt
git add test-data/ref-issue.txt
git commit -m "Add reference PR for issue pattern"
git push -u origin ref-issue-456-test
gh pr create --base main --head ref-issue-456-test \
  --title "Reference: Issue Pattern" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

# PR #10: Stack A
git checkout main
git checkout -b ref-stack-a
echo "# Stack Level A" > test-data/ref-stack-a.txt
git add test-data/ref-stack-a.txt
git commit -m "Add stack level A"
git push -u origin ref-stack-a
gh pr create --base main --head ref-stack-a \
  --title "Reference: Stack A" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# PR #11: Stack B (based on stack-a)
git checkout ref-stack-a
git checkout -b ref-stack-b
echo "# Stack Level B" > test-data/ref-stack-b.txt
git add test-data/ref-stack-b.txt
git commit -m "Add stack level B"
git push -u origin ref-stack-b
gh pr create --base ref-stack-a --head ref-stack-b \
  --title "Reference: Stack B" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# PR #12: Stack C (based on stack-b)
git checkout ref-stack-b
git checkout -b ref-stack-c
echo "# Stack Level C" > test-data/ref-stack-c.txt
git add test-data/ref-stack-c.txt
git commit -m "Add stack level C"
git push -u origin ref-stack-c
gh pr create --base ref-stack-b --head ref-stack-c \
  --title "Reference: Stack C" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# Return to main
git checkout main

# Verify all PRs were created
gh pr list --repo data-yaml/qen-test --limit 20
```

**Expected Output:**
```text
#12  Reference: Stack C           ref-stack-c
#11  Reference: Stack B           ref-stack-b
#10  Reference: Stack A           ref-stack-a
#9   Reference: Issue Pattern     ref-issue-456-test
#8   Reference: Failing Checks    ref-failing-checks
#7   Reference: Passing Checks    ref-passing-checks
```

### Update PR Numbers if Needed

If the PR numbers differ from 7-12, update `/Users/ernest/GitHub/qen/tests/integration/constants.py`:

```python
STANDARD_PRS = {
    "passing": 7,  # Update to actual PR number
    "failing": 8,  # Update to actual PR number
    "issue": 9,    # Update to actual PR number
    "stack": [10, 11, 12],  # Update to actual PR numbers
}
```

## Step 2: Verify Optimized Tests Work

### Run Type Checking
```bash
cd /Users/ernest/GitHub/qen
./poe typecheck
```

Expected: No type errors.

### Run Integration Tests

```bash
./poe test-integration
```

**Expected Output:**
- 6 tests should pass
- Total time: ~10-15 seconds
- All tests use real GitHub API
- Tests: `test_pull.py` (3 tests) + `test_pr_status.py` (3 tests)

## Step 3: Measure Performance Improvement

### Run Optimized Tests

```bash
time ./poe test-integration
```

Note the total time (should be ~10-15 seconds).

**Expected Result:** Tests complete in ~10-15 seconds using standard PRs (85% faster than old approach).

## Step 4: Update CI Configuration (Optional)

If you have CI workflows, integration tests are now fast enough to run regularly:

```yaml
# .github/workflows/test.yml
- name: Run integration tests
  run: ./poe test-integration
```

## Step 5: Commit Changes

Once tests pass:

```bash
cd /Users/ernest/GitHub/qen

# Stage all changes
git add tests/integration/constants.py
git add tests/integration/test_pull.py
git add tests/integration/test_pr_status.py
git add tests/conftest.py
git add pyproject.toml
git add STANDARD_PRS_SETUP.md
git add INTEGRATION_TEST_OPTIMIZATION_SUMMARY.md
git add NEXT_STEPS.md

# Commit
git commit -m "feat: optimize integration tests with standard reference PRs

- Add standard PR constants and helper functions
- Create optimized test files (test_pull.py, test_pr_status.py)
- Delete old slow tests (test_pull_lifecycle.py, test_pr_status_lifecycle.py)
- Reduce integration test time from 68s to ~10-15s (85% improvement)

Tests still use real GitHub API (no mocks).
Standard PRs #7-12 created in data-yaml/qen-test."

# Push
git push origin integration-test-optimization
```

## Troubleshooting

### Tests Fail: "Standard PR not found"
- Verify standard PRs exist: `gh pr list --repo data-yaml/qen-test`
- Check PR numbers match constants.py
- Ensure PRs are OPEN (not closed)

### Tests Fail: "Branch not found"
- Verify branches exist: `git ls-remote --heads https://github.com/data-yaml/qen-test`
- Check branch names match STANDARD_BRANCHES in constants.py

### Tests Slow: "Still taking 60+ seconds"

- Verify that lifecycle test files have been deleted
- Check that optimized tests are being executed (should see `test_*_standard` in output)

### Type Errors
- Run `./poe typecheck` to identify issues
- Ensure all imports are correct
- Check that conftest.py helpers have proper type annotations

## Success Criteria Checklist

- [ ] Standard PRs #7-12 created in data-yaml/qen-test
- [ ] All 6 PRs are OPEN
- [ ] `./poe typecheck` passes
- [ ] `./poe test-integration` passes in ~10-15s
- [ ] Performance improvement measured (85% faster)
- [ ] Changes committed to git

## Questions?

See detailed documentation in:
- `/Users/ernest/GitHub/qen/INTEGRATION_TEST_OPTIMIZATION_SUMMARY.md` - Full implementation details
- `/Users/ernest/GitHub/qen/STANDARD_PRS_SETUP.md` - Complete PR setup guide
- `/Users/ernest/GitHub/qen/spec/4-tests/optimize-integration-tests.md` - Original optimization spec
