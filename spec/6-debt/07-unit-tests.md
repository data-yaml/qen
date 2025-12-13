# Tech Debt: Unit Tests

> **PRIORITY: MEDIUM** - Tests work but have significant duplication, inconsistent patterns, and maintenance burden

## Executive Summary

The unit test suite (35 files, ~14,000 lines) is functional and provides good coverage, but suffers from:
- **Heavy duplication** in mock setup patterns across test files
- **Inconsistent fixture usage** - some tests use pytest fixtures, others use unittest.mock directly
- **Mixed testing patterns** - combines pure unit tests with pseudo-integration tests
- **Verbose test setup** - repetitive configuration code in many tests
- **Lack of shared test utilities** - helper functions duplicated across files
- **Inconsistent naming conventions** - mix of test class names and organizational patterns

The tests work and catch bugs effectively, but the codebase would benefit from systematic refactoring to reduce duplication, improve maintainability, and establish consistent patterns.

## Problem Statement

### Current Issues

#### 1. Mock Setup Duplication

**Location**: Throughout `tests/unit/qen/commands/` and `tests/unit/qen/`

**Problem**: Nearly identical mock setup code is repeated across multiple test files.

**Example** from `test_status.py`, `test_pr.py`, `test_add.py`:

```python
# This pattern appears in ~15 different test files
mock_config = Mock()
mock_config.read_main_config.return_value = {
    "meta_path": "/tmp/meta",
    "current_project": "test-project",
}
mock_config.read_project_config.return_value = {
    "folder": "proj/test",
    "repo": "/tmp/meta",
}
mock_ensure.return_value = mock_config
```

**Impact**: Changes to config structure require updates in dozens of places.

#### 2. Inconsistent Mock Libraries

**Location**: All test files

**Problem**: Tests mix `unittest.mock` and `pytest-mock` (mocker fixture) inconsistently.

**Examples**:

```python
# test_git_utils.py - uses unittest.mock directly
with unittest.mock.patch("subprocess.run") as mock_run:
    mock_run.return_value = unittest.mock.Mock(stdout="", returncode=0)

# test_add.py - uses pytest-mock mocker fixture
def test_something(mocker):
    mocker.patch("qen.git_utils.get_current_branch", return_value="main")
```

**Impact**: Different testing patterns make code harder to understand and maintain.

#### 3. Verbose Git Mock Patterns

**Location**: `test_add.py`, `test_init.py`, integration test setup

**Problem**: Every test that needs a git repo has 20-30 lines of subprocess.run mocking.

**Example** (repeated ~20 times):

```python
subprocess.run(
    ["git", "config", "user.name", "Test User"],
    cwd=child_repo,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "config", "user.email", "test@example.com"],
    cwd=child_repo,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "add", "README.md"],
    cwd=child_repo,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "commit", "-m", "Initial commit"],
    cwd=child_repo,
    check=True,
    capture_output=True,
)
```

**Impact**: Each test requiring git operations is 3x longer than necessary.

#### 4. Duplicate Test Helpers

**Location**: Multiple files in `tests/unit/helpers/`

**Problem**: Test helper functionality is fragmented across multiple files with unclear organization:
- `tests/unit/helpers/test_mock.py` - Basic config mocks (22 lines)
- `tests/unit/helpers/github_mock.py` - GitHub API mocks (87 lines)
- `tests/unit/fixtures/github_fixtures.py` - GitHub fixtures (69 lines)
- `tests/unit/schemas/github_pr.py` - GitHub schemas (63 lines)

**Impact**: Hard to find the right helper function; encourages duplication.

#### 5. Parametrize Opportunities Missed

**Location**: `test_project.py`, `test_config.py`, `test_git_status.py`

**Problem**: Many tests repeat similar logic with different inputs instead of using `@pytest.mark.parametrize`.

**Example** from `test_project.py`:

```python
def test_parse_https_url(self) -> None:
    """Test parsing full HTTPS URL."""
    result = parse_repo_url("https://github.com/myorg/myrepo")
    assert result["org"] == "myorg"

def test_parse_https_url_with_git_extension(self) -> None:
    """Test parsing HTTPS URL with .git extension."""
    result = parse_repo_url("https://github.com/myorg/myrepo.git")
    assert result["org"] == "myorg"

def test_parse_ssh_url(self) -> None:
    """Test parsing SSH URL."""
    result = parse_repo_url("git@github.com:myorg/myrepo.git")
    assert result["org"] == "myorg"
```

