# Integration Testing with Real GitHub API

**Status:** Draft
**Created:** 2025-12-06
**Author:** Product Manager (AI Agent)

## Executive Summary

QEN's integration tests MUST use the real GitHub API. No mocks. Period.

We've had repeated production failures because mocked tests passed while real GitHub API calls failed. This spec defines our mock-free integration testing strategy using a dedicated test repository at https://github.com/data-yaml/qen-test.

## The Problem with Mocks

### Past Failures

**Production Bug #1 - Wrong Field Names**
```python
# Mock data had this:
mock_pr = {"state": "success"}  # ❌ Wrong!

# Real GitHub API has this:
real_pr = {"status": "completed", "conclusion": "success"}  # ✅ Correct
```

**Production Bug #2 - Missing Fields**
- Mocks omitted `mergeable` field
- Tests passed, production failed on merge conflicts
- Users reported bugs we thought we'd tested

**Production Bug #3 - API Schema Changes**
- GitHub changed check run structure
- Mocks weren't updated
- Integration tests passed
- Production broke for all users

### False Confidence

When integration tests use mocks:
- ✅ Tests pass in CI
- ✅ Code review approves
- ✅ Merge to main
- ❌ Production fails
- 😱 User reports bug
- 🔥 Emergency hotfix

## Testing Policy

### Unit Tests - Fast and Mocked

**Purpose:** Test individual functions and modules in isolation

**Characteristics:**
- Use mocks liberally for speed
- No network calls
- No external dependencies
- Run in milliseconds
- Run before every commit (pre-commit hook)

**Example:**
```python
def test_parse_pr_url(mocker):
    """Unit test - mock is fine here"""
    mock_gh = mocker.patch('qen.commands.status.run_gh_command')
    mock_gh.return_value = '{"number": 123}'

    result = parse_pr_url("https://github.com/org/repo/pull/123")
    assert result == 123
```

### Integration Tests - Real and Unmocked

**Purpose:** Validate our contract with GitHub's API

**HARD REQUIREMENTS:**
- ✅ **MUST use real GitHub API**
- ✅ **MUST use actual `gh` CLI commands**
- ✅ **MUST test against https://github.com/data-yaml/qen-test**
- ❌ **NO MOCKS ALLOWED**
- ❌ **NO MOCK DATA FILES**
- ❌ **NO MOCK `gh` COMMANDS**

**Example:**
```python
def test_pr_status_passing_checks(real_test_repo, unique_prefix, cleanup_branches):
    """Integration test - NO MOCKS"""
    # Create real branch
    branch = f"{unique_prefix}-passing"
    subprocess.run(["git", "checkout", "-b", branch], cwd=real_test_repo)

    # Create real PR via gh CLI
    pr_url = subprocess.run(
        ["gh", "pr", "create", "--base", "main", "--head", branch,
         "--title", "Test PR", "--body", "Integration test"],
        cwd=real_test_repo, capture_output=True, text=True
    ).stdout.strip()

    # Test real QEN command against real GitHub API
    result = subprocess.run(
        ["qen", "status", "--pr", pr_url],
        capture_output=True, text=True
    )

    assert "✓ All checks passed" in result.stdout
```

### Why This Matters

**The Contract with GitHub:**
- GitHub's API is our interface to the world
- If our understanding of that API is wrong, everything breaks
- Mocks let us lie to ourselves about what's real
- Only real API calls validate the contract

**Past Evidence:**
- 3 production bugs caused by mock/reality mismatch
- 0 bugs from unmocked integration tests
- Integration tests that use real API catch breaking changes immediately

## Test Repository: data-yaml/qen-test

### Purpose

A dedicated GitHub repository for integration testing QEN features:
- Pull request status checks
- Stacked PR detection
- PR merging and rebasing
- Branch management
- GitHub Actions workflows

**Repository:** https://github.com/data-yaml/qen-test

### Test Execution Model

Every integration test run follows this workflow:

