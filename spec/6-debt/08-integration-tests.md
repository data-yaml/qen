# Tech Debt: Integration Tests

> **PRIORITY: MEDIUM-HIGH** - Tests are good but have significant duplication, inconsistent patterns, and maintenance burden. Some patterns are better than unit tests, but gaps remain.

## Executive Summary

The integration test suite (10 test files, ~2,000 lines) successfully validates real GitHub API integration with NO MOCKS, but suffers from:

- **Heavy duplication** in test setup patterns (creating meta repos, projects, config)
- **Inconsistent fixture usage** - some tests use shared fixtures, others duplicate setup
- **Missing type hints** on most test functions and fixtures
- **Git setup code duplicated** across 4 test files (~150 lines total)
- **Project creation helpers scattered** - inline in test files rather than shared utilities
- **Test organization inconsistencies** - mix of function-level and module-level setup
- **Excellent standard PR optimization** that could be used more widely
- **Good separation** from unit tests (true NO MOCKS enforcement)

**Strengths vs Unit Tests:**
- ✅ Better: Absolutely NO MOCKS (hard requirement enforced)
- ✅ Better: Standard reference PRs pattern is excellent optimization
- ✅ Better: Helper functions in conftest.py are well-documented
- ✅ Better: Clear docstrings explaining REAL operations
- ❌ Worse: More duplication of git setup code
- ❌ Worse: Less parametrization (many similar tests could be combined)
- ❌ Worse: Worse type hint coverage

## Problem Areas

### 1. Git Repository Setup Duplication

**Location**: `test_init.py`, `test_pull.py`, `conftest.py`

**Problem**: Near-identical git repository initialization code repeated across multiple locations.

**Examples**:

`test_init.py` lines 54-108 (tmp_meta_repo fixture):
```python
subprocess.run(
    ["git", "init", "-b", "main"],
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "config", "user.name", "QEN Integration Test"],
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "config", "user.email", "test@qen.local"],
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
# ... remote setup, initial commit
```

`test_pull.py` lines 39-71 (setup_test_project_optimized):
```python
subprocess.run(["git", "init", "-b", "main"], cwd=meta_repo, check=True, capture_output=True)
subprocess.run(
    ["git", "config", "user.name", "QEN Integration Test"],
    cwd=meta_repo,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "config", "user.email", "test@qen.local"],
    cwd=meta_repo,
    check=True,
    capture_output=True,
)
# ... same pattern
```

`conftest.py` lines 194-270 (meta_prime_repo fixture):
```python
subprocess.run(
    ["git", "init", "-b", "main"],
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
subprocess.run(
    ["git", "config", "user.name", "Test User"],  # Note: Different user!
    cwd=meta_dir,
    check=True,
    capture_output=True,
)
# ... same pattern again
```

**Impact**:
- ~150 lines of duplicated git setup code
- Inconsistent test user names ("Test User" vs "QEN Integration Test")
- Changes to git setup require updates in 4+ places
- More opportunities for divergence and bugs

### 2. Project Creation Setup Duplication

**Location**: `test_pull.py`, `test_init.py`, `conftest.py`

**Problem**: Project creation and initialization duplicated with slight variations.

**Examples**:

`test_pull.py` lines 20-88 (setup_test_project_optimized):
```python
def setup_test_project_optimized(
    tmp_path: Path, temp_config_dir: Path, project_suffix: str
) -> tuple[Path, Path]:
    """Create a test meta repo and project for integration testing."""
    # Create meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize git repo (20 lines of subprocess calls)
    # Initialize qen (subprocess call)
    # Create project (subprocess call)
    # Find project directory (glob matching)

    return meta_repo, project_dir
```

`conftest.py` lines 273-345 (qen_project fixture):
```python
def qen_project(
    meta_prime_repo: Path,
    temp_config_dir: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path]:
    """Create a QEN project with per-project meta clone."""
    # Initialize qen global config (subprocess)
    # Create project (subprocess)
    # Calculate paths (datetime logic)
    # Verify paths exist (assertions)
    # Verify correct branch (subprocess)

    return meta_prime_repo, per_project_meta, project_dir
```