**Better approach** (single parametrized test):

```python
@pytest.mark.parametrize("url,expected_org,expected_repo", [
    ("https://github.com/myorg/myrepo", "myorg", "myrepo"),
    ("https://github.com/myorg/myrepo.git", "myorg", "myrepo"),
    ("git@github.com:myorg/myrepo.git", "myorg", "myrepo"),
])
def test_parse_repo_url(url, expected_org, expected_repo):
    result = parse_repo_url(url)
    assert result["org"] == expected_org
    assert result["repo"] == expected_repo
```

**Impact**:
- 3-5x more test code than necessary
- Changes to test logic require updates to multiple functions
- Test output is harder to read (many similar test names)

#### 6. Inconsistent Test Class Organization

**Location**: All test files

**Problem**: Mix of organizational patterns without clear rationale:
- Some files use test classes (`TestConfigInitialization`, `TestMainConfig`)
- Some files use module-level functions
- Some classes group by feature, others by function
- No consistent naming pattern

**Examples**:

```python
# test_config.py - deeply nested classes
class TestConfigInitialization:
    class TestConfigPaths:
        def test_get_config_dir(self): ...
        def test_get_main_config_path(self): ...

# test_git_utils.py - flat functions
def test_has_uncommitted_changes_clean(tmp_path): ...
def test_checkout_branch_success(tmp_path): ...

# test_status.py - mixed approach
class TestSyncStatus:
    def test_sync_status_up_to_date(self): ...

def test_format_status_output(): ...  # Module-level function
```

**Impact**: Harder to navigate tests and understand organization.

#### 7. Type Hints Inconsistently Used

**Location**: All test files

**Problem**: Some tests have full type hints, others have none.

**Examples**:

```python
# test_config.py - full type hints
def test_read_main_config_success(self, test_storage: QenvyTest) -> None:
    """Test reading main config successfully."""

# test_git_utils.py - no type hints on some tests
def test_has_uncommitted_changes_clean(tmp_path):
    """Test has_uncommitted_changes with clean repo."""
```

**Impact**: Inconsistent code quality; harder to catch type errors in tests.

#### 8. Large Fixture in conftest.py

**Location**: `tests/conftest.py`

**Problem**: Single 886-line conftest.py file mixes:
- Unit test fixtures (simple)
- Integration test fixtures (complex)
- Helper functions (should be separate module)
- Documentation comments (good but verbose)

**Impact**:
- Hard to find specific fixture
- Mixing concerns (unit vs integration)
- Long file is harder to maintain

#### 9. Mock Data Schema Validation

**Location**: `tests/unit/helpers/github_mock.py`, `tests/unit/schemas/github_pr.py`

**Problem**: Good TypedDict schemas exist for GitHub API data, but not enforced in all tests.

**Example** - Schema exists:

```python
# tests/unit/schemas/github_pr.py
class PrData(TypedDict):
    """GitHub PR schema from gh pr view --json."""
    number: int
    title: str
    state: Literal["OPEN", "CLOSED", "MERGED"]
    # ... more fields
```

But many tests create mock data without validation:

```python
# test_pr.py - manually creates dict without schema validation
pr_data = {
    "number": 123,
    "title": "Test PR",
    "state": "OPEN",  # Could be "open" and test would pass!
    # Missing required fields like 'mergeable'
}
```

**Impact**: Tests can pass with invalid mock data that doesn't match real GitHub API.

#### 10. Pseudo-Integration Tests in Unit Suite

**Location**: `test_add.py`, `test_init.py`

**Problem**: Some "unit" tests do real git operations instead of mocking:

```python
# test_add.py - creates real git repos
def test_add_repository_full_workflow(
    tmp_path: Path,
    test_storage: QenvyTest,
    temp_git_repo: Path,
    child_repo: Path,
    mocker,
):
    # Real git operations mixed with mocks
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
```

**Impact**:
- Unit tests slower than necessary
- Tests fragile (depend on git binary, filesystem)
- Blurs line between unit and integration tests

### Root Cause

These issues stem from:

