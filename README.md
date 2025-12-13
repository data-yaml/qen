# QEN: A Developer Nest for Multi-Repo Innovation

**QEN** ("קֵן", *nest* in [Biblical Hebrew](https://biblehub.com/hebrew/7064.htm), pronounced 'kin')
is a lightweight tool for organizing multi-repository development work.

QEN gathers all context for a project (code, specs, artifacts, etc.) into a single managed folder inside a per-project meta repository clone.

## Architecture Overview

QEN uses a **per-project meta architecture** that provides physical isolation between projects:

### Meta Prime vs Per-Project Metas

- **Meta Prime** (`meta/`) - Your original meta repository where you manually review and merge project branches
- **Per-Project Metas** (`meta-{project}/`) - QEN-managed clones where each project lives in physical isolation

This architecture enables:

1. **Simultaneous multi-project work** - Each project is a separate directory with independent git state
2. **No branch-switching friction** - Your IDE, language servers, and tools stay stable
3. **Physical isolation** - Changes in one project never accidentally affect another
4. **Standard git workflows** - All per-project metas push to the same remote for review

### Directory Structure

```text
~/GitHub/                           # (or wherever meta prime is found)
├── meta/                           # Meta prime (user-controlled)
│   ├── main branch                 # Manually review/merge here
│   └── .git/                       # Original git database
├── meta-myproj/                    # Per-project meta (qen-managed)
│   ├── branch: 251210-myproj       # Project branch checked out
│   ├── proj/251210-myproj/         # Project directory
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   ├── qen                     # Project wrapper script
│   │   ├── workspaces/             # IDE configuration
│   │   └── repos/                  # Sub-repos cloned here
│   └── .git/                       # Independent git database
└── meta-other/                     # Another per-project meta
    ├── branch: 251209-other        # Different branch
    └── proj/251209-other/
        └── repos/                  # Different sub-repos
```

**Key Insight:** Each active project gets its own physical clone of the meta repository, enabling true parallel development without workspace disruption.

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

This finds your meta prime repository, extracts metadata (remote URL, parent directory, default branch), extracts your organization from git remotes, and stores configuration in your system's standard config directory (via platformdirs: `~/Library/Application Support/qen` on macOS, `~/.config/qen` on Linux).

### 2. Create a Project

```bash
uvx qen init my-project
```

This clones your meta prime repository to create a per-project meta clone with:

- **Physical location**: `meta-my-project/` (sibling to meta prime)
- **Git branch**: `YYMMDD-my-project` (e.g., `251203-readme-bootstrap`)
- **Project directory**: `proj/YYMMDD-my-project/`
- **Project files**:
  - `README.md` - Project documentation stub
  - `pyproject.toml` - Repository configuration with `[tool.qen]` section
  - `qen` - Executable wrapper for running qen commands in project context
  - `.gitignore` - Ignores repos/ directory
  - `repos/` - Gitignored directory for sub-repositories
  - `workspaces/` - IDE multi-repo configuration

**Note:** `qen init` does NOT automatically push the branch to the remote. You control when to push using standard git commands.

### Discovery-First Project Setup

`qen init` uses a **discovery-first approach** that works for both new and existing projects:

**First Machine (Project Creator):**

```bash
uvx qen init myproject
# Creates new per-project meta clone
# Creates new branch: 251210-myproject
# You push manually when ready
```

**Second Machine (Project Collaborator):**

```bash
uvx qen init myproject
# Discovers existing remote branch 251210-myproject
# Clones per-project meta with that branch
# Pulls latest changes
# You're ready to work!
```

The command automatically:

1. **Checks for remote branches** matching the project name
2. **Checks for local config** in your system's config directory (platformdirs handles the location)
3. **Checks for local repo** at `meta-{project}/`
4. **Shows you what exists** and what will happen
5. **Prompts for confirmation** before taking action

This means `qen init myproject` is idempotent and safe to run multiple times. It will:

- **Create new** if nothing exists
- **Clone existing** if remote branch exists
- **Do nothing** if already configured locally
- **Prompt for choice** if multiple remote branches match

**Fully-Qualified Project Names:**

You can also specify exact branch names to avoid ambiguity:

```bash
# Short name (auto-generates YYMMDD prefix)
uvx qen init myproject          # Uses 251210-myproject (or finds existing)

# Fully-qualified name (use exact branch)
uvx qen init 251210-myproject   # Uses exactly 251210-myproject
```

### Using the Project Wrapper

Each project includes a `./qen` executable wrapper that automatically runs qen commands in that project's context:

```bash
cd meta-my-project/proj/YYMMDD-my-project/
./qen status      # Works without specifying --proj
./qen add myrepo  # Automatically uses this project
./qen pr          # Launch PR manager for this project
```

The wrapper is especially useful when you have multiple projects, as it eliminates the need to specify `--proj` or remember which project you're in.

### Workflow Benefits

**Without per-project metas (old model):**

- Switch branch → lose repos/ state → re-clone everything
- IDE confused by sudden directory changes
- Can't work on two projects at same time

**With per-project metas (new model):**

- Each project isolated in `meta-{project}/` directory
- All repos stay cloned and ready
- IDE stays stable
- Work on multiple projects simultaneously

### 3. Manage Configuration

Configuration is stored in your system's standard config directory (via platformdirs: `~/Library/Application Support/qen` on macOS, `~/.config/qen` on Linux) and tracks:

- Your meta prime location and metadata (remote URL, parent directory, default branch)
- Your GitHub organization
- Current active project
- Per-project settings (branch name, project path, per-project meta location)

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

- Cloned to `repos/myrepo/` (inside the per-project meta)
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

### 8. Delete Projects

Remove projects with safety checks and warnings:

```bash
# Delete project (config + local repo)
uvx qen del myproject

# Delete only config, keep local repo
uvx qen del myproject --config-only

# Delete only local repo, keep config
uvx qen del myproject --repo-only

# Delete everything including remote branch (WARNING)
uvx qen del myproject --remote

# Skip confirmation prompts
uvx qen del myproject --yes
```

The `del` command includes safety checks:

- **Uncommitted changes detection** - Warns if files are modified
- **Unpushed commits detection** - Warns if commits haven't been pushed
- **Remote branch protection** - Never deletes remote by default
- **Interactive confirmation** - Shows what will be deleted before proceeding

Example output:

```text
Delete project 'myproject':
  ✓ Config: <config-dir>/myproject/config.toml
  ✓ Repo: ~/GitHub/meta-myproject (branch: 251210-myproject)
  ✗ Remote: origin/251210-myproject (will NOT be deleted)

⚠️  Warning: Uncommitted changes:
  • 3 uncommitted file(s)
  • 2 unpushed commit(s)

Delete config and repo? [y/N]:
```

**Important:** The `--remote` flag is dangerous and requires explicit confirmation. Use it only when you're certain you want to delete the remote branch permanently.

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

## Migration from v0.3.x

QEN v0.4.0 introduces a **breaking change** with the new per-project meta architecture. If you need the old single-branch model, use:

```bash
# Use the old version
uvx qen@0.3.0 status
```

To migrate to the new architecture:

1. Finish or archive your current projects
2. Delete old project configurations (location varies by OS - use `qen config --list` to find them)
3. Reinitialize: `uvx qen init`
4. Recreate projects: `uvx qen init my-project`

See the [Migration Guide](spec/5-clone/04-migration-guide.md) for details.

## Contributing

QEN is open source and contributions are welcome! For developer documentation, see [AGENTS.md](AGENTS.md).

## License

MIT License - see LICENSE file for details.

## Links

- **Homepage**: <https://github.com/data-yaml/qen>
- **Issues**: <https://github.com/data-yaml/qen/issues>
- **PyPI**: <https://pypi.org/project/qen/>
