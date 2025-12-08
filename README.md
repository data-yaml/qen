# QEN: A Developer Nest for Multi-Repo Innovation

**QEN** ("קֵן", *nest* in [Biblical Hebrew](https://biblehub.com/hebrew/7064.htm)) is a tiny, extensible tool for organizing multi-repository development work. A "qen" is a lightweight context—a safe, structured "nest"—where complex feature development can incubate across multiple repos.

QEN gathers all context for a project (code, specs, artifacts, etc.) into a single managed folder inside a central `meta` repository.

## Quick Start

### 1. Initialize qen

From within or near your `meta` repository:

```bash
qen init
```

This finds the `meta` repo, extracts your organization from git remotes, and stores configuration in `$XDG_CONFIG_HOME/qen/config.toml`.

### 2. Create a project

```bash
qen init my-project
```

This creates:

- Git branch: `YYYY-MM-DD-my-project`
- Project directory: `proj/YYYY-MM-DD-my-project/`
- Configuration files:
  - `README.md` - Project documentation stub
  - `pyproject.toml` - Repository configuration with `[tool.qen]` section
  - `repos/` - Gitignored directory for sub-repositories
- User config: `$XDG_CONFIG_HOME/qen/projects/my-project.toml`

The project is automatically set as your current project.

### 3. Add repositories

```bash
cd meta/proj/YYYY-MM-DD-my-project/

# Add a repository using different formats
qen add https://github.com/myorg/myrepo    # Full URL
qen add myorg/myrepo                       # org/repo format
qen add myrepo                             # Uses org from config

# Add with specific branch
qen add myorg/myrepo --branch develop

# Add with custom path
qen add myorg/myrepo --path repos/custom-name
```

The repository will be:

- Cloned to `repos/myrepo/`
- Added to `pyproject.toml` in the `[[tool.qen.repos]]` section
- Tracked with its URL, branch, and local path

### 4. Work with pull requests

```bash
# Show PR status for all repositories
qen pr status

# Show detailed PR information
qen pr status -v

# Identify and display stacked PRs
qen pr stack

# Update stacked PRs (rebase child PRs on parent PRs)
qen pr restack

# Preview restack changes without making them
qen pr restack --dry-run
```

### 5. Check git status

```bash
# Show git status across all repos
qen status

# Show detailed status with verbose output
qen status -v

# Fetch latest changes before showing status
qen status --fetch
```

## Current Status

**Implemented:**

- `qen init` - Initialize qen configuration
- `qen init <project>` - Create new project with branch, directory structure, and configuration
- `qen add` - Add sub-repositories to current project with flexible URL formats
- `qen status` - Show git status across all sub-repos
- `qen pr status` - Show PR status for all repositories
- `qen pr stack` - Identify and display stacked PRs
- `qen pr restack` - Update stacked PRs to latest base branches

**Planned:**

- `qen sync` - Push and pull sub-repos
- Additional PR management features

## Philosophy

**QEN is intentionally small.** It creates structure without dictating workflow.

Design principles:

- **Context over configuration** - Minimal manifests, maximum clarity
- **Always latest** - Work with current branches (checkpoints optional)
- **Zero global state** - XDG-compliant configuration per project
- **Human-readable** - Simple directory structures and TOML configs

## Development

### Setup

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Git hooks are automatically installed when you run tests
./poe test
```

### Git Hooks

The project uses `pre-commit` to maintain code quality:

- **pre-commit**: Runs linting (ruff) and type checking (mypy) before each commit
- **pre-push**: Runs the full test suite before pushing

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

### Testing

```bash
# Run tests
./poe test

# Run tests with coverage
./poe test-cov

# Type checking
./poe typecheck

# Lint and format
./poe lint

# Version management
./poe version                    # Show current version
./poe version -b patch           # Bump patch, commit (no push)
./poe version --tag              # Create release tag v0.1.2, push everything
./poe version --dev              # Create timestamped dev tag v0.1.2-dev.YYYYMMDD.HHMMSS, push
```

### Project Structure

```text
src/
├── qen/          # Main CLI and project management
│   ├── cli.py              # Command-line interface
│   ├── config.py           # QEN configuration management
│   ├── project.py          # Project creation and structure
│   ├── git_utils.py        # Git operations
│   ├── repo_utils.py       # Repository URL parsing and cloning
│   ├── pyproject_utils.py  # pyproject.toml management
│   └── commands/
│       ├── init.py         # Init command implementation
│       └── add.py          # Add command implementation
└── qenvy/        # Reusable XDG-compliant config library
    ├── storage.py          # Profile-based config storage
    ├── base.py             # Core config management
    ├── formats.py          # TOML/JSON handlers
    └── types.py            # Type definitions
```

## License

MIT License
