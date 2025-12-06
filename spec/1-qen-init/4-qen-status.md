# Spec: qen status

## Overview

Show git status across all repositories in the current project. Provides a unified view of uncommitted changes, branch information, and sync status for both the meta repository and all sub-repositories defined in `pyproject.toml`.

## Command

### `qen status` - Show status across all repositories

**Behavior:**

1. Determine current project from `$XDG_CONFIG_HOME/qen/config.toml` (error if none)
2. Load project config from `$XDG_CONFIG_HOME/qen/projects/<proj-name>.toml`
3. Navigate to project folder in meta repo
4. Read `pyproject.toml` to get list of repositories from `[[tool.qen.repos]]`
5. For each repository (meta + all sub-repos):
   - Check if repo exists locally (skip with warning if not cloned)
   - Get current branch name
   - Check for uncommitted changes (modified, staged, untracked files)
   - Check sync status with remote (ahead/behind/diverged)
6. Display results in organized format

**Output format:**

```log
Project: my-project (2025-12-05-my-project)
Branch: 2025-12-05-my-project

Meta Repository
  Status: clean | modified | staged | untracked
  Branch: 2025-12-05-my-project
  Sync:   up-to-date | ahead 2 | behind 3 | diverged (ahead 2, behind 3)

Sub-repositories:

  repos/backend (github.com/myorg/backend)
    Status: clean
    Branch: develop
    Sync:   ahead 1 commit

  repos/frontend (github.com/myorg/frontend)
    Status: modified (3 files)
    Branch: main
    Sync:   behind 2 commits
    Modified files:
      - src/components/Header.tsx
      - src/App.tsx
      - package.json

  repos/api (github.com/myorg/api)
    Warning: Repository not cloned. Run 'qen clone' to initialize.
```

## Design Decisions

1. **Current project context**: Operates on the current project from config (no project argument)
2. **Comprehensive view**: Shows meta repo + all sub-repos in single view
3. **Git status semantics**: Mimics `git status --short` information hierarchy
4. **Skip missing repos**: Warn but don't error if a repo isn't cloned yet
5. **Fetch before status**: Optionally run `qen pull` to get accurate sync status (flag: `--pull`)
6. **Hierarchical display**: Meta repo first, then sub-repos in order from pyproject.toml
7. **File details**: Show modified file list for repos with changes (optional with `--verbose`)

## Status Information

### Repository Status Categories

| Status | Description |
|--------|-------------|
| `clean` | No uncommitted changes, working tree clean |
| `modified` | Unstaged changes in tracked files |
| `staged` | Changes staged for commit |
| `untracked` | Untracked files present |
| `mixed` | Combination of modified, staged, and/or untracked |

### Sync Status Categories

| Sync Status | Description |
|-------------|-------------|
| `up-to-date` | Local and remote branches match |
| `ahead N` | Local has N commits not pushed to remote |
| `behind N` | Remote has N commits not pulled locally |
| `diverged` | Local and remote have diverged (ahead X, behind Y) |
| `no remote` | No remote tracking branch configured |

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `--fetch` | Run `git fetch` on all repos before checking status | false |
| `--verbose` / `-v` | Show detailed file lists for modified repos | false |
| `--project <name>` | Override current project from config | current |
| `--meta-only` | Show only meta repository status | false |
| `--repos-only` | Show only sub-repository status | false |

## Implementation Details

### Git Commands Used

```bash
# Check repository status
git status --porcelain=v1

# Get current branch
git rev-parse --abbrev-ref HEAD

# Get sync status (requires fetch first)
git fetch  # optional, with --fetch flag
git rev-list --left-right --count HEAD...@{upstream}

# Check for uncommitted changes
git diff-index --quiet HEAD  # exit code 0 = clean, 1 = changes
```

### Status Detection Logic

```python
def get_repo_status(repo_path: Path) -> RepoStatus:
    """Get comprehensive status for a repository."""
    # Check if directory exists
    if not repo_path.exists():
        return RepoStatus(exists=False)

    # Get current branch
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path)

    # Check for changes using porcelain format
    porcelain = run_git_command(["status", "--porcelain=v1"], cwd=repo_path)

    modified = []
    staged = []
    untracked = []

    for line in porcelain.splitlines():
        status_code = line[:2]
        file_path = line[3:]

        if status_code[0] != ' ' and status_code[0] != '?':
            staged.append(file_path)
        if status_code[1] != ' ':
            modified.append(file_path)
        if status_code == '??':
            untracked.append(file_path)

    # Get sync status with remote
    try:
        # Get upstream branch
        upstream = run_git_command(
            ["rev-parse", "--abbrev-ref", "@{upstream}"],
            cwd=repo_path
        )

        # Count commits ahead/behind
        counts = run_git_command(
            ["rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
            cwd=repo_path
        )
        ahead, behind = counts.split()
        sync_status = SyncStatus(
            ahead=int(ahead),
            behind=int(behind),
            has_upstream=True
        )
    except GitError:
        # No upstream configured
        sync_status = SyncStatus(has_upstream=False)

    return RepoStatus(
        exists=True,
        branch=branch,
        modified=modified,
        staged=staged,
        untracked=untracked,
        sync=sync_status
    )
```

### pyproject.toml Reading

```python
def load_repos_from_pyproject(project_dir: Path) -> list[RepoConfig]:
    """Load repository configurations from pyproject.toml."""
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise StatusError(f"No pyproject.toml found in {project_dir}")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    # Get [tool.qen.repos] array
    try:
        repos = data["tool"]["qen"]["repos"]
    except KeyError:
        # No repos defined yet
        return []

    return [
        RepoConfig(
            url=repo["url"],
            branch=repo.get("branch", "main"),
            path=repo.get("path", infer_path_from_url(repo["url"]))
        )
        for repo in repos
    ]
```

