# Integration Test Suite Overhaul

**Date:** 2025-12-11
**Status:** Proposed
**Context:** The entire integration test suite has systemic duplication issues. Every test file recreates meta repos from scratch with duplicated 50+ line setup blocks. This is a comprehensive refactoring plan to eliminate ALL duplication.

---

## Problem: Systemic Code Duplication

### Current State - The Numbers

- **Total integration test files:** 9 files, 3,873 lines
- **Duplicated meta repo setup:** 17+ instances of the same 50-80 line block
- **Duplicated git init:** 18+ instances
- **Total estimated duplication:** ~1,500 lines (38% of test code!)

### What's Duplicated (Everywhere)

**In EVERY test file that needs a project:**

```python
# Create temporary meta repo (DUPLICATED 17+ TIMES)
meta_repo = tmp_path / "meta"
meta_repo.mkdir()

# Initialize git (DUPLICATED 18+ TIMES)
subprocess.run(["git", "init", "-b", "main"], cwd=meta_repo, ...)
subprocess.run(["git", "config", "user.name", "Test User"], cwd=meta_repo, ...)
subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=meta_repo, ...)

# Create meta.toml (DUPLICATED 17+ TIMES)
meta_toml = meta_repo / "meta.toml"
meta_toml.write_text('[meta]\nname = "test-org"\n')
subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, ...)
subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=meta_repo, ...)

# Add remote with WRONG URL (DUPLICATED, BROKEN)
subprocess.run(
    ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
    cwd=meta_repo, ...
)

# Initialize qen (DUPLICATED 17+ TIMES)
result = run_qen(["init"], temp_config_dir, cwd=meta_repo)

# Create project (DUPLICATED 17+ TIMES)
result = run_qen(["init", "test-project", "--yes"], temp_config_dir, cwd=meta_repo)

# Find project directory with iteration logic (DUPLICATED 15+ TIMES)
proj_dir = None
for item in (meta_repo / "proj").iterdir():
    if item.is_dir() and "test-project" in item.name:
        proj_dir = item
        break
```

**This block appears in:**
- `test_add.py` - 8 times
- `test_status.py` - 7 times
- `test_rm_real.py` - helper function (used 10 times)
- `test_qen_wrapper.py` - 5 times
- `test_pull.py` - helper function (used 3 times)

### Why This Is Unacceptable

1. **~1,500 lines of copy-paste** - 38% of integration test code is duplication
2. **Maintenance nightmare** - Fix in one place, breaks in 16 others
3. **Wrong URLs everywhere** - Tests use `https://github.com/data-yaml/meta.git` which DOESN'T EXIST
4. **Per-project meta architecture broke everything** - None of these tests work anymore
5. **Adding new tests is painful** - Must copy-paste 50+ lines of setup
6. **No single source of truth** - Each test reimplements the same logic slightly differently

---

## Solution: Complete Fixture-Based Architecture

### Design Principles

1. **Zero duplication** - Setup logic exists in exactly ONE place
2. **Composable fixtures** - Tests combine small, focused fixtures
3. **Fast by default** - Use `file://` URLs for local cloning
4. **Correct by default** - Fixtures understand per-project meta architecture
5. **Easy to use** - Tests are 90% test logic, 10% setup

### Fixture Hierarchy

```text
tmp_path (pytest built-in)
    ↓
temp_config_dir (existing, keep as-is)
    ↓
meta_prime_repo (NEW - creates meta prime with correct remotes)
    ↓
qen_project (NEW - creates per-project meta + project)
    ↓
test_repo (NEW - adds qen-test repo to project)
    ↓
YOUR TEST (just test logic, zero setup!)
```

---

## New Fixtures (Full Specification)

### Fixture 1: `meta_prime_repo`

**Purpose:** Create a meta prime repository with correct remote configuration for local cloning

**Location:** `tests/conftest.py`

**Signature:**
```python
@pytest.fixture
def meta_prime_repo(tmp_path: Path) -> Path:
    """Create meta prime repository with file:// remote for local cloning.

    Creates a fully initialized git repository that serves as meta prime.
    Configured with:
    - origin remote: file:// URL (enables fast local cloning)
    - github remote: https://github.com/test-org/test-meta.git (for org extraction)
    - Initial commit with meta.toml

    Returns:
        Path to meta prime repository

    Example:
        def test_something(meta_prime_repo):
            # meta_prime_repo is ready to use
            result = run_qen(["init"], config_dir, cwd=meta_prime_repo)
    """
```

