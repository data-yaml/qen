# AGENTS.md - AI Agent Guide for QEN Development

This guide helps AI coding agents (like Claude Code, GitHub Copilot, Cursor, etc.) understand and work effectively with the QEN codebase.

## Quick Reference

**Primary Documentation:** See [README.md](README.md) for full project details, philosophy, and user-facing documentation.

**Technology Stack:**

- Python 3.12+ (strict type checking with mypy)
- Click for CLI
- Poe the Poet for task running
- uv for package management (preferred)
- pre-commit for git hooks
- pytest for testing

## The `./poe` Task Runner

QEN uses a wrapper script at `./poe` that intelligently runs Poe the Poet tasks:

```bash
./poe <task> [args...]
```

**How it works:**

1. Prefers `uv run poe` (modern, fast Python package manager)
2. Falls back to activated venv if available
3. Last resort: global Python installation

**Available Tasks** (from `pyproject.toml`):

| Task | Command | Purpose |
|------|---------|---------|
| `./poe test` | Run unit tests only | Run fast unit tests (use this first!) |
| `./poe test-unit` | Unit tests only | Fast tests with mocks |
| `./poe test-integration` | Integration tests only | Slow tests with real GitHub API |
| `./poe test-all` | All tests | Run both unit and integration tests |
| `./poe test-cov` | pytest with coverage | Generate coverage report |
| `./poe test-fast` | pytest -x | Stop on first failure |
| `./poe typecheck` | mypy src/ | Type checking only |
| `./poe lint` | ruff + format + mypy | Fix linting and format code |
| `./poe lint-check` | ruff check | Check without fixing |
| `./poe setup-hooks` | pre-commit install | Install git hooks manually |
| `./poe claude` | ln -sf AGENTS.md CLAUDE.md | Create CLAUDE.md symlink |
| `./poe version` | Show version | Display current version |
| `./poe version -b patch` | Bump patch | Increment version, commit |
| `./poe version --tag` | Create release tag | Tag v0.1.2, push |
| `./poe version --dev` | Create dev tag | Tag v0.1.2-dev.YYYYMMDD.HHMMSS |

**Why `./poe` instead of direct commands:**

- Ensures consistent environment (uv, venv, or global)
- Single entry point for all development tasks
- No need to remember `uv run` or activate venv

## Testing Philosophy

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
def test_parse_repo_url(mocker):
    """Unit test - mocks are OK here"""
    mock_clone = mocker.patch('subprocess.run')

    result = parse_repo_url("https://github.com/org/repo")
    assert result.org == "org"
    assert result.repo == "repo"
```

**Run unit tests:**
```bash
./poe test          # Default: runs only unit tests
./poe test-unit     # Explicit unit tests only
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

**Why This Matters:**

Past production bugs caused by mocks:
1. Mock data had wrong field names (`state` vs `status`)
2. Mock data omitted required fields (`mergeable`)
3. GitHub API changes not caught by mocks

**Integration tests validate our contract with GitHub. Never mock them.**

**Example:**
```python
@pytest.mark.integration
def test_pr_status_passing_checks(real_test_repo, unique_prefix, cleanup_branches):
    """Integration test - NO MOCKS"""
    # Create real branch
    branch = f"{unique_prefix}-passing"

    # Create real PR via gh CLI (not mocked!)
    pr_url = create_test_pr(real_test_repo, branch, "main")
    cleanup_branches.append(branch)

    # Wait for real GitHub Actions to complete
    time.sleep(40)

    # Test against REAL GitHub API
    result = subprocess.run(
        ["gh", "pr", "view", pr_url, "--json", "statusCheckRollup"],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True
    )

    pr_data = json.loads(result.stdout)
    assert len(pr_data["statusCheckRollup"]) > 0
```

**Run integration tests:**
```bash
# Requires GITHUB_TOKEN environment variable
export GITHUB_TOKEN="ghp_..."
./poe test-integration

# Or use gh CLI token
GITHUB_TOKEN=$(gh auth token) ./poe test-integration
```