1. **Organic growth** - Tests added incrementally without refactoring
2. **No test utilities module** - No shared place for common test helpers
3. **Insufficient upfront design** - Test patterns not established early
4. **Copy-paste development** - New tests copied from existing tests
5. **Time pressure** - Focus on functionality over test maintainability

## Refactoring Strategy

### Phase 1: Extract Common Test Utilities (2-3 days)

**Goal**: Create shared test helper modules to eliminate duplication

**Actions**:
1. Create `tests/unit/helpers/mock_factory.py`:
   - `create_mock_config(meta_path, project, **overrides)` - Standard config mock
   - `create_mock_ensure_initialized(**overrides)` - Standard ensure_initialized mock
   - `create_mock_project_setup(**overrides)` - Complete project setup mock

2. Create `tests/unit/helpers/git_helpers.py`:
   - `setup_git_repo(path)` - Configure git user/email
   - `create_git_commit(repo, file, message)` - Make a commit
   - `create_git_branch(repo, branch)` - Create and checkout branch

3. Consolidate GitHub mocks:
   - Merge `github_mock.py` and `github_fixtures.py` into single module
   - Enforce TypedDict schemas for all mock data
   - Add validation functions

**Success Criteria**:
- All test files import from new helpers
- Mock setup code reduced by ~50%
- No copy-pasted mock setup patterns

### Phase 2: Standardize Mock Usage (1-2 days)

**Goal**: Use pytest-mock consistently throughout

**Actions**:
1. Convert all `unittest.mock` usage to `pytest-mock` (mocker fixture)
2. Update all tests to use `mocker.patch()` instead of `with patch()`
3. Remove all `import unittest.mock` statements

**Example conversion**:

```python
# Before
from unittest.mock import Mock, patch

def test_something():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0)

# After
def test_something(mocker):
    mock_run = mocker.patch("subprocess.run", return_value=Mock(returncode=0))
```

**Success Criteria**:
- Zero `unittest.mock` imports in test files
- All tests use mocker fixture for patching
- Consistent mock patterns across all tests

### Phase 3: Add Parametrized Tests (2-3 days)

**Goal**: Reduce test duplication using `@pytest.mark.parametrize`

**Actions**:
1. Identify test groups with similar patterns:
   - URL parsing tests (8 tests → 1 parametrized test)
   - Config validation tests (12 tests → 2 parametrized tests)
   - Status format tests (15 tests → 3 parametrized tests)

2. Convert to parametrized tests:
   - Keep one test function with parameters
   - Add descriptive test IDs for each parameter set
   - Remove duplicate test functions

**Success Criteria**:
- ~30-40 test functions converted to parametrized tests
- Test code reduced by ~500-800 lines
- Test names more descriptive with parameter values

### Phase 4: Reorganize Test Classes (1 day)

**Goal**: Consistent test organization and naming

**Actions**:
1. Establish standard pattern:
   - Use classes for grouping related tests only
   - Class name: `Test{Feature}` (e.g., `TestConfigReading`, `TestPrStatus`)
   - Module-level functions for simple tests
   - Max 2 levels of nesting

2. Convert existing tests to standard pattern

**Success Criteria**:
- All test files follow same organizational pattern
- Class names are consistent and descriptive
- Easy to find tests by feature

### Phase 5: Add Type Hints (1-2 days)

**Goal**: Full type coverage in test files

**Actions**:
1. Add type hints to all test functions:
   - Parameter types (including fixtures)
   - Return type `-> None` for test functions

2. Update mypy configuration to check test files

**Success Criteria**:
- All test functions have complete type hints
- mypy passes on tests/ directory
- Type errors caught in CI

### Phase 6: Split conftest.py (1 day)

**Goal**: Separate unit and integration fixtures

**Actions**:
1. Create `tests/unit/conftest.py` - unit test fixtures only
2. Create `tests/integration/conftest.py` - integration test fixtures only
3. Keep shared fixtures in `tests/conftest.py`
4. Move helper functions to separate modules

**Success Criteria**:
- Each conftest.py < 200 lines
- Clear separation of concerns
- Fixtures easy to find

## Implementation Plan

### Step 1: Create Test Utilities (Week 1)
- [ ] Create `tests/unit/helpers/mock_factory.py`
- [ ] Create `tests/unit/helpers/git_helpers.py`
- [ ] Consolidate GitHub mocks
- [ ] Add validation for mock data schemas

