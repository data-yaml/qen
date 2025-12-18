# Integration Testing with Real GitHub API

## Overview

QEN uses a **NO MOCKS** policy for integration tests. All integration tests use the real GitHub API against the dedicated test repository at <https://github.com/data-yaml/qen-test>.

## Why No Mocks?

**Past production bugs caused by mocks:**

1. Mock data had wrong field names (`state` vs `status`)
2. Mock data omitted required fields (`mergeable`)
3. GitHub API changes not caught by mocks

**Integration tests validate our contract with GitHub. Never mock them.**

## Test Repository Setup

### GitHub Actions Workflows

The `data-yaml/qen-test` repository needs three GitHub Actions workflows:

**Location:** `.github/workflows/` in the qen-test repository

**Workflows:**

1. **always-pass.yml** - Always passes for all branches
2. **always-fail.yml** - Fails for branches containing "-failing-" in the name
3. **slow-check.yml** - Takes 35 seconds to simulate slow checks

These workflow files are provided in `/Users/ernest/GitHub/qen/docs/qen-test-workflows/`.

### Setup Instructions

```bash
# Clone the test repo
git clone https://github.com/data-yaml/qen-test
cd qen-test

# Copy workflows from qen repo
cp /path/to/qen/docs/qen-test-workflows/*.yml .github/workflows/

# Commit and push
git add .github/workflows/
git commit -m "Add GitHub Actions workflows for integration testing"
git push origin main
```

## Running Integration Tests

### Prerequisites

- GitHub Personal Access Token with repo permissions
- `gh` CLI tool installed and authenticated

### Environment Setup

```bash
# Set GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# Or authenticate gh CLI
echo "$GITHUB_TOKEN" | gh auth login --with-token
```

### Run Tests

```bash
# Run only integration tests
./poe test-integration

# Run all tests (unit + integration)
./poe test-all

# Run specific integration test
pytest tests/integration/test_pr_status.py::test_pr_with_passing_checks_standard -v
```

## Test Fixtures

### Real GitHub Fixtures (NO MOCKS)

All fixtures in `tests/conftest.py`:

- **`github_token()`** - Get token from environment, skip if not set
- **`real_test_repo()`** - Clone actual qen-test repo to tmp directory
- **`unique_prefix()`** - Generate unique branch prefix (`test-{timestamp}-{uuid}`)
- **`cleanup_branches()`** - Track and cleanup test branches after test

### Helper Functions

- **`create_test_pr()`** - Create real PR using gh CLI
- **`create_pr_stack()`** - Create stack of PRs (A→B→C) for testing

## Test Scenarios

### Core Functionality Tests (REQUIRED)

**These tests MUST exist for core commands that manipulate project state:**

#### 1. Status Command

Tests that `qen status` correctly displays project state.

**Test:** `tests/integration/test_status.py`

```python
@pytest.mark.integration
def test_status_command(temp_config_dir, real_test_repo):
    """Verify status command displays correct project state."""
    # Create project
    subprocess.run(["./qen", "--config-dir", temp_config_dir, "init", "test-proj"], check=True)

    # Add repo
    subprocess.run(["./qen", "--config-dir", temp_config_dir, "add", real_test_repo], check=True)

    # Run status
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "status"],
        capture_output=True, text=True, check=True
    )

    assert "test-proj" in result.stdout
    assert real_test_repo in result.stdout
```

#### 2. Commit Command

Tests that `qen commit` correctly commits changes across repositories.

**Test:** `tests/integration/test_commit.py`

```python
@pytest.mark.integration
def test_commit_command(temp_config_dir, real_test_repo):
    """Verify commit command commits changes across repos."""
    # Setup project
    subprocess.run(["./qen", "--config-dir", temp_config_dir, "init", "test-proj"], check=True)

    # Get project paths
    project_config = load_project_config(temp_config_dir, "test-proj")
    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    # Create test file
    test_file = project_dir / "test.txt"
    test_file.write_text("test content")

    # Commit should work
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "commit", "-m", "test commit"],
        capture_output=True, text=True, check=True
    )

    assert "committed" in result.stdout.lower() or "clean" in result.stdout.lower()
```

#### 3. Add Command

Tests that `qen add` correctly clones and registers repositories.

**Test:** `tests/integration/test_add.py`

```python
@pytest.mark.integration
def test_add_command(temp_config_dir, real_test_repo):
    """Verify add command clones and registers repos."""
    # Setup project
    subprocess.run(["./qen", "--config-dir", temp_config_dir, "init", "test-proj"], check=True)

    # Add repo
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "add", real_test_repo],
        capture_output=True, text=True, check=True
    )

    # Verify repo was added
    project_config = load_project_config(temp_config_dir, "test-proj")
    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    # Check pyproject.toml
    pyproject_path = project_dir / "pyproject.toml"
    assert pyproject_path.exists()

    pyproject = tomli.loads(pyproject_path.read_text())
    assert "tool" in pyproject
    assert "qen" in pyproject["tool"]
    assert "repos" in pyproject["tool"]["qen"]
    assert len(pyproject["tool"]["qen"]["repos"]) == 1
```