#### IMPORTANT: Integration tests are NOT run in CI

- They create real PRs on data-yaml/qen-test
- They require write permissions to external repo
- They're expensive (API rate limits, 2+ min runtime)
- Run them manually when changing GitHub API integration code
- CI only runs fast unit tests

### Test Repository: data-yaml/qen-test

Integration tests use a dedicated repository at https://github.com/data-yaml/qen-test.

**GitHub Actions Workflows:**
- `always-pass.yml` - Always passes
- `always-fail.yml` - Fails for branches with "-failing-" in name
- `slow-check.yml` - Takes 35 seconds to complete

**Test Execution:**
1. Clone real repo to /tmp
2. Generate unique prefix: `test-{timestamp}-{uuid}`
3. Create test branches and PRs using real gh CLI
4. Run tests against REAL GitHub API
5. Cleanup branches after test

## Development Workflow

### 1. First Time Setup

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests (auto-installs git hooks on first run)
./poe test
```

### 2. Before Making Changes

```bash
# Always run tests first to ensure baseline
./poe test

# Check types if working on type-sensitive code
./poe typecheck
```

### 3. After Making Changes

```bash
# Fix formatting and check types
./poe lint

# Run tests
./poe test

# Or run with coverage to see what you're testing
./poe test-cov
```

### 4. Git Hooks (Automatic)

The project uses pre-commit hooks that run automatically:

**pre-commit hook** (before each commit):

- Linting with ruff
- Type checking with mypy

**pre-push hook** (before each push):

- Unit test suite (fast)

**Note:** Hooks are auto-installed when you run `./poe test` for the first time.

## Project Architecture

### Directory Structure

```tree
src/
├── qen/                    # Main CLI and project management
│   ├── cli.py              # Command-line interface entry point
│   ├── config.py           # QEN configuration management
│   ├── project.py          # Project creation and structure
│   ├── git_utils.py        # Git operations (branches, repos)
│   ├── repo_utils.py       # Repository URL parsing and cloning
│   ├── pyproject_utils.py  # pyproject.toml CRUD operations
│   └── commands/           # Command implementations
│       ├── init.py         # qen init [project]
│       └── add.py          # qen add <repo>
└── qenvy/                  # Reusable XDG-compliant config library
    ├── storage.py          # Profile-based config storage
    ├── base.py             # Core config management
    ├── formats.py          # TOML/JSON handlers
    └── types.py            # Type definitions

tests/                      # Test suite mirrors src/ structure
├── unit/                   # Unit tests (mocks OK)
└── integration/            # Integration tests (NO MOCKS)
scripts/                    # Build and version management scripts
```

### Key Concepts

**QEN (קֵן, "nest"):** A lightweight context for multi-repo development work.

**Meta Repository:** Central repository containing project directories (`proj/`)

**Project Structure:**

- Each project creates a dated git branch: `YYYY-MM-DD-project-name`
- Project directory: `proj/YYYY-MM-DD-project-name/`
- Contains: `README.md`, `pyproject.toml`, `repos/` (gitignored sub-repos)

**Configuration Locations:**

- Global: `$XDG_CONFIG_HOME/qen/config.toml`
- Per-project: `$XDG_CONFIG_HOME/qen/projects/<project>.toml`
- Project manifest: `proj/YYYY-MM-DD-project/pyproject.toml` (with `[tool.qen]`)

### CRITICAL: QEN Always Uses Stored Config State

- **QEN commands ALWAYS operate on the CURRENT CONFIG as stored in XDG directories**
- Commands DO NOT infer state from your current working directory
- Commands DO NOT scan your filesystem to discover projects
- The config files are the single source of truth for all project metadata
- Example: `qen status` operates on repos listed in the project config, not repos you happen to be in
- Example: `qen sh` changes to the PROJECT FOLDER as stored in config, not your current directory

## Code Style and Standards

### Type Checking

- **Strict mypy** enabled (`strict = true` in pyproject.toml)
- All functions must have type annotations
- Use `from typing import ...` for complex types

### Linting

- Ruff for linting and formatting (line-length = 100)
- Import sorting with isort via ruff
- Python 3.12+ features preferred

### Testing

- pytest for all tests
- Tests mirror `src/` structure
- Use `pytest-mock` for mocking **unit tests only**
- **NEVER mock integration tests**
- Aim for high coverage (use `./poe test-cov` to check)

### Git Conventions

- Descriptive commit messages
- Pre-commit hooks ensure quality (auto-run)
- Pre-push hooks run unit test suite

## Common Development Tasks

### Adding a New Command

1. Create command file: `src/qen/commands/mycommand.py`
2. Implement command logic with Click decorators
3. Register in `src/qen/cli.py`
4. Add unit tests: `tests/qen/commands/test_mycommand.py`
5. Add integration tests if needed: `tests/integration/test_mycommand_real.py`
6. Run: `./poe test`

### Working with Configuration

```python
from qen.config import QenConfig