**Differences**:
- `setup_test_project_optimized` creates meta repo from scratch
- `qen_project` uses existing meta_prime_repo fixture
- Different return tuple sizes (2 vs 3 items)
- Different path calculation logic
- Both duplicate project directory discovery logic

**Impact**:
- ~100 lines of duplicated project creation logic
- Hard to maintain consistency between approaches
- Tests using different patterns behave differently
- Unclear which pattern to use for new tests

### 3. Missing Type Hints

**Location**: All integration test files

**Problem**: Most test functions and many fixtures lack type hints.

**Statistics**:
- Total test functions: ~35
- Functions with type hints: ~12 (34%)
- Total fixtures: ~15
- Fixtures with type hints: ~8 (53%)

**Examples**:

`test_pr_status.py` line 19:
```python
def test_stacked_prs_standard() -> None:  # ✅ HAS type hint
```

`test_qen_wrapper.py` line 26:
```python
def test_qen_wrapper_generation(  # ❌ NO return type
    real_test_repo: Path,  # ✅ Parameter types
    unique_prefix: str,
    cleanup_branches: list[str],
    temp_config_dir: Path,
):
```

`test_branch_checking.py` line 17:
```python
def test_qen_config_switches_branch(  # ❌ NO return type
    tmp_meta_repo: Path,
    unique_project_name: str,
    temp_config_dir: Path,
):
```

`conftest.py` line 460:
```python
def unique_prefix() -> str:  # ✅ HAS type hint
```

**Impact**:
- Harder to catch type errors in tests
- Less readable code (unclear what fixtures return)
- Inconsistent with project's strict mypy policy
- Hurts maintainability

### 4. TOML Manipulation Duplication

**Location**: `test_pull.py`, `test_add.py`, `test_rm_real.py`

**Problem**: Manual TOML reading/writing duplicated across test files.

**Examples**:

`test_pull.py` lines 91-127 (add_repo_entry_to_pyproject):
```python
def add_repo_entry_to_pyproject(
    project_dir: Path,
    url: str,
    branch: str,
    path: str,
) -> None:
    """Add a repo entry to project's pyproject.toml without cloning."""
    pyproject_path = project_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    if "tool" not in pyproject:
        pyproject["tool"] = {}
    if "qen" not in pyproject["tool"]:
        pyproject["tool"]["qen"] = {}
    if "repos" not in pyproject["tool"]["qen"]:
        pyproject["tool"]["qen"]["repos"] = []

    pyproject["tool"]["qen"]["repos"].append({
        "url": url,
        "branch": branch,
        "path": path,
    })

    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)
```

Similar pattern in `test_add.py` lines 69-77 (reading pyproject):
```python
pyproject_path = proj_dir / "pyproject.toml"
assert pyproject_path.exists(), "pyproject.toml not found"

with open(pyproject_path, "rb") as f:
    pyproject = tomllib.load(f)

assert "tool" in pyproject
assert "qen" in pyproject["tool"]
assert "repos" in pyproject["tool"]["qen"]
repos = pyproject["tool"]["qen"]["repos"]
```

`test_rm_real.py` lines 28-34 (same pattern):
```python
pyproject_path = project_dir / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject = tomllib.load(f)
repos = pyproject["tool"]["qen"]["repos"]
```

**Impact**:
- ~50 lines of duplicated TOML manipulation
- Error-prone (easy to forget error handling)
- Hard to add validation or schema checking
- Should use existing `pyproject_utils` module

### 5. Test Fixture Organization Issues

**Location**: `test_init.py`, `conftest.py`

**Problem**: Some fixtures are test-specific but live in test files, others are in conftest but not widely used.

**Examples**:

`test_init.py` lines 29-110 (tmp_meta_repo fixture):
```python
@pytest.fixture(scope="function")
def tmp_meta_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for use as a meta repo."""
    # 80 lines of setup code
    return meta_dir
```

This fixture:
- Only used in test_init.py (5 tests)
- Duplicates meta_prime_repo fixture in conftest.py
- Could be merged or made more general

`test_init.py` lines 113-129 (unique_project_name fixture):
```python
@pytest.fixture(scope="function")
def unique_project_name(unique_prefix: str) -> str:
    """Generate unique project name for integration tests."""
    return unique_prefix
```