```bash
#!/bin/bash
# 1. Clone real repo to /tmp
TEST_DIR="/tmp/qen-test-$(uuidgen)"
git clone https://github.com/data-yaml/qen-test "$TEST_DIR"

# 2. Generate unique prefix for this test run
PREFIX="test-$(date +%s)-$(uuidgen | cut -d- -f1)"

# 3. Create test branches with unique prefix
git checkout -b "${PREFIX}-passing-checks"
# ... make commits ...
git push -u origin "${PREFIX}-passing-checks"

# 4. Create real PRs using gh CLI
gh pr create --base main --head "${PREFIX}-passing-checks" ...

# 5. Run tests against REAL GitHub API
pytest tests/integration/

# 6. Cleanup - delete test branches
gh pr close <pr-url> --delete-branch

# 7. Remove cloned repo
rm -rf "$TEST_DIR"
```

### Key Principles

**Isolation:**
- Each test run uses unique prefix: `test-{timestamp}-{uuid}`
- No conflicts between parallel test runs
- Safe to run multiple times simultaneously

**Real API:**
- Actual `gh` commands (not mocked)
- Real GitHub Actions workflows
- Real PR states and check runs

**Cleanup:**
- Delete branches after test
- Close PRs after test
- Remove cloned repo
- Idempotent (can re-run safely)

**CI-Friendly:**
- Uses `GITHUB_TOKEN` from environment
- Works in GitHub Actions
- Handles rate limits gracefully

## GitHub Actions Workflows for Test Repo

### 1. always-pass.yml

```yaml
name: Always Pass
on:
  pull_request:
  push:
    branches-ignore:
      - 'test-*'

jobs:
  pass:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "✓ Check passed"
```

### 2. always-fail.yml

```yaml
name: Always Fail on Failing Branches
on:
  pull_request:
  push:

jobs:
  conditional-fail:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check branch name
        run: |
          BRANCH="${{ github.head_ref || github.ref_name }}"
          if [[ "$BRANCH" == *"-failing-"* ]]; then
            echo "✗ This branch is meant to fail"
            exit 1
          fi
          echo "✓ This branch is not a failing test"
```

### 3. slow-check.yml

```yaml
name: Slow Check
on:
  pull_request:
  push:

jobs:
  slow:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Simulate long-running check
        run: |
          echo "Starting slow check..."
          sleep 35
          echo "✓ Slow check completed"
```

## Test Scenarios

### Scenario 1: PR with Passing Checks

**Setup:**
```bash
BRANCH="${PREFIX}-passing"
git checkout -b "$BRANCH" main
echo "test" > test-data/sample.txt
git add test-data/sample.txt
git commit -m "Add test data"
git push -u origin "$BRANCH"

PR_URL=$(gh pr create --base main --head "$BRANCH" \
  --title "Test: All checks pass" \
  --body "This PR should have all passing checks")
```

**Expected State:**
- All workflows pass ✓

**Test:**
```python
def test_pr_status_all_passing(real_test_repo, unique_prefix, cleanup_branches):
    """Test PR with all checks passing - REAL GITHUB API"""
    branch = f"{unique_prefix}-passing"
    pr_url = create_test_pr(real_test_repo, branch, "main")

    # Wait for real checks to complete
    time.sleep(40)

    result = subprocess.run(
        ["qen", "status", "--pr", pr_url],
        capture_output=True, text=True
    )

    assert result.returncode == 0
    assert "✓ All checks passed" in result.stdout

    cleanup_branches.append(branch)
```

### Scenario 2: PR with Failing Checks

**Setup:**
```bash
# Branch name includes "-failing-" to trigger failure
BRANCH="${PREFIX}-failing-checks"
git checkout -b "$BRANCH" main
echo "fail" > test-data/sample.txt
git add test-data/sample.txt
git commit -m "Add failing test"
git push -u origin "$BRANCH"

PR_URL=$(gh pr create --base main --head "$BRANCH" \
  --title "Test: Failing checks" \
  --body "This PR should have failing checks")
```

**Expected State:**
- `always-fail.yml` → ✗ failure (contains "-failing-")

