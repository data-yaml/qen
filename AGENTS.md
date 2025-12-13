# AGENTS.md - AI Agent Guide for QEN Development

This guide helps AI coding agents (like Claude Code, GitHub Copilot, Cursor, etc.) understand and work effectively with the QEN codebase.

## Quick Reference

**Primary Documentation:** See [README.md](README.md) for user-facing documentation, philosophy, and end-user guide.

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
| `./poe test-integration` | Integration tests only | Real GitHub API (auto-detects token) |
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

## Development Setup

### First Time Setup

```bash
# Clone the repository
git clone https://github.com/data-yaml/qen.git
cd qen

# IMPORTANT: DO NOT install qen globally during development
# Always use ./qen to run the CLI during development

# Run tests (auto-installs git hooks and dependencies on first run)
./poe test
```

### Git Hooks

The project uses `pre-commit` to maintain code quality:

- **pre-commit**: Runs linting (ruff) and type checking (mypy) before each commit
- **pre-push**: Runs the unit test suite before pushing

Hooks are **automatically installed** when you run `./poe test` for the first time.

To manually manage hooks:

```bash
# Install hooks explicitly
./poe setup-hooks

# Run pre-commit checks manually
uv run pre-commit run --all-files

# Run pre-push checks manually (including tests)
uv run pre-commit run --hook-stage pre-push --all-files
```

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
- ✅ **MUST test against <https://github.com/data-yaml/qen-test>**
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
# Auto-detects GitHub token from gh CLI or environment
./poe test-integration

# Token detection order:
# 1. GITHUB_TOKEN environment variable (if set)
# 2. gh auth token (if gh CLI is authenticated)

# You can also explicitly set the token:
GITHUB_TOKEN="ghp_..." ./poe test-integration
```

#### IMPORTANT: Integration tests are NOT run in CI

- They use standard reference PRs on data-yaml/qen-test
- They require read permissions to external repo
- They run in ~10-15 seconds using standard PRs
- Run them manually when changing GitHub API integration code
- CI only runs fast unit tests

### Test Repository: data-yaml/qen-test

Integration tests use a dedicated repository at <https://github.com/data-yaml/qen-test>.

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

### 1. Before Making Changes

```bash
# Always run tests first to ensure baseline
./poe test

# Check types if working on type-sensitive code
./poe typecheck
```

### 2. After Making Changes

```bash
# Fix formatting and check types
./poe lint

# Run tests
./poe test

# Or run with coverage to see what you're testing
./poe test-cov
```

### 3. Common Testing Commands

```bash
# Run specific test file
./poe test-fast tests/qen/test_config.py

# Run specific integration test
pytest tests/integration/test_pr_status.py::test_pr_with_passing_checks -v

# Run with coverage for specific module
pytest tests/qen/test_config.py --cov=src/qen/config.py --cov-report=term

# Stop on first failure
./poe test-fast

# Run all tests (unit + integration)
./poe test-all
```

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
│       ├── add.py          # qen add <repo>
│       ├── status.py       # qen status
│       └── pr.py           # qen pr [subcommand]
└── qenvy/                  # Reusable XDG-compliant config library
    ├── storage.py          # Profile-based config storage
    ├── base.py             # Core config management
    ├── formats.py          # TOML/JSON handlers
    └── types.py            # Type definitions

tests/                      # Test suite mirrors src/ structure
├── unit/                   # Unit tests (mocks OK)
│   ├── qen/                # Tests for qen module
│   └── qenvy/              # Tests for qenvy module
└── integration/            # Integration tests (NO MOCKS)
    ├── test_pull.py        # Integration tests using standard PRs
    └── test_pr_status.py   # Integration tests using standard PRs
scripts/                    # Build and version management scripts
    ├── version.py          # Version management
    └── integration_test.py # Integration test runner
```

### Key Concepts

**QEN (קֵן, "nest"):** A lightweight context for multi-repo development work.

**Meta Prime:** User's original `meta/` repository where project branches are manually reviewed and merged.