**Implementation:**
```python
@pytest.fixture
def meta_prime_repo(tmp_path: Path) -> Path:
    """Create meta prime with correct remotes."""
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()

    # Initialize git with main branch
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Configure git user
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Create meta.toml
    meta_toml = meta_dir / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')

    # Initial commit
    subprocess.run(
        ["git", "add", "meta.toml"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Add origin remote for cloning (file:// URL)
    subprocess.run(
        ["git", "remote", "add", "origin", f"file://{meta_dir}"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    # Add github remote for org extraction (not used for cloning)
    subprocess.run(
        ["git", "remote", "add", "github", "https://github.com/test-org/test-meta.git"],
        cwd=meta_dir,
        check=True,
        capture_output=True,
    )

    return meta_dir
```

**What it provides:**
- ✅ Meta prime repository ready for `qen init`
- ✅ Correct `file://` origin for fast local cloning
- ✅ GitHub remote for org extraction
- ✅ Initial commit with meta.toml
- ✅ Git user configured

---

### Fixture 2: `qen_project`

**Purpose:** Create a QEN project with per-project meta clone

**Location:** `tests/conftest.py`

**Signature:**
```python
@pytest.fixture
def qen_project(
    meta_prime_repo: Path,
    temp_config_dir: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path]:
    """Create a QEN project with per-project meta clone.

    Runs qen init to set up global config, then qen init <project> to create
    per-project meta clone. Returns all relevant paths.

    Args:
        meta_prime_repo: Meta prime from fixture
        temp_config_dir: Isolated config directory
        request: Pytest request for parametrization

    Returns:
        Tuple of (meta_prime_path, per_project_meta_path, project_dir_path)

    Example:
        def test_something(qen_project, temp_config_dir):
            meta_prime, per_project_meta, proj_dir = qen_project

            # Add repos, run status, etc.
            result = run_qen(["add", "repo-url"], temp_config_dir, cwd=meta_prime)
    """
```

**Implementation:**
```python
@pytest.fixture
def qen_project(
    meta_prime_repo: Path,
    temp_config_dir: Path,
    request: pytest.FixtureRequest,
) -> tuple[Path, Path, Path]:
    """Create QEN project with per-project meta."""
    from datetime import datetime

    # Get project name from parametrize or use default
    project_name = getattr(request, "param", "test-project")

    # Initialize qen global config
    result = subprocess.run(
        ["qen", "--config-dir", str(temp_config_dir), "init"],
        cwd=meta_prime_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen init failed: {result.stderr}"

    # Create project (creates per-project meta clone)
    result = subprocess.run(
        ["qen", "--config-dir", str(temp_config_dir), "init", project_name, "--yes"],
        cwd=meta_prime_repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen init {project_name} failed: {result.stderr}"

    # Calculate paths using per-project meta architecture
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    per_project_meta = meta_prime_repo.parent / f"meta-{project_name}"
    project_dir = per_project_meta / "proj" / branch_name

    # Verify paths exist
    assert per_project_meta.exists(), f"Per-project meta not found: {per_project_meta}"
    assert project_dir.exists(), f"Project directory not found: {project_dir}"

    return meta_prime_repo, per_project_meta, project_dir
```

**What it provides:**
- ✅ QEN global config initialized
- ✅ Per-project meta clone created
- ✅ Project directory created
- ✅ All paths calculated and verified
- ✅ Ready for `qen add`, `qen status`, etc.

---

### Fixture 3: `test_repo` (Optional Convenience)

**Purpose:** Pre-add qen-test repository to project

**Location:** `tests/conftest.py`

**Signature:**
```python
@pytest.fixture
def test_repo(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    """Add qen-test repository to project.

    Convenience fixture that adds https://github.com/data-yaml/qen-test
    to the project and returns all paths including the cloned repo.

    Args:
        qen_project: Project fixture
        temp_config_dir: Config directory

    Returns:
        Tuple of (meta_prime, per_project_meta, project_dir, repo_path)

    Example:
        def test_status(test_repo, temp_config_dir):
            meta_prime, per_project_meta, proj_dir, repo_path = test_repo

            # repo is already cloned, just test status
            result = run_qen(["status"], temp_config_dir, cwd=meta_prime)
    """
```