**Test:**
```python
def test_pr_status_with_failures(real_test_repo, unique_prefix, cleanup_branches):
    """Test PR with failing checks - REAL GITHUB API"""
    branch = f"{unique_prefix}-failing-checks"
    pr_url = create_test_pr(real_test_repo, branch, "main")

    time.sleep(40)

    result = subprocess.run(
        ["qen", "status", "--pr", pr_url],
        capture_output=True, text=True
    )

    assert result.returncode != 0
    assert "✗ Some checks failed" in result.stdout

    cleanup_branches.append(branch)
```

### Scenario 3: Stacked PRs (A→B→C)

**Setup:**
```bash
# Create stack: main → A → B → C
A="${PREFIX}-stack-a"
B="${PREFIX}-stack-b"
C="${PREFIX}-stack-c"

# Branch A
git checkout -b "$A" main
echo "A" > test-data/stack-a.txt
git add test-data/stack-a.txt
git commit -m "Stack A"
git push -u origin "$A"
gh pr create --base main --head "$A" --title "Stack: Base (A)"

# Branch B (based on A)
git checkout -b "$B" "$A"
echo "B" > test-data/stack-b.txt
git add test-data/stack-b.txt
git commit -m "Stack B"
git push -u origin "$B"
gh pr create --base "$A" --head "$B" --title "Stack: Middle (B)"

# Branch C (based on B)
git checkout -b "$C" "$B"
echo "C" > test-data/stack-c.txt
git add test-data/stack-c.txt
git commit -m "Stack C"
git push -u origin "$C"
gh pr create --base "$B" --head "$C" --title "Stack: Top (C)"
```

**Test:**
```python
def test_stacked_prs(real_test_repo, unique_prefix, cleanup_branches):
    """Test stacked PR detection - REAL GITHUB API"""
    stack_branches = create_pr_stack(real_test_repo, unique_prefix, 3)

    time.sleep(10)

    result = subprocess.run(
        ["qen", "status", "--stack"],
        capture_output=True, text=True,
        cwd=real_test_repo
    )

    assert result.returncode == 0
    assert "Stack detected" in result.stdout

    cleanup_branches.extend(stack_branches)
```

## Updated Test Infrastructure

### conftest.py - No Mocks

```python
"""Integration test fixtures - NO MOCKS"""
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Generator
import pytest


@pytest.fixture(scope="session")
def github_token() -> str:
    """Get GitHub token from environment"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set")
    return token


@pytest.fixture(scope="function")
def real_test_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Clone REAL test repository"""
    repo_url = "https://github.com/data-yaml/qen-test"
    repo_dir = tmp_path / "qen-test"

    subprocess.run(
        ["git", "clone", repo_url, str(repo_dir)],
        check=True,
        capture_output=True
    )

    subprocess.run(
        ["git", "config", "user.email", "test@qen.local"],
        cwd=repo_dir, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "QEN Integration Test"],
        cwd=repo_dir, check=True
    )

    yield repo_dir


@pytest.fixture(scope="function")
def unique_prefix() -> str:
    """Generate unique prefix for test branches"""
    import time
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    return f"test-{timestamp}-{unique_id}"


@pytest.fixture(scope="function")
def cleanup_branches(real_test_repo: Path) -> Generator[list[str], None, None]:
    """Track branches to cleanup after test"""
    branches_to_cleanup: list[str] = []

    yield branches_to_cleanup

    # Cleanup all test branches
    for branch in branches_to_cleanup:
        try:
            subprocess.run(
                ["gh", "pr", "close", branch, "--delete-branch"],
                cwd=real_test_repo,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            pass


def create_test_pr(
    repo_dir: Path,
    head_branch: str,
    base_branch: str,
    title: str = "Test PR",
    body: str = "Integration test PR"
) -> str:
    """Create a REAL PR using gh CLI and return URL"""

    subprocess.run(
        ["git", "checkout", base_branch],
        cwd=repo_dir, check=True, capture_output=True
    )

    subprocess.run(
        ["git", "checkout", "-b", head_branch],
        cwd=repo_dir, check=True, capture_output=True
    )

    test_file = repo_dir / "test-data" / "sample.txt"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text(f"Test data for {head_branch}")

    subprocess.run(
        ["git", "add", str(test_file)],
        cwd=repo_dir, check=True
    )

    subprocess.run(
        ["git", "commit", "-m", f"Test commit for {head_branch}"],
        cwd=repo_dir, check=True, capture_output=True
    )

    subprocess.run(
        ["git", "push", "-u", "origin", head_branch],
        cwd=repo_dir, check=True, capture_output=True
    )

    result = subprocess.run(
        ["gh", "pr", "create",
         "--base", base_branch,
         "--head", head_branch,
         "--title", title,
         "--body", body],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True
    )

    return result.stdout.strip()
```

