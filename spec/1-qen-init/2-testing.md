# Spec: Testing Strategy

## Overview

Minimal testing approach for qen and qenvy focusing on critical paths and CI automation.

## Test Structure

```
tests/
├── qen/
│   ├── test_init.py          # qen init command
│   ├── test_add.py           # qen add command
│   ├── test_config.py        # Config management
│   └── integration/
│       └── test_workflow.py  # End-to-end workflows
└── qenvy/
    ├── test_storage.py       # File I/O, atomic writes
    ├── test_inheritance.py   # Profile inheritance
    ├── test_validation.py    # Config validation
    └── test_formats.py       # TOML/JSON parsing
```

## qen Tests

### Unit Tests
- **test_init.py:** Meta repo discovery, org inference, config creation, error conditions
- **test_add.py:** Repo addition, branch handling, meta.toml updates
- **test_config.py:** Config read/write, project switching

### Integration Tests
- **test_workflow.py:** Full workflow: init → create project → add repos → status

## qenvy Tests

### Unit Tests
- **test_storage.py:** Atomic writes, backups, XDG paths, profile CRUD
- **test_inheritance.py:** Single/multi-level inheritance, circular detection, deep merge
- **test_validation.py:** Metadata validation, custom validators
- **test_formats.py:** TOML/JSON serialization, format errors

## Test Tooling

**Framework:** pytest

**Coverage target:** >80% for core logic (init, add, storage, inheritance)

**Poe tasks:**
```toml
[tool.poe.tasks]
test = "pytest tests/ -v"
test-cov = "pytest tests/ --cov=src --cov-report=term --cov-report=html"
test-fast = "pytest tests/ -x"  # Stop on first failure
```

## CI Pipeline

### `.github/workflows/test.yml`

**Triggers:** Push to all branches, PRs

**Jobs:**

1. **Test**
   - Matrix: Python 3.12, 3.13
   - Matrix: Ubuntu, macOS
   - Run: `uv run pytest tests/ --cov`
   - Upload coverage to codecov

2. **Lint**
   - Run: `uv run ruff check .`
   - Run: `uv run mypy src/`

3. **Build**
   - Run: `uv build`
   - Verify package installs: `uv pip install dist/*.whl`

**Required checks:** test, lint, build must pass before merge

### Existing `.github/workflows/publish.yml`

Keep as-is. Triggers on tags for PyPI, branches for TestPyPI.

## Testing Guidelines

1. **Fail fast:** Use fixtures that create/cleanup temp directories
2. **Mock git:** Use temporary git repos for integration tests
3. **Isolate XDG:** Override `XDG_CONFIG_HOME` in tests
4. **Test errors:** Verify error messages and exit codes
5. **No network:** All tests run offline (mock git remotes if needed)

## Dependencies

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]
```

## Tasks

1. Create test directory structure
2. Write qen unit tests (init, add, config)
3. Write qen integration test (full workflow)
4. Write qenvy unit tests (storage, inheritance, validation, formats)
5. Add pytest configuration to pyproject.toml
6. Add poe test tasks
7. Create `.github/workflows/test.yml`
8. Add dev dependencies
9. Configure coverage reporting

## Appendix: In-Memory Test Config (Avoiding Environment Variable Manipulation)

### Problem

Manipulating environment variables like `XDG_CONFIG_HOME` in tests is a code smell because:

1. Environment variables are global state that can leak between tests
2. Cache invalidation is unreliable across different platformdirs versions
3. Tests become dependent on environment setup rather than explicit configuration

### Solution: In-Memory Test Implementation

Create an in-memory storage backend that extends the base configuration class without touching the filesystem or environment.

**Reference:** `/Users/ernest/GitHub/benchling-webhook/test/helpers/xdg-test.ts`

### Implementation

**File:** `tests/helpers/qenvy_test.py`

```python
"""In-memory QenvyConfig implementation for testing.

Provides an in-memory storage backend that implements the same interface
as QenvyConfig but stores all data in dictionaries instead of files.

This eliminates the need to manipulate XDG_CONFIG_HOME or clear platformdirs caches.
"""

from pathlib import Path
from typing import Any

from qenvy.base import QenvyBase
from qenvy.exceptions import ProfileNotFoundError
from qenvy.formats import TOMLHandler
from qenvy.types import ProfileConfig