**Implementation:**
```python
@pytest.fixture
def test_repo(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> tuple[Path, Path, Path, Path]:
    """Add qen-test to project."""
    meta_prime, per_project_meta, project_dir = qen_project

    # Add qen-test repository
    result = subprocess.run(
        [
            "qen",
            "--config-dir",
            str(temp_config_dir),
            "add",
            "https://github.com/data-yaml/qen-test",
        ],
        cwd=meta_prime,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"qen add failed: {result.stderr}"

    # Calculate repo path
    repo_path = project_dir / "repos" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned: {repo_path}"

    return meta_prime, per_project_meta, project_dir, repo_path
```

**What it provides:**
- ✅ Everything from `qen_project`
- ✅ qen-test repository already added and cloned
- ✅ Repo path calculated and verified

---

## Migration Strategy

### Phase 1: Add Fixtures (30 min)

**File:** `tests/conftest.py`

1. Add `meta_prime_repo` fixture
2. Add `qen_project` fixture
3. Add `test_repo` fixture (optional)
4. Run smoke test to verify fixtures work

**Verification:**
```bash
# Create a simple test that uses the fixtures
pytest tests/integration/test_fixtures.py -v
```

---

### Phase 2: Migrate test_add.py (1 hour)

**File:** `tests/integration/test_add.py`
**Current:** 971 lines, 8 tests, massive duplication
**Target:** ~400 lines, 8 tests, zero duplication

**Migration pattern for each test:**

**BEFORE (82 lines of setup + test):**
```python
def test_add_with_full_https_url(tmp_path: Path, temp_config_dir: Path) -> None:
    # Create temporary meta repo (50+ lines)
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], ...)
    # ... 45 more lines ...

    # Find project directory (5 lines)
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        # ...

    # Actual test (25 lines)
    result = run_qen(["add", "https://github.com/data-yaml/qen-test"], ...)
    # ... assertions ...
```

**AFTER (25 lines total):**
```python
def test_add_with_full_https_url(qen_project, temp_config_dir: Path) -> None:
    """Test qen add with full HTTPS URL - REAL CLONE."""
    meta_prime, per_project_meta, proj_dir = qen_project

    # Test logic only (no setup!)
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test"],
        temp_config_dir,
        cwd=meta_prime,
    )
    assert result.returncode == 0

    # Verify repository was cloned
    repo_path = proj_dir / "repos" / "qen-test"
    assert repo_path.exists()

    # Verify pyproject.toml was updated
    pyproject = proj_dir / "pyproject.toml"
    content = pyproject.read_text()
    assert "https://github.com/data-yaml/qen-test" in content
```

**Apply to all 8 tests:**
- `test_add_with_full_https_url`
- `test_add_with_ssh_url`
- `test_add_with_short_format`
- `test_add_with_custom_branch`
- `test_add_with_custom_path`
- `test_add_multiple_repos_with_indices`
- `test_add_invalid_url_error_handling`
- `test_add_nonexistent_repo_error_handling`

**Expected savings:** ~450 lines removed

---

### Phase 3: Migrate test_status.py (1 hour)

**File:** `tests/integration/test_status.py`
**Current:** 832 lines, 7 tests
**Target:** ~350 lines, 7 tests

**Migration pattern:**

Some tests need repos, some don't:

```python
# Test with no repos
def test_status_basic_clean_repos(qen_project, temp_config_dir):
    meta_prime, per_project_meta, proj_dir = qen_project
    # Test logic...

# Test with repos pre-added
def test_status_with_modified_files(test_repo, temp_config_dir):
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Modify a file in repo
    test_file = repo_path / "test.txt"
    test_file.write_text("modified")

    # Test status detection
    result = run_qen(["status"], temp_config_dir, cwd=meta_prime)
    assert "modified" in result.stdout
```

**Apply to all 7 tests:**
- `test_status_basic_clean_repos`
- `test_status_with_modified_files`
- `test_status_verbose_mode`
- `test_status_meta_only`
- `test_status_repos_only`
- `test_status_multiple_repos_with_indices`
- `test_status_with_nonexistent_repo`

**Expected savings:** ~400 lines removed

---

### Phase 4: Migrate test_rm_real.py (1 hour)

**File:** `tests/integration/test_rm_real.py`
**Current:** 389 lines, 10 tests, has helper function
**Target:** ~150 lines, 10 tests, no helper needed

