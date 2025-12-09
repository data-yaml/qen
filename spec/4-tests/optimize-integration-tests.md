# Integration Test Performance Optimization

## Executive Summary

**Current:** 68 seconds for 3 integration tests
**Optimized:** ~10 seconds (85% reduction)
**Method:** Use standard reference PRs instead of creating new PRs every test run

## Key Insight: We're Not Testing PR Creation

None of the slow tests are testing PR **creation**. They're testing PR **reading**:

- Reading PR metadata via `gh` CLI
- Parsing GitHub API responses
- Updating pyproject.toml with PR data
- Detecting check status (passing, failing, pending)

**Current waste:** Creating NEW PRs + waiting 10-20s for GitHub Actions = fixture overhead

**Solution:** Use permanent reference PRs that already exist in qen-test

## Standard Reference PRs Needed in qen-test

Create these permanent PRs (never close them):

```text
PR #1: "Reference: Passing Checks"
  Branch: ref-passing-checks
  Base: main
  Status: Open, all checks passing
  Purpose: Test reading PR with passing checks

PR #2: "Reference: Failing Checks"
  Branch: ref-failing-checks (contains "-failing-")
  Base: main
  Status: Open, checks failing (always-fail.yml triggers)
  Purpose: Test detecting failed checks

PR #3: "Reference: Issue Pattern"
  Branch: ref-issue-456-test
  Base: main
  Status: Open
  Purpose: Test issue number extraction from branch name

PR #4-6: "Reference: Stacked PRs"
  PR #4: ref-stack-a → main
  PR #5: ref-stack-b → ref-stack-a
  PR #6: ref-stack-c → ref-stack-b
  Status: Open stack of 3
  Purpose: Test stack detection
```

## Test-by-Test Analysis

### Test 1: test_pull_updates_pr_metadata (currently 21.20s)

**What it tests:** Does `qen pull` correctly read a PR and update pyproject.toml?

**Current approach:**

1. Create new PR with unique branch name
2. Wait 15s for GitHub Actions to start
3. Run `qen pull` and verify metadata

**Optimized approach:**

1. Clone existing `ref-passing-checks` branch
2. Add to pyproject.toml pointing at that branch
3. Run `qen pull` - it detects PR #1 immediately
4. Verify metadata

**Time:** 21.20s → ~3s (no PR creation, no waiting)

### Test 2: test_pull_with_failing_checks (currently 26.12s)

**What it tests:** Does `qen pull` correctly detect FAILING checks?

**Current approach:**

1. Create new PR with "-failing-" in name
2. Wait 20s for checks to fail
3. Run `qen pull` and verify failure detection

**Optimized approach:**

1. Clone existing `ref-failing-checks` branch
2. Add to pyproject.toml
3. Run `qen pull` - reads PR #2 (already has failed checks)
4. Verify failure detection

**Time:** 26.12s → ~3s

### Test 3: test_pull_detects_issue_from_branch (currently ~10s)

**What it tests:** Does `qen pull` extract issue number from branch name?

**Optimized approach:**

1. Clone existing `ref-issue-456-test` branch
2. Run `qen pull` - extracts issue from branch name
3. Verify issue=456 in metadata

**Time:** ~10s → ~3s

### Test 4: test_stacked_prs (currently 21.73s)

**What it tests:** Can we detect stacked PR relationships?

**Current approach:**

1. Create 3 new PRs in a stack
2. Wait 10s for GitHub to index
3. Verify stack structure via API

**Optimized approach:**

1. Just query existing PRs #4, #5, #6 via GitHub API
2. Verify stack structure (no creation needed!)

**Time:** 21.73s → ~2s (just API calls)

## The One Exception: Testing In-Progress Checks

**Test:** `test_check_slow_progress` (verifies we handle in-progress checks)

**Current approach:** Create PR, check while slow-check.yml is running (35s)

**Optimized approach:** Push a timestamp file to trigger workflow re-run

```bash
# In test: trigger new workflow run
echo "timestamp: $(date +%s)" > timestamp.txt
git add timestamp.txt
git commit -m "Trigger check re-run"
git push

# Wait ~2s for workflow to start (not finish!)
time.sleep(2)

# Verify check status is "IN_PROGRESS"
# This is FAST because we're not waiting for completion
```

**Time:** Don't need to wait for 35s check to complete - just verify it's IN_PROGRESS

## Implementation Plan

### Phase 1: Create Standard PRs in qen-test (ONE TIME SETUP)

**Action:** Manually create 6 reference PRs in data-yaml/qen-test