class QenvyTest(QenvyBase):
    """In-memory configuration storage for testing.

    Extends QenvyBase with dict-based storage primitives.
    All business logic (validation, inheritance) is inherited from QenvyBase,
    ensuring identical behavior to the production filesystem implementation.

    Example:
        ```python
        storage = QenvyTest()

        # Write and read profiles
        storage.write_profile("test", {"key": "value"})
        config = storage.read_profile("test")

        # Clear all data after test
        storage.clear()
        ```
    """

    def __init__(self, app_name: str = "qen", format: str = "toml"):
        """Initialize in-memory storage.

        Args:
            app_name: Application name (for compatibility)
            format: Configuration format (for compatibility)
        """
        self.app_name = app_name
        self.format_handler = TOMLHandler() if format == "toml" else None
        self._profiles: dict[str, ProfileConfig] = {}

    def clear(self) -> None:
        """Clear all stored data (useful for test cleanup)."""
        self._profiles.clear()

    # Storage Primitives Implementation (In-Memory)

    def _read_profile_raw(self, profile: str) -> ProfileConfig:
        """Read raw profile from memory without validation.

        Args:
            profile: Profile name

        Returns:
            Deep copy of profile configuration

        Raises:
            ProfileNotFoundError: If profile not found
        """
        if profile not in self._profiles:
            raise ProfileNotFoundError(profile)

        # Return deep copy to prevent mutations
        import copy
        return copy.deepcopy(self._profiles[profile])

    def _write_profile_raw(self, profile: str, config: ProfileConfig) -> None:
        """Write raw profile to memory without validation.

        Args:
            profile: Profile name
            config: Configuration to write
        """
        import copy
        self._profiles[profile] = copy.deepcopy(config)

    def _delete_profile_raw(self, profile: str) -> None:
        """Delete profile from memory.

        Args:
            profile: Profile name
        """
        self._profiles.pop(profile, None)

    def _list_profiles_raw(self) -> list[str]:
        """List all profile names from memory.

        Returns:
            Sorted list of profile names
        """
        return sorted(self._profiles.keys())

    def _profile_exists_raw(self, profile: str) -> bool:
        """Check if profile exists in memory.

        Args:
            profile: Profile name

        Returns:
            True if profile exists
        """
        return profile in self._profiles

    def _ensure_base_dir_exists(self) -> None:
        """No-op for in-memory storage."""
        pass

    def get_base_dir(self) -> Path:
        """Return a fake base directory for compatibility.

        Returns:
            Path to fake directory (not actually used)
        """
        return Path("/tmp/qen-test")
```

### Usage in Tests

**File:** `tests/conftest.py`

```python
import pytest
from pathlib import Path

from tests.helpers.qenvy_test import QenvyTest


@pytest.fixture
def test_storage() -> QenvyTest:
    """Provide clean in-memory storage for each test.

    Returns:
        Fresh QenvyTest instance that will be cleaned up after test
    """
    storage = QenvyTest()
    yield storage
    storage.clear()


@pytest.fixture
def test_config(test_storage: QenvyTest, tmp_path: Path) -> tuple[QenvyTest, Path]:
    """Provide test storage and temp directory.

    Returns:
        Tuple of (storage, meta_repo_path)
    """
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize with test data
    storage.write_profile("main", {
        "meta_path": str(meta_repo),
        "org": "testorg",
        "current_project": None,
    })

    return storage, meta_repo
```

**File:** `tests/qen/test_add.py` (updated)

```python
def test_add_repository_full_workflow(
    test_storage: QenvyTest,
    tmp_path: Path,
    child_repo: Path,
) -> None:
    """Test adding repository with in-memory config."""
    # Setup
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Write config to in-memory storage
    test_storage.write_profile("main", {
        "meta_path": str(meta_repo),
        "org": "testorg",
        "current_project": "test-project",
    })

    # Create project structure
    project_dir = meta_repo / "proj/2025-12-05-test-project"
    project_dir.mkdir(parents=True)
    (project_dir / "repos").mkdir()
    (project_dir / "pyproject.toml").write_text('[tool.qen]\\ncreated = "2025-12-05"\\n')

    test_storage.write_profile("test-project", {
        "branch": "2025-12-05-test-project",
        "folder": "proj/2025-12-05-test-project",
        "created": "2025-12-05T10:00:00Z",
    })

    # Test: Pass storage explicitly to add_repository
    add_repository(
        repo=str(child_repo),
        branch="main",
        path=None,
        verbose=False,
        storage=test_storage,  # Explicit dependency injection
    )

    # Verify: Repository was cloned and config updated
    assert (project_dir / "repos/child_repo").exists()
```

### Benefits

1. **No environment manipulation** - Tests don't touch `XDG_CONFIG_HOME`
2. **Explicit dependencies** - Pass storage directly to functions
3. **Fast and reliable** - No filesystem I/O, no cache invalidation issues
4. **Identical behavior** - Inherits all business logic from base class
5. **Easy cleanup** - Just call `storage.clear()`

### Migration Steps

1. Create `tests/helpers/qenvy_test.py` with in-memory implementation
2. Update command functions to accept optional `storage` parameter
3. Update fixtures to use `QenvyTest` instead of monkeypatching env vars
4. Remove `isolated_config` fixture and XDG_CONFIG_HOME manipulation
5. Update all tests to use in-memory storage
