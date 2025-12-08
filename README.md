# QEN: A Developer Nest for Multi-Repo Innovation

**QEN** ("קֵן", *nest* in [Biblical Hebrew](https://biblehub.com/hebrew/7064.htm), pronounced 'kin')
is a lightweight tool for organizing multi-repository development work.

QEN gathers all context for a project (code, specs, artifacts, etc.) into a single managed folder inside a central `meta` repository.

## Quick Start

No installation needed! Use `uvx` to run QEN commands directly:

```bash
uvx qen --version
uvx qen --help
```

### 1. Initialize QEN

From within or near your `meta` repository:

```bash
uvx qen init
```

This finds your `meta` repo, extracts your organization from git remotes, and stores configuration in your system's CONFIG_HOME directory.

### 2. Create a Project

```bash
uvx qen init my-project
```

This uses the previously-discovered `meta` repository to create a project-specific:

- **Git branch**: `YYYY-MM-DD-my-project`
- **Project directory**: `proj/YYYY-MM-DD-my-project/`
- **Project files**:
  - `README.md` - Project documentation stub
  - `pyproject.toml` - Repository configuration with `[tool.qen]` section
  - `qen` - Executable wrapper for running qen commands in project context
  - `.gitignore` - Ignores repos/ directory
  - `repos/` - Gitignored directory for sub-repositories

### Using the Project Wrapper

Each project includes a `./qen` executable wrapper that automatically runs qen commands in that project's context:

```bash
cd proj/YYYY-MM-DD-my-project/
./qen status      # Works without specifying --proj
./qen add myrepo  # Automatically uses this project
./qen pr status   # Check PR status for this project
```

The wrapper is especially useful when you have multiple projects, as it eliminates the need to specify `--proj` or remember which project you're in

### 3. Manage Configuration

Configuration is stored in your system's CONFIG_HOME directory and tracks:

- Your meta repository location
- Your GitHub organization
- Current active project
- Per-project settings (branch name, project path, etc.)

To view or modify, use the `config` command:

```bash
# Show current project
uvx qen config

# List all projects
uvx qen config --list

# Switch to a different project
uvx qen config --switch other-project

# Show global configuration
uvx qen config --global
```

### 4. Add Repositories

```bash
# Add a repository using different formats
uvx qen add https://github.com/myorg/myrepo    # Full URL
uvx qen add myorg/myrepo                       # org/repo format
uvx qen add myrepo                             # Uses org from config

# Add with specific branch
uvx qen add myorg/myrepo --branch develop

# Add with custom path
uvx qen add myorg/myrepo --path repos/custom-name
```

The repository will be:

- Cloned to `repos/myrepo/`
- Added to `pyproject.toml` in the `[[tool.qen.repos]]` section
- Tracked with its URL, branch, and local path

### 5. Check Git Status

```bash
# Show git status across all repos
uvx qen status

# Show detailed status with verbose output
uvx qen status -v

# Fetch latest changes before showing status
uvx qen status --fetch
```

### 6. Work with Pull Requests

```bash
# Show PR status for all repositories
uvx qen pr status

# Show detailed PR information
uvx qen pr status -v

# Identify and display stacked PRs
uvx qen pr stack

# Update stacked PRs (rebase child PRs on parent PRs)
uvx qen pr restack

# Preview restack changes without making them
uvx qen pr restack --dry-run
```

## Requirements

- Python 3.12 or higher
- Git
- GitHub CLI (`gh`) for PR commands

## Contributing

QEN is open source and contributions are welcome! For developer documentation, see [AGENTS.md](AGENTS.md).

## License

MIT License - see LICENSE file for details.

## Links

- **Homepage**: <https://github.com/data-yaml/qen>
- **Issues**: <https://github.com/data-yaml/qen/issues>
- **PyPI**: <https://pypi.org/project/qen/>