```bash
# In qen-test repo:
git checkout -b ref-passing-checks
git push -u origin ref-passing-checks
gh pr create --base main --title "Reference: Passing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

git checkout -b ref-failing-checks
git push -u origin ref-failing-checks
gh pr create --base main --title "Reference: Failing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

git checkout -b ref-issue-456-test
git push -u origin ref-issue-456-test
gh pr create --base main --title "Reference: Issue Pattern" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE."

# Create stacked PRs
git checkout -b ref-stack-a
git push -u origin ref-stack-a
gh pr create --base main --title "Reference: Stack A" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

git checkout -b ref-stack-b
git push -u origin ref-stack-b
gh pr create --base ref-stack-a --title "Reference: Stack B" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

git checkout -b ref-stack-c
git push -u origin ref-stack-c
gh pr create --base ref-stack-b --title "Reference: Stack C" \
  --body "Part of stacked PR reference. DO NOT CLOSE."
```

**Document PR numbers:** Update test constants

```python
# In tests/conftest.py or tests/integration/constants.py
STANDARD_PRS = {
    "passing": 1,      # Update with actual PR number
    "failing": 2,
    "issue": 3,
    "stack": [4, 5, 6],
}
```

### Phase 2: Add Helper Functions

**File:** `tests/conftest.py`

```python
def clone_standard_branch(
    project_dir: Path,
    branch: str,
    repo_name: str = "qen-test"
) -> Path:
    """Clone a standard reference branch for testing.

    Args:
        project_dir: Project directory path
        branch: Branch name (e.g., "ref-passing-checks")
        repo_name: Repository name

    Returns:
        Path to cloned repository
    """
    repos_dir = project_dir / "repos"
    repos_dir.mkdir(exist_ok=True)

    repo_path = repos_dir / repo_name
    subprocess.run(
        [
            "git", "clone", "--branch", branch,
            f"https://github.com/data-yaml/{repo_name}",
            str(repo_path)
        ],
        check=True,
        capture_output=True
    )

    # Configure git
    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=repo_path,
        check=True,
    )

    return repo_path


def verify_standard_pr_exists(pr_number: int) -> dict:
    """Verify standard reference PR exists and is open.

    Args:
        pr_number: PR number to verify

    Returns:
        PR data from GitHub API

    Raises:
        AssertionError: If PR doesn't exist or is closed
    """
    result = subprocess.run(
        [
            "gh", "pr", "view", str(pr_number),
            "--repo", "data-yaml/qen-test",
            "--json", "number,state,headRefName,baseRefName"
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    pr_data = json.loads(result.stdout)
    assert pr_data["state"] == "OPEN", \
        f"Standard PR #{pr_number} is not open (state={pr_data['state']})"

    return pr_data
```

### Phase 3: Rewrite Tests

**File:** `tests/integration/test_pull_lifecycle.py`

Create new test functions that use standard PRs:

```python
@pytest.mark.integration
def test_pull_updates_pr_metadata_standard(
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull reads standard PR and updates pyproject.toml.

    Uses permanent reference PR instead of creating new PR.
    This is MUCH faster (3s vs 21s) with no loss of test quality.
    """
    # Verify standard PR exists
    pr_data = verify_standard_pr_exists(STANDARD_PRS["passing"])

    # Setup test project
    meta_repo, project_dir = setup_test_project(
        tmp_path, temp_config_dir, "pull-standard-test"
    )

    # Clone standard branch (no PR creation!)
    branch = pr_data["headRefName"]  # "ref-passing-checks"
    clone_standard_branch(project_dir, branch)

    # Add to pyproject.toml
    add_repo_entry_to_pyproject(
        project_dir,
        url="https://github.com/data-yaml/qen-test",
        branch=branch,
        path="repos/qen-test"
    )

    # Run qen pull (reads EXISTING PR)
    result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30)
    assert result.returncode == 0, f"qen pull failed: {result.stderr}"

    # Verify metadata updated correctly
    pyproject = load_pyproject(project_dir / "pyproject.toml")
    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo = repos[0]

    # Verify PR metadata
    assert repo["pr"] == STANDARD_PRS["passing"]
    assert repo["pr_status"] == "open"
    assert repo["pr_checks"] in ["passing", "pending"]
    assert repo["pr_base"] == "main"

    # Verify issue not present (branch doesn't match pattern)
    assert "issue" not in repo

    # Verify updated timestamp
    assert "updated" in repo
    datetime.fromisoformat(repo["updated"].replace("Z", "+00:00"))
```

Similar rewrites for other tests.