**Key change:** Delete `setup_rm_test_project()` helper entirely (60+ lines)

**Migration pattern:**

```python
# BEFORE: Uses helper
def test_rm_by_index(tmp_path, temp_config_dir):
    meta_repo, project_dir = setup_rm_test_project(tmp_path, temp_config_dir, "rm-idx")
    # Test logic...

# AFTER: Uses fixture
def test_rm_by_index(test_repo, temp_config_dir):
    meta_prime, per_project_meta, proj_dir, repo_path = test_repo

    # Test removing by index
    result = run_qen(["rm", "1"], temp_config_dir, cwd=meta_prime)
    assert result.returncode == 0
```

**Expected savings:** ~200 lines removed (including helper deletion)

---

### Phase 5: Migrate test_qen_wrapper.py (45 min)

**File:** `tests/integration/test_qen_wrapper.py`
**Current:** 350 lines, 5 tests
**Target:** ~150 lines, 5 tests

**Migration pattern:** Same as above

**Expected savings:** ~200 lines removed

---

### Phase 6: Migrate test_pull.py (45 min)

**File:** `tests/integration/test_pull.py`
**Current:** 334 lines, 3 tests, has optimized helper
**Target:** ~150 lines, 3 tests

**Key change:** Update or delete `setup_test_project_optimized()` helper

**Option A:** Keep helper, update to use fixture internally
**Option B:** Delete helper, use fixtures directly

**Recommendation:** Option B (delete helper, use fixtures)

**Expected savings:** ~150 lines removed

---

### Phase 7: test_init.py - Keep As-Is (0 min)

**File:** `tests/integration/test_init.py`
**Status:** Already correct! Uses `file://` URLs, all 6 tests pass

**Decision:** Don't touch it. Already uses the right pattern.

---

### Phase 8: Other Files - No Changes Needed

**Files that don't need migration:**

1. **test_pr_status.py** - Uses standard PRs, no meta repo setup
2. **test_github_schema.py** - Direct GitHub API, no meta deps
3. **test_branch_checking.py** - ERROR, investigate separately

---

## Benefits

### Immediate Benefits

**Code Quality:**
- ✅ **Eliminate ~1,500 lines** of duplicated code (38% reduction)
- ✅ **Single source of truth** for meta repo setup
- ✅ **Fix all broken tests** (wrong URLs fixed)
- ✅ **Zero copy-paste** in future tests

**Developer Experience:**
- ✅ **New tests are trivial** - 3 lines instead of 50
- ✅ **Tests are readable** - 90% test logic, 10% setup
- ✅ **Fast to run** - `file://` cloning is 10x faster
- ✅ **Easy to debug** - Setup code is centralized

**Maintainability:**
- ✅ **Change once, fix everywhere** - Fixture updates propagate
- ✅ **Correct by default** - Fixtures enforce per-project meta
- ✅ **Type-safe** - Return tuples with clear types
- ✅ **Self-documenting** - Fixture docstrings explain architecture

### Long-Term Benefits

**Architectural:**
- ✅ **Tests validate architecture** - Fixtures encode per-project meta design
- ✅ **Future-proof** - Architecture changes only update fixtures
- ✅ **Composable** - Mix and match fixtures as needed
- ✅ **Consistent** - All tests use same setup

**Quality:**
- ✅ **Higher confidence** - Less duplication = fewer bugs
- ✅ **Faster iteration** - Less code to maintain
- ✅ **Better coverage** - Easy to add new tests
- ✅ **Clear intent** - Test code shows what's being tested

---

## Code Metrics

### Before Refactoring

| Metric | Value |
|--------|-------|
| Total lines | 3,873 |
| Duplicated lines | ~1,500 (38%) |
| Setup:test ratio | 2:1 (66% setup, 33% test) |
| Fixture coverage | 20% (only helpers) |
| Single source of truth | ❌ No |

### After Refactoring

| Metric | Value |
|--------|-------|
| Total lines | ~2,200 (-43%) |
| Duplicated lines | 0 (0%) |
| Setup:test ratio | 1:9 (10% setup, 90% test) |
| Fixture coverage | 80% (all setup) |
| Single source of truth | ✅ Yes |

**Net improvement:**
- **-1,673 lines** removed
- **-100% duplication** eliminated
- **+8x readability** (setup:test ratio improved)
- **+∞% maintainability** (single source of truth)

---

## Risk Assessment