This fixture:
- Just returns another fixture unchanged
- Could be eliminated (use unique_prefix directly)
- Adds confusion without value

**Impact**:
- Hard to find the right fixture to use
- Duplication between conftest and test files
- Fixtures with narrow scope living in broad locations
- Confusing for new test writers

### 6. Assertion Message Inconsistency

**Location**: All test files

**Problem**: Assertion messages vary widely in detail and format.

**Examples**:

Good (detailed):
```python
# test_init.py line 218
assert per_project_meta.exists(), f"Per-project meta not created: {per_project_meta}"
assert (per_project_meta / ".git").exists(), "Per-project meta is not a git repo"
```

Bad (minimal):
```python
# test_add.py line 77
assert isinstance(repos, list)
assert len(repos) == 1
```

Bad (inconsistent format):
```python
# test_status.py line 61
assert "clean" in output.lower() or "nothing to commit" in output.lower()
```

Better alternative:
```python
assert "clean" in output.lower() or "nothing to commit" in output.lower(), (
    f"Expected clean status, got: {output}"
)
```

**Impact**:
- Test failures harder to debug
- Inconsistent developer experience
- Wasted time investigating failures

### 7. Test Organization Patterns

**Location**: All test files

**Problem**: No consistent pattern for related test groups.

**Comparison**:

`test_pr_status.py`:
- All module-level functions
- No test classes
- 4 tests, well organized
- ✅ Clean and simple

`test_add.py`:
- All module-level functions
- No test classes
- 11 tests in same file
- ❌ Could benefit from grouping

`test_qen_wrapper.py`:
- All module-level functions
- 5 related tests about wrapper behavior
- ❌ Could be grouped in test class

**Better approach** (from unit tests):
```python
class TestWrapperGeneration:
    """Tests for wrapper script generation."""

    def test_wrapper_is_executable(self, ...):
        """Test wrapper has execute permissions."""

    def test_wrapper_has_no_template_vars(self, ...):
        """Test template substitution."""
```

**Impact**:
- Harder to navigate test files
- Unclear test relationships
- Less IDE support for test navigation

### 8. Subprocess Error Handling Inconsistencies

**Location**: All test files

**Problem**: Inconsistent error handling for subprocess calls.

**Examples**:

Good (explicit check and error message):
```python
# test_init.py line 201
result = run_qen(["init"], temp_config_dir, cwd=meta_repo)
assert result.returncode == 0, f"qen init failed: {result.stderr}"
```

Inconsistent (sometimes uses check=True):
```python
# test_pull.py line 163
result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30)
assert result.returncode == 0, f"qen pull failed: {result.stderr}"
```

Could use:
```python
result = run_qen(["pull"], temp_config_dir, cwd=meta_repo, timeout=30, check=True)
# No assertion needed - will raise CalledProcessError
```

But then inconsistent with other tests that need to check output even on success.

**Impact**:
- Harder to understand error handling strategy
- Some tests might not catch failures correctly
- Inconsistent debugging experience

### 9. Excellent Pattern: Standard PR Optimization

**Location**: `test_pull.py`, `test_pr_status.py`, `constants.py`

**POSITIVE EXAMPLE** - This is EXCELLENT and should be used more widely:

`constants.py`:
```python
"""Standard reference PR constants for integration tests."""

STANDARD_PRS = {
    "passing": 215,
    "failing": 216,
    "issue": 217,
    "stack": [218, 219, 220],
}

STANDARD_BRANCHES = {
    "passing": "ref-passing-checks",
    "failing": "ref-failing-checks",
    "issue": "ref-issue-456-test",
}
```

Usage in `test_pull.py`:
```python
def test_pull_updates_pr_metadata_standard(
    temp_config_dir: Path,
    tmp_path: Path,
) -> None:
    """Test qen pull reads standard PR and updates pyproject.toml.

    Uses permanent reference PR instead of creating new PR.
    This is MUCH faster (3s vs 21s) with no loss of test quality.

    NO MOCKS - uses real GitHub API to verify PR metadata.
    """
    pr_number = STANDARD_PRS["passing"]
    pr_data = verify_standard_pr_exists(pr_number)
    branch = STANDARD_BRANCHES["passing"]

    # Clone existing branch (no PR creation!)
    clone_standard_branch(project_dir, branch)
    # ... rest of test
```

