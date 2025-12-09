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

- **Git branch**: `YYMMDD-my-project` (e.g., `251203-readme-bootstrap`)
- **Project directory**: `proj/YYMMDD-my-project/`
- **Project files**:
  - `README.md` - Project documentation stub
  - `pyproject.toml` - Repository configuration with `[tool.qen]` section
  - `qen` - Executable wrapper for running qen commands in project context
  - `.gitignore` - Ignores repos/ directory
  - `repos/` - Gitignored directory for sub-repositories
  - `workspaces/` - IDE multi-repo configuration

### Using the Project Wrapper

Each project includes a `./qen` executable wrapper that automatically runs qen commands in that project's context:

```bash
cd proj/YYMMDD-my-project/
./qen status      # Works without specifying --proj
./qen add myrepo  # Automatically uses this project
./qen pr          # Launch PR manager for this project
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
- **Assigned an index** based on the order it was added (starting from 1)

Repositories are displayed with indices for easy reference:

```text
[1] myorg/repo1 (main)
[2] myorg/repo2 (feature)
[3] myorg/repo3 (dev)
```

### 5. Check Git Status

```bash
# Show git status across all repos (with indices)
uvx qen status

# Show detailed status with verbose output
uvx qen status -v

# Fetch latest changes before showing status
uvx qen status --fetch
```

The `status` command displays each repository with its index:

```text
Sub-repositories:

  [1] repos/main/repo1 (https://github.com/org/repo1)
    Status: Clean
    Branch: main
```

### 6. Work with Pull Requests

QEN v0.3.0 introduces an interactive TUI for PR management:

```bash
# Launch interactive PR manager (select repos, choose action)
uvx qen pr

# Pre-select repos by index, then choose action interactively
uvx qen pr 1 3

# Direct operations with flags
uvx qen pr 1 --action merge --strategy squash --yes
uvx qen pr 2 --action create --title "Add feature X"
uvx qen pr --action restack

# View PR information in git status
uvx qen status --pr
```

**Breaking Change:** The v0.3.0 release removed `qen pr status`, `qen pr stack`, and `qen pr restack` subcommands in favor of the interactive TUI. Use `qen status --pr` for read-only PR information.

#### PR TUI Operations

- **Merge**: Merge PR(s) with configurable strategy (squash/merge/rebase)
- **Close**: Close PR(s) without merging
- **Create**: Create new PR with title, body, and base branch
- **Restack**: Update stacked PRs to latest base branch
- **Stack View**: Display PR stack relationships

Repository indices ([1], [2], etc.) are used for quick reference:

```text
Index | Repo       | Branch      | PR#  | Status | Checks
1     | foo        | feat-auth   | 123  | open   | passing
2     | bar        | main        | -    | -      | -
3     | baz        | fix-bug     | 124  | open   | failing
```

### 7. Generate Editor Workspaces

Create editor workspace files that span all repositories in your project:

```bash
# Generate workspace files for all supported editors
uvx qen workspace

# Generate only VS Code workspace
uvx qen workspace --editor vscode

# Generate only Sublime Text workspace
uvx qen workspace --editor sublime

# Open the generated workspace
code workspaces/vscode.code-workspace
```

Workspace files are created in the `workspaces/` directory and include:

- Project root folder
- All sub-repositories
- PR numbers in folder names (when available)
- Sensible file exclusions (.git, **pycache**, etc.)

## Repository Indices

QEN automatically assigns **1-based indices** to repositories based on their order in the `[[tool.qen.repos]]` array in `pyproject.toml`. These indices:

- Start at 1 (not 0) for user-friendliness
- Are based on the order repositories appear in the configuration
- Are displayed in all repository listings (`qen status`, `qen pr status`, etc.)
- Provide a convenient way to reference repositories

The index reflects the position in the TOML array, making it easy to understand which repo you're referring to when working with multiple repositories.

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
