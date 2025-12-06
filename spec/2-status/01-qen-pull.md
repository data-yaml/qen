# qen pull - Repository Synchronization and Status

## Overview

`qen pull` retrieves current state information and synchronizes all sub-repositories within a QEN project. It updates local repositories with remote changes and captures comprehensive metadata about each repository's state.

## Command Behavior

### Basic Usage

```bash
qen pull                    # Fetch and merge all repos (git pull)
qen pull --fetch-only       # Fetch only, don't merge (git fetch)
```

**Note:** `--fetch-only` updates remote tracking branches without modifying your working directory. Useful for checking what's new without changing local files.

### What It Does

1. **Locates current project** - Uses default project from qen config
2. **Discovers all sub-repositories** - Reads `pyproject.toml` to find repos in `[tool.qen.repos]`
3. **Fetches remote state** - Retrieves latest information from each remote
4. **Updates local branches** - Pulls changes into current branch (unless `--fetch-only`)
5. **Updates PR/issue metadata** - Writes PR/issue associations to `pyproject.toml` if detected
6. **Displays summary** - Shows what changed across all repositories with current state

## Repository Metadata

### Committed Metadata (pyproject.toml)

Each repository stores minimal, essential information. This metadata is committed to git and should be human-readable and editable.

```toml
[tool.qen.repos.example-repo]
url = "https://github.com/org/example-repo"
branch = "feature/my-work"              # Current working branch
added = "2025-12-05T14:30:00Z"          # When added to project
updated = "2025-12-05T15:45:00Z"    # Last successful pull
pr = 123                                # Optional: PR number if tracking
pr_base = "main"                        # Optional: PR target branch
issue = 456                             # Optional: Issue number if tracking
```

**Not stored in pyproject.toml:**

- Git state (commits, ahead/behind, dirty status)
- GitHub state (PR status, checks, mergeable)
- Working directory state (modified files, stashes)

## Output Format

### Summary View

```log
Pulling project: feature-work

📦 example-repo (feature/my-work)
   ✓ Pulled 3 commits from origin/feature/my-work
   📋 PR #123 (open) → main
   ✓ Checks passing

📦 another-repo (main)
   ⚠ 2 commits behind origin/main
   ⚠ 1 uncommitted change
   • No PR

📦 third-repo (bugfix/issue-456)
   ✗ Merge conflicts detected
   📋 PR #789 (draft) → develop
   ⏳ Checks pending

Summary:
  3 repositories processed
  1 needs attention (conflicts)
  2 PRs tracked (1 open, 1 draft)
```

## Error Handling

### Scenarios to Handle

1. **Remote unreachable** - Mark metadata as stale, continue with other repos
2. **Authentication required** - Prompt or use credential helper
3. **Merge conflicts** - Mark repo, don't fail entire operation
4. **Detached HEAD** - Note state, don't attempt pull
5. **No remote configured** - Skip, note in output
6. **GitHub API unavailable** - Skip PR/issue metadata, continue with git operations

## Integration Points

### With Other Commands

- `qen add` - After cloning a repo, calls `qen pull` to initialize metadata and detect PR/issue associations
- `qen status` - Reads local metadata
- `qen sync` - Uses metadata to determine push/pull needs
- `qen init` - Sets up metadata schema in project manifest

### External Tools

- **gh CLI** - Required for PR/issue information. If not installed, GitHub features are skipped with a warning.
- **git** - Required. All git operations via subprocess calls to git CLI.

## Configuration

### Project-Level Settings (Optional)

```toml
[tool.qen.pull]
auto_merge = true                        # Auto-merge if fast-forward possible
parallel = true                          # Pull repos in parallel
max_workers = 4                          # Parallel worker count
```

### Global Settings (Optional)

```toml
[pull]
github_cli = "gh"                        # Path to GitHub CLI (default: "gh")
```

## Success Criteria

### Must Accomplish

1. **Pull all repos** - Successfully fetch and merge for each sub-repository
2. **Query current state** - Show live git/GitHub status for each repository
3. **Update minimal metadata** - Write only essential info to `pyproject.toml`
4. **Handle failures gracefully** - One repo failure doesn't stop others
5. **Show clear summary** - User understands what happened across all repos

### Should Accomplish

1. **Parallel execution** - Pull multiple repos concurrently
2. **GitHub integration** - Show PR/issue data from `gh` CLI when available
3. **Conflict detection** - Identify and report merge conflicts

### Nice to Have

1. **Progress indication** - Show progress for long-running operations
2. **Selective pull** - Pull specific repos only
3. **Branch suggestions** - Suggest switching branches based on PR state

## Non-Goals

- **Not a git wrapper** - Don't replicate all git pull options
- **Not CI/CD** - Don't run builds or tests
- **Not a merge tool** - Don't resolve conflicts automatically
- **Not a GitHub client** - Don't manage PRs/issues, just read their state

## Design Decisions

1. **Multiple remotes** - Only track `origin`. Other remotes are out of scope.
2. **Submodules** - Ignore submodules within sub-repositories. Not our concern.
3. **PR/issue detection** - Auto-detect on pull by checking current branch against `gh` CLI.
4. **Mono-repos** - Each sub-repo is treated as a single unit. Internal structure is not our problem.

## Related Specifications

- [4-qen-status.md](../1-qen-init/4-qen-status.md) - Status display using this metadata
- [5-qen-sync.md](../1-qen-init/5-qen-sync.md) - Push operations using this metadata