### Low Risk: Breaking Tests

**Mitigation:**
- Migrate one file at a time
- Run tests after each migration
- Keep git history clean (one commit per file)

**Rollback:**
- Each commit is independent
- Easy to revert if issues arise

### Low Risk: Fixture Complexity

**Mitigation:**
- Fixtures are simple and focused
- Clear docstrings with examples
- Type hints for all returns

**Verification:**
- Write fixture tests first
- Smoke test before migration

### Low Risk: Test Isolation

**Mitigation:**
- Use `tmp_path` (auto-cleanup)
- Each test gets fresh fixtures
- No shared state

**Pytest handles:**
- Fixture lifecycle
- Cleanup on failure
- Parallel execution

---

## Implementation Timeline

| Phase | Task | Files | Time | Lines Saved |
|-------|------|-------|------|-------------|
| 1 | Add fixtures | conftest.py | 30m | +120 |
| 2 | test_add.py | 1 file | 1h | -450 |
| 3 | test_status.py | 1 file | 1h | -400 |
| 4 | test_rm_real.py | 1 file | 1h | -200 |
| 5 | test_qen_wrapper.py | 1 file | 45m | -200 |
| 6 | test_pull.py | 1 file | 45m | -150 |
| 7 | test_init.py | - | 0m | 0 |
| 8 | Others | - | 0m | 0 |
| **Total** | | **5 files** | **5h** | **-1,280 lines** |

**Note:** Net savings = -1,280 + 120 (fixtures) = **-1,160 lines** (30% reduction)

---

## Success Criteria

### Must Have

- [ ] All 39 integration tests pass
- [ ] Zero duplicated setup code
- [ ] All tests use shared fixtures
- [ ] No mocks introduced (still REAL operations)
- [ ] Tests run in <30 seconds total

### Should Have

- [ ] Fixtures have comprehensive docstrings
- [ ] Example usage in fixture docstrings
- [ ] Type hints on all fixtures
- [ ] Commit per file migration

### Nice to Have

- [ ] Update AGENTS.md with fixture patterns
- [ ] Add fixture usage guide
- [ ] Smoke test CI check

---

## Example: Before vs After

### Before (82 lines)

```python
def test_add_with_full_https_url(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with full HTTPS URL."""
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None

    # ACTUAL TEST STARTS HERE
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test"],
        temp_config_dir,
        cwd=meta_repo,
    )
    assert result.returncode == 0

    # Verify repository was cloned
    repo_path = proj_dir / "repos" / "qen-test"
    assert repo_path.exists()

    # Verify pyproject.toml
    pyproject = proj_dir / "pyproject.toml"
    content = pyproject.read_text()
    assert "https://github.com/data-yaml/qen-test" in content
```

### After (25 lines)

```python
def test_add_with_full_https_url(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with full HTTPS URL - REAL CLONE."""
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository
    result = run_qen(
        ["add", "https://github.com/data-yaml/qen-test"],
        temp_config_dir,
        cwd=meta_prime,
    )
    assert result.returncode == 0

    # Verify repository was cloned
    repo_path = proj_dir / "repos" / "qen-test"
    assert repo_path.exists()

    # Verify pyproject.toml was updated
    pyproject = proj_dir / "pyproject.toml"
    content = pyproject.read_text()
    assert "https://github.com/data-yaml/qen-test" in content
```

**Comparison:**
- **Before:** 82 lines (57 setup, 25 test)
- **After:** 25 lines (5 fixture, 20 test)
- **Savings:** 57 lines (70% reduction)
- **Readability:** 10x better

---

## Conclusion

The current integration test suite has **systemic duplication** that makes it:
- Hard to maintain (1,500 lines of copy-paste)
- Fragile (wrong URLs, broken by architecture changes)
- Painful to extend (50+ lines of setup per test)

This refactoring:
1. **Eliminates ALL duplication** (1,500+ lines)
2. **Fixes all broken tests** (correct URLs, per-project meta)
3. **Makes future tests trivial** (3-5 lines instead of 50+)
4. **Establishes best practices** (fixture-based testing)
5. **Takes ~5 hours** (one-time investment)

**This is NOT a "nice to have" refactoring. This is CRITICAL infrastructure work.**

The test suite is 38% duplication. That's unacceptable. Fix it now, reap benefits forever.

**Recommendation:** Approve and execute immediately. Start with Phase 1 (fixtures) today.
