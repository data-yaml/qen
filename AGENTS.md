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
| `./poe test` | Auto-installs hooks + runs pytest | Run test suite (use this first!) |
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

- Full test suite

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
- Use `pytest-mock` for mocking
- Aim for high coverage (use `./poe test-cov` to check)

### Git Conventions

- Descriptive commit messages
- Pre-commit hooks ensure quality (auto-run)
- Pre-push hooks run full test suite

## Common Development Tasks

### Adding a New Command

1. Create command file: `src/qen/commands/mycommand.py`
2. Implement command logic with Click decorators
3. Register in `src/qen/cli.py`
4. Add tests: `tests/qen/commands/test_mycommand.py`
5. Run: `./poe test`

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
```

## Related Documentation

- [README.md](README.md) - User-facing documentation, philosophy, quick start
- `pyproject.toml` - All tool configuration, dependencies, and poe tasks
- `scripts/version.py` - Version management implementation
- `.pre-commit-config.yaml` - Git hooks configuration

## For AI Agents: Key Reminders

1. **Always use `./poe` for tasks** - Don't use `uv run poe` or `poetry run poe` directly
2. **Run `./poe test` before and after changes** - Hooks will catch issues
3. **Type hints are mandatory** - Strict mypy is enabled
4. **Keep it simple** - Follow the minimalist philosophy
5. **Test coverage matters** - Use `./poe test-cov` to verify
6. **XDG directories** - Use `platformdirs` for config paths
7. **TOML for config** - Use `tomli` and `tomli_w` for reading/writing

---

*This file is intended for AI coding agents. For human-readable documentation, see [README.md](README.md).*