## Error Conditions

- Current project not set: "No current project. Run 'qen init _project_' or use --project flag."
- Project config not found: "Project '<name>' not found in qen configuration."
- Not in meta repo: "Must be run from within meta repository or project directory."
- No pyproject.toml: "No pyproject.toml found in project directory. Initialize with 'qen init _project_'."
- Git command failure: "Git command failed: <error message>"

## Examples

### Example 1: Clean status

```bash
$ qen status
Project: auth-redesign (2025-12-05-auth-redesign)
Branch: 2025-12-05-auth-redesign

Meta Repository
  Status: clean
  Branch: 2025-12-05-auth-redesign
  Sync:   up-to-date

Sub-repositories:

  repos/api (github.com/myorg/api)
    Status: clean
    Branch: develop
    Sync:   up-to-date
```

### Example 2: Status with changes

```bash
$ qen status --verbose
Project: auth-redesign (2025-12-05-auth-redesign)
Branch: 2025-12-05-auth-redesign

Meta Repository
  Status: modified (2 files)
  Branch: 2025-12-05-auth-redesign
  Sync:   ahead 1 commit
  Modified files:
    - README.md
    - docs/architecture.md

Sub-repositories:

  repos/api (github.com/myorg/api)
    Status: mixed (3 modified, 2 staged, 1 untracked)
    Branch: develop
    Sync:   behind 2 commits
    Modified files:
      - src/handlers/auth.py
      - tests/test_auth.py
      - config/settings.py
    Staged files:
      - src/models/user.py
      - src/schemas/auth.py
    Untracked files:
      - temp_notes.txt
```

### Example 3: With fetch

```bash
$ qen status --fetch
Fetching updates...
  ✓ meta
  ✓ repos/api
  ✓ repos/frontend

Project: auth-redesign (2025-12-05-auth-redesign)
...
```

## Test Requirements

### Unit Tests

1. **Status detection tests** (`tests/test_status.py`):
   - Test detecting clean repository (no changes)
   - Test detecting modified files (unstaged changes)
   - Test detecting staged files
   - Test detecting untracked files
   - Test detecting mixed status (multiple types of changes)
   - Test handling non-existent repository paths
   - Test handling repositories without git initialization

2. **Sync status tests**:
   - Test detecting up-to-date sync status
   - Test detecting ahead commits (local ahead of remote)
   - Test detecting behind commits (local behind remote)
   - Test detecting diverged branches
   - Test handling no upstream branch configured
   - Test sync status with fetch vs without fetch

3. **pyproject.toml parsing tests**:
   - Test loading repos from valid pyproject.toml
   - Test handling missing pyproject.toml
   - Test handling malformed pyproject.toml
   - Test handling empty [tool.qen.repos] array
   - Test handling missing [tool.qen] section
   - Test parsing repo configs with all fields specified
   - Test parsing repo configs with defaults (missing branch/path)

4. **Output formatting tests**:
   - Test status output for clean repos
   - Test status output for modified repos
   - Test status output with --verbose flag
   - Test status output for missing repos
   - Test hierarchical display (meta first, then sub-repos)
   - Test summary statistics

5. **Flag handling tests**:
   - Test --fetch flag triggers git fetch
   - Test --verbose shows file lists
   - Test --project overrides current project
   - Test --meta-only filters to meta repo
   - Test --repos-only filters to sub-repos

6. **Error handling tests**:
   - Test error when no current project set
   - Test error when project config not found
   - Test error when not in meta repo
   - Test error when pyproject.toml missing
   - Test graceful handling of git command failures

### Integration Tests

1. **Full status workflow** (`tests/integration/test_status_integration.py`):
   - Create test project with qen init
   - Add test repositories to pyproject.toml
   - Clone repositories into repos/ directory
   - Make various changes (modify, stage, untrack files)
   - Run qen status and verify output
   - Test with --fetch flag
   - Test with --verbose flag

2. **Multi-repo scenarios**:
   - Test status with multiple sub-repos
   - Test status with some repos missing (not cloned)
   - Test status with repos in different states
   - Test status when meta repo has changes
   - Test status when sub-repos have changes

3. **Sync status accuracy**:
   - Create commits locally (ahead)
   - Create commits on remote (behind)
   - Create commits both places (diverged)
   - Test fetch updates sync status correctly

### Test Fixtures

Required test fixtures in `tests/fixtures/`:

1. **Mock git repositories**:
   - Clean repo (no changes)
   - Modified repo (unstaged changes)
   - Staged repo (staged changes)
   - Untracked repo (untracked files)
   - Mixed repo (combination)

2. **Mock pyproject.toml files**:
   - Valid with multiple repos
   - Valid with single repo
   - Valid with empty repos array
   - Missing [tool.qen] section
   - Malformed TOML

3. **Mock project configurations**:
   - Valid project config
   - Project with missing repos
   - Project with all repos cloned

### Test Coverage Requirements

- Minimum 80% code coverage for status command implementation
- 100% coverage for critical paths (status detection, sync status)
- Edge cases must have explicit test coverage
- Error conditions must have explicit test coverage

## Future Enhancements

1. **Color output**: Colorize status indicators (green=clean, yellow=modified, red=conflicts)
2. **Summary statistics**: Show totals (X repos clean, Y with changes, Z need sync)
3. **JSON output**: `--json` flag for machine-readable output
4. **Watch mode**: `--watch` flag to continuously monitor status
5. **Stash detection**: Show if repos have stashed changes
6. **Conflict detection**: Highlight repos with merge conflicts
7. **Commit info**: Show last commit message and author for each repo