**Why this is excellent**:
- ✅ Dramatically faster (3s vs 21s per test)
- ✅ No loss of test quality (still uses real API)
- ✅ More reliable (no race conditions from PR creation)
- ✅ Permanent test fixtures
- ✅ Well-documented with docstrings

**Opportunity**: Apply this pattern to more tests in `test_add.py`, `test_status.py`, etc.

### 10. Missing Parametrization Opportunities

**Location**: `test_qen_wrapper.py`, `test_add.py`

**Problem**: Similar tests repeated instead of using parametrize.

**Example** - `test_qen_wrapper.py` lines 165-269 (3 similar tests):

```python
def test_qen_wrapper_from_parent_directory(...):
    """Test wrapper works from parent directory."""
    # ... setup
    result = subprocess.run([str(qen_wrapper), ...], cwd=proj_parent)
    assert "bash:" not in result.stderr.lower()

def test_qen_wrapper_from_arbitrary_directory(...):
    """Test wrapper works from arbitrary directory."""
    # ... setup (almost identical)
    result = subprocess.run([str(qen_wrapper), ...], cwd=arbitrary_dir)
    assert "bash:" not in result.stderr.lower()

def test_qen_wrapper_project_context(...):
    """Test wrapper activates correct project context."""
    # ... different test but similar pattern
```

**Better approach**:
```python
@pytest.mark.parametrize("cwd_type,description", [
    ("project", "from project directory"),
    ("parent", "from parent directory"),
    ("arbitrary", "from arbitrary directory"),
])
def test_qen_wrapper_works_from_different_cwd(
    cwd_type: str,
    description: str,
    real_test_repo: Path,
    tmp_path: Path,
    ...
):
    """Test wrapper works from different working directories."""
    # Calculate cwd based on cwd_type
    # Run test
    # Single assertion logic
```

**Impact**:
- ~60 lines of duplicated test code in test_qen_wrapper.py alone
- More tests to maintain
- Harder to ensure all scenarios covered consistently

## Strengths Worth Preserving

### 1. NO MOCKS Policy Enforcement

Every test file starts with:
```python
"""Integration tests for X using REAL operations.

NO MOCKS ALLOWED. These tests use REAL git operations and REAL GitHub repositories.
"""
```

This is enforced consistently and rigorously. Excellent.

### 2. Excellent Helper Documentation

`conftest.py` helpers are well-documented:
```python
def run_qen(
    args: list[str],
    temp_config_dir: Path,
    cwd: Path | None = None,
    check: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run qen command with isolated config directory.

    This helper ensures all integration test qen calls use --config-dir
    to avoid polluting the user's actual qen configuration.

    Args:
        args: Command arguments (e.g., ["init", "my-project"])
        temp_config_dir: Temporary config directory from fixture
        cwd: Working directory for command (optional)
        check: Raise CalledProcessError if command fails (default: False)
        timeout: Command timeout in seconds (optional)

    Returns:
        CompletedProcess with stdout/stderr as text

    Example:
        result = run_qen(
            ["init", "test-project", "--yes"],
            temp_config_dir,
            cwd=repo_dir,
        )
        assert result.returncode == 0
    """
```

### 3. Standard PR Optimization Pattern

The standard reference PR pattern (constants.py + verify_standard_pr_exists) is exemplary:
- Fast (3s vs 21s)
- Reliable
- Real API usage
- Well documented

### 4. Test Isolation

Good use of temp_config_dir throughout:
```python
result = run_qen(["init"], temp_config_dir, cwd=meta_repo)
```

Prevents test pollution of user config.

## Comparison with Unit Test Issues