**Per-Project Meta:** QEN-managed `meta-{project}/` clones where each project lives in physical isolation. Each per-project meta:

- Is a full git clone of the meta prime's remote
- Lives in a sibling directory to meta prime (e.g., `~/GitHub/meta-myproj/`)
- Has its own project branch checked out (e.g., `251210-myproj`)
- Contains the project directory (`proj/YYMMDD-myproj/`) with its own `repos/` subdirectories
- Enables simultaneous multi-project work without branch-switching friction

**Architecture Benefits:**

1. **Physical isolation** - Each project is a separate directory with independent git state
2. **Simultaneous work** - Can work on multiple projects at once without conflicts
3. **No repos/ thrashing** - Sub-repos stay cloned and ready when switching projects
4. **IDE stability** - Language servers and file watchers don't get disrupted

**Project Structure:**

- Each project creates a per-project meta clone: `meta-{project}/`
- Inside the clone, a dated git branch: `YYMMDD-project-name`
- Project directory: `proj/YYMMDD-project-name/`
- Contains: `README.md`, `pyproject.toml`, `repos/` (gitignored sub-repos)

**Configuration Locations:**

QEN uses `platformdirs.user_config_dir("qen")` which resolves to:

- **macOS**: `~/Library/Application Support/qen/`
- **Linux**: `~/.config/qen/`
- **Windows**: `%LOCALAPPDATA%\qen\`

Structure:

- Global config: `<config-dir>/main/config.toml`
- Per-project configs: `<config-dir>/<project>/config.toml`
- Project manifest: `proj/YYMMDD-project/pyproject.toml` (with `[tool.qen]`)

**Global Configuration Schema:**

```toml
meta_path = "/Users/ernest/GitHub/meta"  # Path to meta prime
meta_remote = "git@github.com:org/meta.git"  # Remote URL for cloning per-project metas
meta_parent = "/Users/ernest/GitHub"  # Parent directory where per-project metas are cloned
meta_default_branch = "main"  # Default branch name (main or master)
org = "my-org"  # GitHub organization
current_project = "myproj"  # Currently active project (optional)
```

**Project Configuration Schema:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
repo = "/Users/ernest/GitHub/meta-myproj"  # Path to per-project meta clone
created = "2025-12-10T12:34:56Z"
```

**CLI Global Options (Runtime Overrides):**

The qen CLI provides global options that override configuration **for a single command execution only**:

```bash
qen [GLOBAL_OPTIONS] <command> [COMMAND_OPTIONS]
```

Available global options (defined in [cli.py](src/qen/cli.py:23-40)):

- `--config-dir PATH` - Override configuration directory (default: platform-specific via platformdirs)
- `--meta PATH` - Override meta repository path
- `--proj NAME` or `--project NAME` - Override current project name

**IMPORTANT:** These options must come **before** the subcommand, not after:

- ✅ **Correct:** `qen --meta ~/GitHub/meta config --global`
- ❌ **Wrong:** `qen config --global --meta ~/GitHub/meta`

**Runtime vs. Persistent Config:**

- Global options are **runtime overrides only** - they do not persist to disk
- To permanently modify global config, use `qen init` (reinitializes with new meta path and org)
- To switch current project persistently, use `qen config <project-name>`

Example use cases:

```bash
# Temporarily use different meta repo for one command
qen --meta /tmp/test-meta status

# Temporarily work with different project
qen --proj other-project status

# Override config dir for testing
qen --config-dir /tmp/qen-test init test-project
```

**Project pyproject.toml Schema:**

The `[tool.qen]` section in each project's pyproject.toml contains:

```toml
[tool.qen]
created = "2025-12-05T10:30:00Z"  # ISO8601 timestamp (required)
description = "Optional description"  # string (optional)

[[tool.qen.repos]]
# User-specified fields (set via qen add):
url = "https://github.com/org/repo"  # string (required)
branch = "main"  # string (optional, default: "main")
path = "repos/repo"  # string (optional, inferred from URL)

# Auto-generated metadata (updated by qen pull):
updated = "2025-12-05T14:23:45Z"  # ISO8601 timestamp of last pull
pr = 123  # int - PR number detected via gh CLI
pr_base = "main"  # string - PR base branch
pr_status = "open"  # string - PR state (open, closed, merged)
pr_checks = "passing"  # string - check status (passing, failing, pending, unknown)
issue = 456  # int - issue number extracted from branch name
```

**Field Reference:**

| Field | Type | Set By | Description |
|-------|------|--------|-------------|
| `url` | string | user (`qen add`) | Git clone URL (required) |
| `branch` | string | user (`qen add`) | Branch to track (default: "main") |
| `path` | string | user (`qen add`) | Local path in `repos/` (inferred from URL) |
| `updated` | ISO8601 | `qen pull` | Last pull timestamp |
| `pr` | int | `qen pull` | PR number from `gh` CLI |
| `pr_base` | string | `qen pull` | PR base branch |
| `pr_status` | string | `qen pull` | PR state (open/closed/merged) |
| `pr_checks` | string | `qen pull` | Check status (passing/failing/pending/unknown) |
| `issue` | int | `qen pull` | Issue number from branch name pattern |

**Repository Indices:**

Repositories are automatically assigned **1-based indices** based on their position in the `[[tool.qen.repos]]` array:

- Indices start at 1 (not 0) for user-friendliness
- Order is determined by position in the TOML array
- Displayed in all repository listings (`qen status`, `qen pr status`, etc.)
- Format: `[1]`, `[2]`, `[3]`, etc.
- Use `enumerate(repos, start=1)` to iterate with indices in Python code

Example in code:

```python
repos = load_repos_from_pyproject(project_dir)
for idx, repo in enumerate(repos, start=1):
    print(f"[{idx}] {repo.url}")
```

### Command Behavior with Per-Project Metas

**All QEN commands now operate on per-project meta clones:**

1. **qen init** - Extracts `meta_remote`, `meta_parent`, `meta_default_branch` from meta prime and stores in global config
2. **`qen init <project>`** - Clones from `meta_remote` to `{meta_parent}/meta-{project}/`, stores path in project config's `repo` field
3. **`qen add <repo>`** - Reads project config's `repo` field, clones sub-repo into `{repo}/proj/YYMMDD-project/repos/`
4. **qen status** - Reads project config's `repo` field, operates on repos in `{repo}/proj/YYMMDD-project/repos/`
5. **qen pr** - Same as status - all PR operations use the per-project meta's repos

**Key Implementation Note:**

- The `meta_path` field in global config still points to meta prime (for reference)
- The `repo` field in project config points to the per-project meta clone (where work happens)
- All project commands use the `repo` field, not `meta_path`

### CRITICAL: QEN Always Uses Stored Config State

- **QEN commands ALWAYS operate on the CURRENT CONFIG as stored in XDG directories**
- Commands DO NOT infer state from your current working directory
- Commands DO NOT scan your filesystem to discover projects
- The config files are the single source of truth for all project metadata
- Example: `qen status` operates on repos listed in the project config's `repo` field
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
4. Add unit tests: `tests/unit/qen/commands/test_mycommand.py`
5. Add integration tests if needed: `tests/integration/test_mycommand_real.py`
6. Run: `./poe test`

### Working with Configuration

```python
from qen.config import QenConfig

# Load global config
config = QenConfig.load()

# Access settings
meta_path = config.meta_path  # Meta prime path
meta_remote = config.meta_remote  # Remote URL for cloning
meta_parent = config.meta_parent  # Where to clone per-project metas
meta_default_branch = config.meta_default_branch  # main or master
org = config.github_org
```

### Working with Projects

```python
from qen.project import find_project_root

# Find current project
project_root = find_project_root()
```

### Working with Repository Indices

