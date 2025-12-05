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