| Issue | Unit Tests | Integration Tests |
|-------|-----------|-------------------|
| Mock setup duplication | ❌❌❌ Heavy (~200 lines) | ✅ N/A (no mocks) |
| Git setup duplication | ❌❌ Moderate (~100 lines) | ❌❌❌ Heavy (~150 lines) |
| Type hint coverage | ❌ Inconsistent (~60%) | ❌❌ Poor (~40%) |
| Parametrization opportunities | ❌❌ Many missed | ❌ Some missed |
| Test organization | ❌ Inconsistent patterns | ❌ Mostly flat functions |
| Fixture organization | ❌ Scattered | ❌ Some duplication |
| Helper function duplication | ❌❌ Across many files | ✅ Better (in conftest) |
| Documentation quality | ❌ Variable | ✅ Good docstrings |
| Mock validation | ❌❌ Missing | ✅ N/A (no mocks) |
| Standard fixtures | ❌ Ad-hoc | ✅✅ Excellent (standard PRs) |

## Root Causes

These issues stem from:

1. **Organic growth** - Tests added incrementally without refactoring
2. **Different authors** - Inconsistent patterns across test files
3. **Speed optimization** - Standard PR pattern added later, not retrofitted to all tests
4. **Missing test utilities** - Git setup code not extracted to helpers
5. **Fixture scope confusion** - Unclear when to use conftest vs test-local fixtures
6. **Type hints deprioritized** - Tests exempt from strict type checking?

## Refactoring Strategy

### Phase 1: Extract Git Setup Helpers (1 day)

**Goal**: Eliminate git repository setup duplication

**Actions**:
1. Create `tests/integration/helpers.py`:
   ```python
   def create_test_git_repo(
       path: Path,
       *,
       branch: str = "main",
       user_name: str = "QEN Integration Test",
       user_email: str = "test@qen.local",
       with_remote: bool = True,
       remote_org: str = "test-org",
       remote_name: str = "test-meta",
   ) -> Path:
       """Create a test git repository with standard configuration.

       Returns path to created repository.
       """
   ```

2. Create `create_test_project()` helper:
   ```python
   def create_test_project(
       meta_repo: Path,
       project_name: str,
       config_dir: Path,
   ) -> tuple[Path, Path]:
       """Create a QEN test project.

       Returns (per_project_meta_path, project_dir_path).
       """
   ```

3. Update all tests to use new helpers

**Success Criteria**:
- Zero duplicated git setup code
- All tests use same helpers
- ~150 lines removed

### Phase 2: Add Type Hints (1 day)

**Goal**: Full type coverage for integration tests

**Actions**:
1. Add return type `-> None` to all test functions
2. Add type hints to all fixtures
3. Add type hints to helper functions in conftest.py
4. Enable mypy checking for tests/integration/

**Success Criteria**:
- 100% type hint coverage
- mypy passes on tests/integration/
- Consistent with project standards

### Phase 3: Consolidate TOML Utilities (0.5 days)

**Goal**: Use existing pyproject_utils module

**Actions**:
1. Create helper in `tests/integration/helpers.py`:
   ```python
   def add_test_repo_to_pyproject(
       project_dir: Path,
       url: str,
       branch: str = "main",
       path: str | None = None,
   ) -> None:
       """Add repository entry to test project's pyproject.toml."""
       # Use qen.pyproject_utils internally
   ```

2. Replace all inline TOML manipulation with helper
3. Add validation using existing schemas

**Success Criteria**:
- Zero inline TOML manipulation
- Uses project's own TOML utilities
- ~50 lines removed

### Phase 4: Reorganize Fixtures (1 day)

**Goal**: Clear fixture organization and elimination of duplication

**Actions**:
1. Create `tests/integration/conftest.py` for integration-specific fixtures
2. Move tmp_meta_repo fixture from test_init.py to integration conftest
3. Merge tmp_meta_repo and meta_prime_repo into single parameterizable fixture
4. Remove trivial wrapper fixtures (unique_project_name)
5. Document fixture usage in AGENTS.md

**Success Criteria**:
- No test-local fixtures that are used in multiple tests
- Clear documentation of when to use each fixture
- Reduced fixture count by ~20%

### Phase 5: Add Parametrization (1 day)

**Goal**: Reduce test duplication with parametrize

**Actions**:
1. Parametrize URL format tests in test_add.py:
   ```python
   @pytest.mark.parametrize("url_format,url,expected_norm", [
       ("https", "https://github.com/data-yaml/qen-test", "https://..."),
       ("ssh", "git@github.com:data-yaml/qen-test.git", "https://..."),
       ("short", "data-yaml/qen-test", "https://..."),
   ])
   def test_add_with_various_url_formats(...)
   ```