```python
from qen.pyproject_utils import load_repos_from_pyproject

# Load repositories
repos = load_repos_from_pyproject(project_dir)

# Iterate with 1-based indices
for idx, repo in enumerate(repos, start=1):
    # Display with index
    print(f"[{idx}] {repo.url}")

    # Access repo properties
    print(f"  Branch: {repo.branch}")
    print(f"  Path: {repo.path}")
```

## Current Implementation Status

**Implemented:**

- `qen init` - Initialize qen configuration with meta prime metadata extraction
- `qen init <project>` - Create new project with per-project meta clone
- `qen add <repo>` - Add sub-repositories to per-project meta
- `qen status` - Show git status across all sub-repos in per-project meta
- `qen pr status` - Show PR status for all repositories
- `qen pr stack` - Identify and display stacked PRs
- `qen pr restack` - Update stacked PRs to latest base branches

**Planned (not yet implemented):**

- `qen sync` - Push and pull sub-repos
- Additional PR management features

## Design Philosophy

When implementing features, follow these principles:

1. **Context over configuration** - Minimal manifests, maximum clarity
2. **Always latest** - Work with current branches (checkpoints optional)
3. **Zero global state** - XDG-compliant configuration per project
4. **Human-readable** - Simple directory structures and TOML configs
5. **Intentionally small** - Create structure without dictating workflow
6. **Physical isolation** - Per-project meta clones enable true multi-project workflows

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
# Install dependencies only (without global qen command)
uv pip install -e . --no-binary :all: || ./poe setup-hooks
```

### Tests failing?

```bash
# Run with verbose output
pytest tests/ -vv

# Run single test
pytest tests/qen/test_config.py::test_specific_function -vv

# Run integration tests (auto-detects token from gh CLI)
./poe test-integration
```

## Related Documentation

- [README.md](README.md) - User-facing documentation, philosophy, quick start
- `pyproject.toml` - All tool configuration, dependencies, and poe tasks
- `scripts/version.py` - Version management implementation
- `.pre-commit-config.yaml` - Git hooks configuration
- `spec/2-status/07-repo-qen-test.md` - Integration testing specification
- `spec/5-clone/02-qen-clone-design.md` - Per-project meta architecture design
- `spec/5-clone/03-qen-clone-spec.md` - Per-project meta implementation spec

## For AI Agents: Key Reminders

1. **Always use `./poe` for tasks** - Don't use `uv run poe` or `poetry run poe` directly
2. **Run `./poe test` before and after changes** - Hooks will catch issues
3. **Type hints are mandatory** - Strict mypy is enabled
4. **Keep it simple** - Follow the minimalist philosophy
5. **Test coverage matters** - Use `./poe test-cov` to verify
6. **XDG directories** - Use `platformdirs` for config paths
7. **TOML for config** - Use `tomli` and `tomli_w` for reading/writing
8. **NO MOCKS for integration tests** - Use real GitHub API only
9. **Repository indices** - Use `enumerate(repos, start=1)` for 1-based indexing
10. **Per-project metas** - All commands operate on per-project meta clones, not meta prime

## Markdown Best Practices

When writing markdown files (specs, documentation, etc.), always follow these rules:

1. **Make headings unique** - Never duplicate heading text, even at different levels
   - ❌ Bad: Multiple "Success Criteria" headings in the same file
   - ✅ Good: "Success Criteria for Init", "Success Criteria for Add Command"

2. **Use proper heading hierarchy** - Never use bold/emphasis as a heading substitute
   - ❌ Bad: `**Important Section**` as a section divider
   - ✅ Good: `### Important Section` with proper heading level

3. **Always specify language for code blocks** - Every fenced code block must have a language
   - ❌ Bad: ` ``` ` (no language specified)
   - ✅ Good: ` ```bash ` or ` ```python ` or ` ```text ` or ` ```log ` or ` ```tree `
   - Use `text` or `log` if no specific language applies

---

*This file is intended for AI coding agents. For human-readable documentation, see [README.md](README.md).*