#### 4. Status-Commit Consistency

Tests that status and commit see the same project directory.

**Test:** `tests/integration/test_consistency.py`

```python
@pytest.mark.integration
def test_status_commit_consistency(temp_config_dir, real_test_repo):
    """Verify status and commit use same project paths."""
    # Setup
    subprocess.run(["./qen", "--config-dir", temp_config_dir, "init", "test-proj"], check=True)

    # Status should work
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "status"],
        capture_output=True, text=True, check=True
    )
    status_output = result.stdout

    # Get project dir from config
    project_config = load_project_config(temp_config_dir, "test-proj")
    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    # Create test file
    (project_dir / "test.txt").write_text("test")

    # Commit should see same directory
    result = subprocess.run(
        ["./qen", "--config-dir", temp_config_dir, "commit", "-m", "test"],
        capture_output=True, text=True, check=True
    )

    # Both should reference same project
    assert "test-proj" in status_output
    assert "test-proj" in result.stdout or "Meta Repository" in result.stdout
```

### GitHub API Integration Tests

#### 5. PR with Passing Checks

```python
@pytest.mark.integration
def test_pr_with_passing_checks(real_test_repo, unique_prefix, cleanup_branches):
    branch = f"{unique_prefix}-passing"
    pr_url = create_test_pr(real_test_repo, branch, "main")
    cleanup_branches.append(branch)

    time.sleep(40)  # Wait for GitHub Actions

    # Test against REAL GitHub API
    result = subprocess.run(["gh", "pr", "view", pr_url, "--json", "statusCheckRollup"], ...)
    assert checks passed
```

#### 6. PR with Failing Checks

Branch name contains "-failing-" to trigger `always-fail.yml` workflow.

#### 7. Stacked PRs

Creates real PR stack: main → A → B → C

#### 8. Slow Check Progress

Tests handling of in-progress checks during `slow-check.yml` execution.

## CI/CD Configuration

### GitHub Actions Workflow

**`.github/workflows/test.yml`** has two separate jobs:

**1. unit-tests** - Fast, runs on all PRs

- Runs in < 10 minutes
- Uses mocks
- Matrix: Python 3.12, 3.13 on Ubuntu, macOS

**2. integration-tests** - Fast, can run regularly

- Runs in ~10-15 seconds using standard PRs
- Uses real GitHub API
- Requires `GITHUB_TOKEN`
- Can run on `main` branch or PRs to `main`

## Test Cleanup

Integration tests automatically cleanup after execution:

1. PRs are closed using `gh pr close`
2. Branches are deleted using `--delete-branch`
3. Cleanup happens in fixture teardown (best effort)

## Troubleshooting

### Tests Skipped

**Error:** `GITHUB_TOKEN not set - skipping integration test`

**Fix:**

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

### gh CLI Not Authenticated

**Error:** `gh: To get started with GitHub CLI, please run: gh auth login`

**Fix:**

```bash
echo "$GITHUB_TOKEN" | gh auth login --with-token
```

### Rate Limiting

GitHub API rate limits:

- Authenticated: 5,000 requests/hour
- Unauthenticated: 60 requests/hour

Always use `GITHUB_TOKEN` for integration tests.

### Timeout Issues

If tests timeout waiting for GitHub Actions:

- Check workflows are enabled in qen-test repository
- Verify branch naming triggers correct workflow
- Increase sleep time if checks take longer than expected

## Mock Infrastructure Removed

The following mock infrastructure has been **DELETED**:

- ✅ `scripts/setup_test_repo.py` - Removed
- ✅ `scripts/clean_test_repo.py` - Removed
- ✅ `.gh-mock/` directories - Removed
- ✅ Mock data files - Removed
- ✅ Mock fixtures for integration tests - Removed

**Unit tests can still use mocks** - this policy applies only to integration tests.

## Success Metrics

**Target Metrics:**

- Zero production bugs from mock mismatches
- Integration test reliability > 95%
- Unit tests < 10 minutes
- Integration tests ~10-15 seconds (using standard PRs)
- Standard PR availability > 99%

**Required Test Coverage:**

Core functionality tests MUST exist for:

- ✅ `status` - Project state display
- ✅ `commit` - Change committing
- ✅ `add` - Repository registration
- ✅ Cross-command consistency (status/commit use same paths)

GitHub API integration tests:

- ✅ PR status checks (passing/failing)
- ✅ Stacked PRs
- ✅ Slow check progress

## Related Documentation

- **Specification:** `spec/2-status/07-repo-qen-test.md`
- **Agent Guide:** `AGENTS.md` - Testing Philosophy section
- **Fixtures:** `tests/conftest.py` - Integration test fixtures
- **Tests:** `tests/integration/test_pr_status.py` and `tests/integration/test_pull.py`
- **Standard PR Setup:** `STANDARD_PRS_SETUP.md`