2. Parametrize wrapper location tests in test_qen_wrapper.py
3. Parametrize standard PR tests in test_pull.py

**Success Criteria**:
- ~10 test functions converted to 3-4 parametrized tests
- ~100 lines removed
- Better test names with parameter values

### Phase 6: Improve Assertion Messages (0.5 days)

**Goal**: Consistent, helpful assertion messages

**Actions**:
1. Add assertion messages to all assertions without them
2. Include relevant context (paths, values, output)
3. Use consistent format:
   ```python
   assert condition, f"Expected X, got Y. Context: {z}"
   ```

**Success Criteria**:
- Every assertion has helpful message
- Failed tests easier to debug
- Consistent message format

### Phase 7: Apply Standard PR Pattern More Widely (1 day)

**Goal**: Use standard PRs in more tests

**Actions**:
1. Identify tests that create PRs dynamically
2. Convert to use standard reference PRs from constants.py
3. Add new standard PRs if needed
4. Update scripts/ensure_test_repo.py if needed

**Success Criteria**:
- All PR tests use standard PRs
- Test suite 30-40% faster
- Same or better coverage

## Implementation Plan

### Week 1
- [x] Phase 1: Extract Git Setup Helpers (1 day)
- [x] Phase 2: Add Type Hints (1 day)
- [x] Phase 3: Consolidate TOML Utilities (0.5 days)
- [x] Phase 4: Reorganize Fixtures (1 day)

### Week 2
- [x] Phase 5: Add Parametrization (1 day)
- [x] Phase 6: Improve Assertion Messages (0.5 days)
- [x] Phase 7: Apply Standard PR Pattern (1 day)
- [x] Final validation and documentation (1 day)

**Total Estimated Time**: 2 weeks (part-time effort)

## Success Criteria

### Quantitative Metrics
- [ ] Test code reduced by 15-20% (from ~2,000 to ~1,600 lines)
- [ ] Git setup duplication eliminated (0 duplicated git init patterns)
- [ ] 100% type hint coverage in integration tests
- [ ] Test execution time reduced by 30-40% (from wider use of standard PRs)
- [ ] All 10 test files follow consistent patterns

### Qualitative Improvements
- [ ] New integration tests can be written faster using shared utilities
- [ ] Test failures easier to debug with better assertions
- [ ] Clear separation between conftest fixtures and test-local fixtures
- [ ] Consistent subprocess error handling
- [ ] Better test organization with parametrize

### Validation Tests
- [ ] Run `./poe test-integration` - all tests pass
- [ ] Run `mypy tests/integration/ --strict` - no errors
- [ ] Time test suite - should be 30-40% faster
- [ ] Verify pre-commit hooks still pass
- [ ] Manual review of 3 refactored test files for quality

## Dependencies and Blockers

### Dependencies
- **None** - This refactoring is self-contained within tests/integration/

### Potential Blockers
1. **Test breakage during refactoring**
   - Mitigation: Refactor incrementally, run tests after each change
   - Mitigation: Keep old and new patterns side-by-side temporarily

2. **Standard PR maintenance**
   - Mitigation: Document standard PR creation in scripts/
   - Mitigation: Monitor qen-test repository for PR state

3. **Type hint complexity**
   - Mitigation: Start with simple function signatures
   - Mitigation: Use type: ignore where needed temporarily

## Related Tech Debt

### Related Documents
- `07-unit-tests.md` - Unit test technical debt (many similar patterns)
- `spec/2-status/07-repo-qen-test.md` - Integration testing specification

### Related Issues
- Standard PR pattern should be documented in AGENTS.md
- conftest.py is large but better organized than unit test conftest
- No CI/CD pipeline yet for automated integration test runs

## Metadata

**Document Created**: 2025-12-11
**Analyzed Files**: 10 integration test files (~2,000 lines)
**Priority**: Medium-High
**Estimated Effort**: 2 weeks (part-time)
**Impact**: High (maintainability, speed) / Low (functionality)

---

*Analysis generated by Claude Sonnet 4.5*