### Step 2: Refactor High-Impact Tests (Week 1-2)
- [ ] Convert `test_pr.py` to use new helpers
- [ ] Convert `test_status.py` to use new helpers
- [ ] Convert `test_add.py` to use new helpers
- [ ] Verify all tests still pass

### Step 3: Standardize Mock Usage (Week 2)
- [ ] Convert all `unittest.mock` to `pytest-mock`
- [ ] Update test patterns guide in AGENTS.md
- [ ] Run full test suite

### Step 4: Add Parametrized Tests (Week 3)
- [ ] Convert URL parsing tests
- [ ] Convert config tests
- [ ] Convert status formatting tests
- [ ] Verify coverage unchanged

### Step 5: Polish and Document (Week 3-4)
- [ ] Reorganize test classes
- [ ] Add complete type hints
- [ ] Split conftest.py
- [ ] Update testing documentation
- [ ] Run final validation

**Total Estimated Time**: 3-4 weeks (part-time effort)

## Success Criteria

### Quantitative Metrics
- [ ] Test code reduced by 20-30% (from ~14,000 to ~10,000 lines)
- [ ] Mock setup duplication eliminated (0 copy-pasted mock patterns)
- [ ] 100% type hint coverage in test files
- [ ] Test execution time reduced by 10-15% (from removing pseudo-integration tests)
- [ ] All 35 test files follow consistent patterns

### Qualitative Improvements
- [ ] New tests can be written faster using shared utilities
- [ ] Test failures easier to debug with better organization
- [ ] Mock patterns consistent across all tests
- [ ] Clear separation between unit and integration tests
- [ ] Test code easier to understand and maintain

### Validation Tests
- [ ] Run `./poe test` - all tests pass
- [ ] Run `./poe test-cov` - coverage unchanged or improved
- [ ] Run `./poe typecheck` on tests/ - no errors
- [ ] Verify pre-commit hooks still pass
- [ ] Manual review of 5 refactored test files for quality

## Testing Strategy

### During Refactoring
1. **Run tests after each change**:
   ```bash
   # After each utility function creation
   ./poe test-unit

   # After each test file refactoring
   ./poe test tests/unit/qen/test_specific.py -v
   ```

2. **Verify coverage maintained**:
   ```bash
   ./poe test-cov
   # Ensure coverage % stays same or increases
   ```

3. **Check for test duplication**:
   ```bash
   # Should show no duplicate test names
   pytest --collect-only | grep "test_" | sort | uniq -d
   ```

### Validation After Completion
1. **Full test suite**:
   ```bash
   ./poe test-all  # Unit + integration
   ```

2. **Type checking**:
   ```bash
   mypy tests/ --strict
   ```

3. **Pre-commit validation**:
   ```bash
   pre-commit run --all-files
   ```

4. **Manual code review**:
   - Review 5 randomly selected refactored test files
   - Check for consistent patterns
   - Verify readability improved

## Dependencies and Blockers

### Dependencies
- **None** - This refactoring is self-contained within tests/

### Potential Blockers
1. **Test breakage during refactoring**
   - Mitigation: Refactor incrementally, run tests after each change
   - Mitigation: Keep old and new patterns side-by-side temporarily

2. **Time/effort underestimation**
   - Mitigation: Break work into small PRs (1-2 files at a time)
   - Mitigation: Phase 1 delivers immediate value, rest is optional

3. **Merge conflicts if done in parallel with feature work**
   - Mitigation: Coordinate with team on timing
   - Mitigation: Do Phase 1 first (most value, least conflict)

## Related Tech Debt

### Related Documents
- `05-tests.md` - Overall test infrastructure tech debt
- `03-qen-lib.md` - Source code organization affects test patterns
- `02-qen-commands.md` - Command structure affects command tests

### Related Issues
- Integration tests use real GitHub API (see `05-tests.md`)
- No CI/CD pipeline yet for automated test runs
- Coverage gaps in some modules (see `05-tests.md`)

## Metadata

**Document Created**: 2025-12-11
**Analyzed Files**: 35 unit test files (~14,000 lines)
**Priority**: Medium
**Estimated Effort**: 3-4 weeks
**Impact**: High (maintainability) / Low (functionality)

---

*Generated with Claude Code*