### Phase 4: Keep Original Tests as Lifecycle Tests (Optional)

**File:** `tests/integration/test_pull_lifecycle.py`

Rename original tests and mark as `@pytest.mark.lifecycle`:

```python
@pytest.mark.lifecycle  # Run less frequently
@pytest.mark.integration
def test_pull_full_lifecycle_with_pr_creation(
    real_test_repo: Path,
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Full lifecycle test: create PR, wait for checks, run qen pull.

    This tests the ENTIRE workflow including PR creation.
    Runs less frequently (nightly) due to 20s runtime.
    """
    # Original test_pull_updates_pr_metadata implementation
    ...
```

### Phase 5: Update pytest Configuration

**File:** `pyproject.toml`

```toml
[tool.pytest.ini_options]
markers = [
    "integration: Integration tests using real GitHub API",
    "lifecycle: Full lifecycle tests (slow, run less frequently)",
]
```

**File:** `poe` task definitions (in pyproject.toml)

```toml
[tool.poe.tasks.test-integration]
cmd = "pytest tests/integration/ -v -m 'integration and not lifecycle'"
help = "Run fast integration tests (uses standard PRs)"

[tool.poe.tasks.test-lifecycle]
cmd = "pytest tests/integration/ -v -m lifecycle"
help = "Run slow lifecycle tests (creates PRs)"
```

## Expected Performance Results

### Before Optimization

- `test_pull_updates_pr_metadata`: 21.20s
- `test_pull_with_failing_checks`: 26.12s
- `test_pull_detects_issue_from_branch`: ~10s
- `test_stacked_prs`: 21.73s

**Total: ~79 seconds**

### After Optimization

- `test_pull_updates_pr_metadata_standard`: ~3s
- `test_pull_with_failing_checks_standard`: ~3s
- `test_pull_detects_issue_standard`: ~3s
- `test_stacked_prs_standard`: ~2s

**Total: ~11 seconds (86% reduction)**

## Quality Assurance

### What We Keep

1. ✅ Real GitHub API (no mocks)
2. ✅ Real `gh` CLI calls
3. ✅ Real check status parsing
4. ✅ Contract validation with GitHub
5. ✅ Real pyproject.toml updates
6. ✅ All assertions and verifications

### What We Change

1. ✅ Use existing PRs instead of creating new ones
2. ✅ No waiting for GitHub Actions (PRs already have completed checks)
3. ✅ Simpler test setup (just clone + verify)

### Risk Mitigation

**Risk:** Standard PRs could be closed accidentally

**Mitigation:**

1. Add prominent warning in PR description: "DO NOT CLOSE - Used by integration tests"
2. Add GitHub Actions workflow to reopen if closed
3. Add test startup check that verifies all standard PRs exist
4. Document PR numbers in test code

**Risk:** Checks on standard PRs could become stale

**Mitigation:**

1. GitHub Actions automatically re-run on every push to branch
2. Can manually trigger re-run if needed
3. Tests verify check data exists (not that it's recent)

## Success Criteria

1. ✅ Integration test suite runs in < 15 seconds (vs 68s currently)
2. ✅ No loss of test coverage or quality
3. ✅ All tests still use real GitHub API (no mocks)
4. ✅ Tests are more maintainable (simpler setup)
5. ✅ No increase in flakiness
6. ✅ Standard PRs are documented and protected

## Rollout Plan

### Week 1: Setup

- Day 1: Create 6 standard PRs in qen-test
- Day 2: Add helper functions to conftest.py
- Day 3: Write one standard test as proof of concept

### Week 2: Migration

- Day 1-3: Rewrite remaining tests to use standard PRs
- Day 4: Run both old and new tests in parallel
- Day 5: Verify performance gains

### Week 3: Cleanup

- Day 1: Mark old tests as `@pytest.mark.lifecycle`
- Day 2: Update CI to run standard tests by default
- Day 3: Document standard PR approach
- Day 4-5: Buffer for fixes

## Critical Files

### To Modify

- `tests/integration/test_pull_lifecycle.py` - Rewrite with standard PRs
- `tests/integration/test_pr_status_lifecycle.py` - Rewrite `test_stacked_prs`
- `tests/conftest.py` - Add helper functions
- `pyproject.toml` - Add pytest markers and poe tasks

### To Create

- `tests/integration/constants.py` - Standard PR numbers
- `tests/integration/test_pull_lifecycle.py` - Original tests (optional)
- `docs/STANDARD_PRS.md` - Document standard PR approach

### External

- `data-yaml/qen-test` repository - Create 6 standard PRs (one-time setup)