# Load global config
config = QenConfig.load()

# Access settings
meta_path = config.meta_path
org = config.github_org
```

### Working with Projects

```python
from qen.project import find_project_root

# Find current project
project_root = find_project_root()
```

### Running Tests for Specific Files

```bash
# Run specific test file
./poe test-fast tests/qen/test_config.py

# Run specific integration test
pytest tests/integration/test_pr_status_real.py::test_pr_with_passing_checks -v

# Run with coverage for specific module
pytest tests/qen/test_config.py --cov=src/qen/config.py --cov-report=term
```

## Current Implementation Status

**Implemented:**

- `qen init` - Initialize qen configuration
- `qen init <project>` - Create new project with full structure
- `qen add <repo>` - Add sub-repositories with flexible URL parsing

**Planned (not yet implemented):**

- `qen status` - Show git status across all sub-repos
- `qen sync` - Push and pull sub-repos

## Design Philosophy

When implementing features, follow these principles:

1. **Context over configuration** - Minimal manifests, maximum clarity
2. **Always latest** - Work with current branches (checkpoints optional)
3. **Zero global state** - XDG-compliant configuration per project
4. **Human-readable** - Simple directory structures and TOML configs
5. **Intentionally small** - Create structure without dictating workflow

## Version Management

```bash
# Check current version
./poe version

# Bump patch version (0.1.2 -> 0.1.3), commit but don't push
./poe version -b patch

# Create release tag and push everything
./poe version --tag

# Create timestamped dev tag (e.g., v0.1.2-dev.20251205.143022)
./poe version --dev
```

## Troubleshooting

### Hooks not running?

```bash
./poe setup-hooks
```

### Type errors?

```bash
./poe typecheck
```

### Import errors?

```bash
uv pip install -e ".[dev]"
```

### Tests failing?

```bash
# Run with verbose output
pytest tests/ -vv

# Run single test
pytest tests/qen/test_config.py::test_specific_function -vv

# Run integration tests (requires GITHUB_TOKEN)
export GITHUB_TOKEN="ghp_..."
./poe test-integration
```

## Related Documentation

- [README.md](README.md) - User-facing documentation, philosophy, quick start
- `pyproject.toml` - All tool configuration, dependencies, and poe tasks
- `scripts/version.py` - Version management implementation
- `.pre-commit-config.yaml` - Git hooks configuration
- `spec/2-status/07-repo-qen-test.md` - Integration testing specification

## For AI Agents: Key Reminders

1. **Always use `./poe` for tasks** - Don't use `uv run poe` or `poetry run poe` directly
2. **Run `./poe test` before and after changes** - Hooks will catch issues
3. **Type hints are mandatory** - Strict mypy is enabled
4. **Keep it simple** - Follow the minimalist philosophy
5. **Test coverage matters** - Use `./poe test-cov` to verify
6. **XDG directories** - Use `platformdirs` for config paths
7. **TOML for config** - Use `tomli` and `tomli_w` for reading/writing
8. **NO MOCKS for integration tests** - Use real GitHub API only

---

*This file is intended for AI coding agents. For human-readable documentation, see [README.md](README.md).*