## CI/CD Configuration

### .github/workflows/test.yml

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    name: Unit Tests (Fast, Mocked)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install uv
      - run: uv pip install -e ".[dev]" --system
      - run: ./poe test -m "not integration"
        timeout-minutes: 5

  integration-tests:
    name: Integration Tests (Real GitHub API)
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' || github.base_ref == 'main'

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install uv
      - run: uv pip install -e ".[dev]" --system
      - run: echo "${{ secrets.GITHUB_TOKEN }}" | gh auth login --with-token
      - run: ./poe test -m integration -v
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        timeout-minutes: 10
```

## Migration Plan

### Phase 1: Set Up Test Repository (Week 1)

```bash
# Repository already exists at https://github.com/data-yaml/qen-test

# Add workflows to test repo
cd /tmp
git clone https://github.com/data-yaml/qen-test
cd qen-test

# Create workflows directory
mkdir -p .github/workflows

# Add workflows (see YAML above)
# Commit and push
git add .github/workflows/
git commit -m "Add test workflows"
git push origin main
```

### Phase 2: Update Test Infrastructure (Week 2)

```bash
# Update conftest.py - remove ALL mocks
# Rewrite tests to use real GitHub API
# Test incrementally
pytest tests/integration/test_pr_status.py -v
```

### Phase 3: Delete Mock Infrastructure (Week 3)

```bash
# DELETE mock files
git rm scripts/setup_test_repo.py
git rm scripts/clean_test_repo.py
git rm -r .gh-mock/ 2>/dev/null || true

git commit -m "Delete mock infrastructure - integration tests now use real GitHub API"
git push origin main
```

### Phase 4: Update Documentation (Week 3)

Update `AGENTS.md` with testing policy (see Appendix below).

## Success Metrics

**Zero production bugs from mock mismatches:**
- Baseline: 3 bugs in past 6 months
- Target: 0 bugs in next 6 months

**Integration test reliability:**
- Target: >95% pass rate
- Measure: CI success rate over 30 days

**Test execution time:**
- Unit tests: <5 minutes
- Integration tests: <10 minutes

**Cleanup success rate:**
- Target: >99% of test branches cleaned up
- Alert: If >50 old test-* branches exist

## Appendix: AGENTS.md Testing Policy

Add this section to `AGENTS.md`:

```markdown
## Testing Philosophy

### Unit Tests - Fast and Mocked

**Purpose:** Test individual functions and modules in isolation

- Use mocks liberally for speed
- No network calls
- Run before every commit (pre-commit hook)

### Integration Tests - Real and Unmocked

**Purpose:** Validate our contract with GitHub's API

**HARD REQUIREMENTS:**
- ✅ **MUST use real GitHub API**
- ✅ **MUST use actual `gh` CLI commands**
- ✅ **MUST test against https://github.com/data-yaml/qen-test**
- ❌ **NO MOCKS ALLOWED**
- ❌ **NO MOCK DATA FILES**
- ❌ **NO MOCK `gh` COMMANDS**

### Why This Matters

Past production bugs caused by mocks:
1. Mock data had wrong field names
2. Mock data omitted fields
3. GitHub API changes not caught

**Integration tests validate our contract with GitHub. Never mock them.**

### Running Tests

```bash
# Unit tests only (fast)
./poe test-unit

# Integration tests only (real GitHub API)
./poe test-integration

# All tests
./poe test
```
```

## Conclusion

Integration tests MUST use the real GitHub API. No exceptions.

This spec defines our mock-free strategy using https://github.com/data-yaml/qen-test.

**Next Steps:**
1. Add GitHub Actions workflows to test repo
2. Update `conftest.py` to remove mocks
3. Rewrite integration tests
4. DELETE mock infrastructure
5. Update `AGENTS.md` with policy
