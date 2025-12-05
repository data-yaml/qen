# Spec: qen sync

## Overview

Synchronize all repositories in the current project by pulling changes from remotes and optionally pushing local commits. Operates on the meta repository and all sub-repositories defined in `pyproject.toml`.

## Command

### `qen sync` - Synchronize all repositories

**Behavior:**

1. Determine current project from `$XDG_CONFIG_HOME/qen/config.toml` (error if none)
2. Load project config from `$XDG_CONFIG_HOME/qen/projects/<proj-name>.toml`
3. Navigate to project folder in meta repo
4. Read `pyproject.toml` to get list of repositories from `[[tool.qen.repos]]`
5. For each repository (meta + all sub-repos):
   - Check if repo exists locally (skip with warning if not cloned)
   - Check for uncommitted changes (error if found and not using `--force-pull`)
   - Fetch updates from remote
   - Pull changes from remote branch
   - Optionally push local commits if `--push` flag is set
6. Display results with summary

**Default mode**: Pull only (safe, non-destructive)

**With `--push`**: Pull then push (bidirectional sync)

## Design Decisions

1. **Pull-first safety**: Default is pull-only to prevent accidental pushes
2. **Uncommitted changes check**: Error if uncommitted changes exist (prevents data loss)
3. **Force pull option**: Allow pulling with uncommitted changes (stash or `--force-pull`)
4. **Sequential execution**: Process repos one at a time for clear error handling
5. **Continue on error**: Keep syncing other repos even if one fails (with summary)
6. **Dry run mode**: `--dry-run` shows what would be done without making changes
7. **Meta repo first**: Always sync meta repo first, then sub-repos

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `--push` | Push local commits after pulling | false |
| `--force-pull` | Pull even with uncommitted changes (dangerous) | false |
| `--dry-run` | Show what would be synced without making changes | false |
| `--project <name>` | Override current project from config | current |
| `--repos-only` | Sync only sub-repositories, skip meta | false |
| `--repo <name>` | Sync only specific repository by path (e.g., "repos/api") | all |
| `--prune` | Prune remote-tracking branches during fetch | false |
| `--rebase` | Use rebase instead of merge when pulling | false |

## Sync Operations

### Pull Operation

```bash
# Standard pull
git fetch origin
git pull origin <branch>

# With rebase
git pull --rebase origin <branch>

# Force pull (with uncommitted changes) - NOT RECOMMENDED
git stash push -m "qen sync auto-stash"
git pull origin <branch>
git stash pop  # Only if stash was successful
```

### Push Operation

```bash
# Push to remote
git push origin <branch>

# Push with lease (safer, prevents overwriting others' work)
git push --force-with-lease origin <branch>
```

## Output Format

### Standard output (pull only)

```
Syncing project: my-project (2025-12-05-my-project)

Meta Repository (2025-12-05-my-project)
  Fetching... ✓
  Pulling...  ✓ (3 commits pulled)
  Status:     up-to-date

Sub-repositories:

  repos/backend (github.com/myorg/backend)
    Fetching... ✓
    Pulling...  ✓ (1 commit pulled)
    Status:     up-to-date

  repos/frontend (github.com/myorg/frontend)
    Fetching... ✓
    Pulling...  ✓ (already up-to-date)
    Status:     up-to-date

Summary:
  ✓ 3 repositories synced
  ↓ 4 commits pulled
  • 0 repositories skipped
```

### With push

```
Syncing project: my-project (2025-12-05-my-project)

Meta Repository (2025-12-05-my-project)
  Fetching... ✓
  Pulling...  ✓ (already up-to-date)
  Pushing...  ✓ (2 commits pushed)
  Status:     synchronized

Sub-repositories:

  repos/backend (github.com/myorg/backend)
    Fetching... ✓
    Pulling...  ✓ (1 commit pulled)
    Pushing...  ✓ (3 commits pushed)
    Status:     synchronized

Summary:
  ✓ 2 repositories synced
  ↓ 1 commit pulled
  ↑ 5 commits pushed
  • 0 repositories skipped
```

### Error cases

```
Syncing project: my-project (2025-12-05-my-project)

Meta Repository (2025-12-05-my-project)
  Fetching... ✓
  Pulling...  ✗ ERROR: Uncommitted changes detected
    Use --force-pull to pull anyway (will stash changes)
    Or commit/stash changes manually
  Status:     sync failed

Sub-repositories:

  repos/backend (github.com/myorg/backend)
    Fetching... ✓
    Pulling...  ✓ (1 commit pulled)
    Status:     up-to-date

  repos/api (github.com/myorg/api)
    Warning:    Repository not cloned. Run 'qen clone' to initialize.
    Status:     skipped

Summary:
  ✓ 1 repository synced
  ✗ 1 repository failed (meta)
  • 1 repository skipped (repos/api)
```

## Implementation Details

### Uncommitted Changes Detection

```python
def has_uncommitted_changes(repo_path: Path) -> bool:
    """Check if repository has uncommitted changes."""
    try:
        # Check for changes
        result = run_git_command(
            ["diff-index", "--quiet", "HEAD"],
            cwd=repo_path,
            check=False  # Don't raise on exit code 1
        )
        # Exit code 0 = no changes, 1 = changes
        if result.returncode == 1:
            return True

        # Also check for untracked files
        status = run_git_command(
            ["status", "--porcelain"],
            cwd=repo_path
        )
        return len(status.strip()) > 0
    except GitError:
        return False
```

### Pull Operation

```python
def pull_repo(
    repo_path: Path,
    branch: str,
    rebase: bool = False,
    force: bool = False
) -> PullResult:
    """Pull changes from remote branch."""

    # Check for uncommitted changes
    if has_uncommitted_changes(repo_path) and not force:
        raise SyncError(
            "Uncommitted changes detected. "
            "Commit, stash, or use --force-pull."
        )

    # Stash if force pull requested
    stashed = False
    if force and has_uncommitted_changes(repo_path):
        run_git_command(
            ["stash", "push", "-m", "qen sync auto-stash"],
            cwd=repo_path
        )
        stashed = True

    try:
        # Fetch first
        run_git_command(["fetch", "origin"], cwd=repo_path)

        # Get commits before pull
        before = run_git_command(
            ["rev-parse", "HEAD"],
            cwd=repo_path
        )

        # Pull with appropriate strategy
        if rebase:
            run_git_command(
                ["pull", "--rebase", "origin", branch],
                cwd=repo_path
            )
        else:
            run_git_command(
                ["pull", "origin", branch],
                cwd=repo_path
            )

        # Get commits after pull
        after = run_git_command(
            ["rev-parse", "HEAD"],
            cwd=repo_path
        )

        # Count commits pulled
        if before != after:
            count = run_git_command(
                ["rev-list", "--count", f"{before}..{after}"],
                cwd=repo_path
            )
            commits_pulled = int(count)
        else:
            commits_pulled = 0

        # Pop stash if we stashed
        if stashed:
            try:
                run_git_command(["stash", "pop"], cwd=repo_path)
            except GitError as e:
                # Stash pop failed (conflicts?)
                raise SyncError(
                    f"Stash pop failed after pull. "
                    f"Resolve conflicts manually: {e}"
                )

        return PullResult(
            success=True,
            commits_pulled=commits_pulled,
            already_up_to_date=(commits_pulled == 0)
        )

    except GitError as e:
        # If we stashed, try to recover
        if stashed:
            try:
                # Reset to before pull
                run_git_command(["reset", "--hard", before], cwd=repo_path)
                run_git_command(["stash", "pop"], cwd=repo_path)
            except:
                pass  # Best effort recovery

        raise SyncError(f"Pull failed: {e}")
```

### Push Operation

```python
def push_repo(repo_path: Path, branch: str, force_with_lease: bool = True) -> PushResult:
    """Push local commits to remote branch."""

    # Check if there's anything to push
    try:
        # Get commit count ahead of remote
        counts = run_git_command(
            ["rev-list", "--count", f"@{{upstream}}..HEAD"],
            cwd=repo_path
        )
        commits_to_push = int(counts)

        if commits_to_push == 0:
            return PushResult(
                success=True,
                commits_pushed=0,
                nothing_to_push=True
            )
    except GitError:
        # No upstream branch
        raise SyncError("No upstream branch configured for push")

    # Push with appropriate flags
    try:
        if force_with_lease:
            run_git_command(
                ["push", "--force-with-lease", "origin", branch],
                cwd=repo_path
            )
        else:
            run_git_command(
                ["push", "origin", branch],
                cwd=repo_path
            )

        return PushResult(
            success=True,
            commits_pushed=commits_to_push,
            nothing_to_push=False
        )

    except GitError as e:
        raise SyncError(f"Push failed: {e}")
```

### Sync Orchestration

```python
def sync_project(
    project_name: str,
    push: bool = False,
    force_pull: bool = False,
    dry_run: bool = False,
    rebase: bool = False,
    specific_repo: str | None = None
) -> SyncSummary:
    """Synchronize all repositories in a project."""

    # Load project configuration
    config = load_project_config(project_name)
    meta_path = Path(config.meta_path)
    project_dir = meta_path / config.folder

    # Load repositories from pyproject.toml
    repos = load_repos_from_pyproject(project_dir)

    # Initialize results
    results = []

    # Sync meta repository first (unless --repos-only)
    if specific_repo is None or specific_repo == "meta":
        print(f"Meta Repository ({config.branch})")
        if not dry_run:
            result = sync_single_repo(
                meta_path,
                config.branch,
                push=push,
                force_pull=force_pull,
                rebase=rebase
            )
            results.append(("meta", result))
        else:
            print("  [DRY RUN] Would fetch, pull, and optionally push")

    # Sync sub-repositories
    print("\nSub-repositories:\n")
    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Skip if specific repo requested and this isn't it
        if specific_repo and repo_name != specific_repo:
            continue

        print(f"  {repo_name} ({repo_config.url})")

        # Check if repo exists
        if not repo_path.exists():
            print("    Warning: Repository not cloned")
            results.append((repo_name, SyncResult(skipped=True)))
            continue

        if not dry_run:
            result = sync_single_repo(
                repo_path,
                repo_config.branch,
                push=push,
                force_pull=force_pull,
                rebase=rebase
            )
            results.append((repo_name, result))
        else:
            print("    [DRY RUN] Would fetch, pull, and optionally push")

    # Print summary
    return print_sync_summary(results, push=push)
```

## Error Conditions

- Current project not set: "No current project. Run 'qen init <project>' or use --project flag."
- Uncommitted changes: "Uncommitted changes detected in <repo>. Commit, stash, or use --force-pull."
- No upstream branch: "No upstream branch configured for <repo>."
- Merge conflicts: "Pull resulted in merge conflicts in <repo>. Resolve manually."
- Push rejected: "Push rejected for <repo>. Remote has commits you don't have. Pull first."
- Network error: "Failed to reach remote for <repo>: <error message>"
- Repository not cloned: "Repository <repo> not found. Run 'qen clone' first."

## Examples

### Example 1: Basic pull sync

```bash
$ qen sync
Syncing project: auth-redesign (2025-12-05-auth-redesign)

Meta Repository (2025-12-05-auth-redesign)
  Fetching... ✓
  Pulling...  ✓ (2 commits pulled)
  Status:     up-to-date

Sub-repositories:

  repos/api (github.com/myorg/api)
    Fetching... ✓
    Pulling...  ✓ (already up-to-date)
    Status:     up-to-date

Summary:
  ✓ 2 repositories synced
  ↓ 2 commits pulled
```

### Example 2: Bidirectional sync (pull + push)

```bash
$ qen sync --push
Syncing project: auth-redesign (2025-12-05-auth-redesign)

Meta Repository (2025-12-05-auth-redesign)
  Fetching... ✓
  Pulling...  ✓ (already up-to-date)
  Pushing...  ✓ (1 commit pushed)
  Status:     synchronized

Sub-repositories:

  repos/api (github.com/myorg/api)
    Fetching... ✓
    Pulling...  ✓ (1 commit pulled)
    Pushing...  ✓ (2 commits pushed)
    Status:     synchronized

Summary:
  ✓ 2 repositories synced
  ↓ 1 commit pulled
  ↑ 3 commits pushed
```

### Example 3: Dry run

```bash
$ qen sync --push --dry-run
[DRY RUN] Syncing project: auth-redesign (2025-12-05-auth-redesign)

Meta Repository (2025-12-05-auth-redesign)
  [DRY RUN] Would fetch, pull, and push

Sub-repositories:

  repos/api (github.com/myorg/api)
    [DRY RUN] Would fetch, pull, and push

[DRY RUN] No changes made
```

### Example 4: Sync single repo

```bash
$ qen sync --repo repos/api
Syncing project: auth-redesign (2025-12-05-auth-redesign)

  repos/api (github.com/myorg/api)
    Fetching... ✓
    Pulling...  ✓ (1 commit pulled)
    Status:     up-to-date

Summary:
  ✓ 1 repository synced
  ↓ 1 commit pulled
```

### Example 5: Error with uncommitted changes

```bash
$ qen sync
Syncing project: auth-redesign (2025-12-05-auth-redesign)

Meta Repository (2025-12-05-auth-redesign)
  Fetching... ✓
  Pulling...  ✗ ERROR: Uncommitted changes detected

    Modified files:
      - README.md
      - docs/api.md

    Options:
      1. Commit changes: git commit -am "your message"
      2. Stash changes: git stash
      3. Force pull:     qen sync --force-pull (will auto-stash)

Sync aborted.
```

## Test Requirements

### Unit Tests

1. **Uncommitted changes detection** (`tests/test_sync.py`):
   - Test detecting clean repository (no changes)
   - Test detecting modified files (unstaged changes)
   - Test detecting staged files
   - Test detecting untracked files
   - Test detecting combination of changes
   - Test handling non-existent repository

2. **Pull operation tests**:
   - Test successful pull with no local changes
   - Test pull that brings in new commits
   - Test pull when already up-to-date
   - Test pull with uncommitted changes (should fail)
   - Test pull with --force-pull (should stash)
   - Test pull with rebase (--rebase flag)
   - Test pull failure and recovery
   - Test counting commits pulled correctly
   - Test stash pop after successful pull
   - Test stash recovery after failed pull

3. **Push operation tests**:
   - Test successful push with local commits
   - Test push when nothing to push (up-to-date)
   - Test push with --force-with-lease
   - Test push without upstream branch (should error)
   - Test push rejection (remote ahead)
   - Test counting commits pushed correctly

4. **Sync orchestration tests**:
   - Test syncing meta repo first
   - Test syncing multiple sub-repos in sequence
   - Test skipping missing repos (not cloned)
   - Test --repos-only flag (skip meta)
   - Test --repo flag (specific repo only)
   - Test --dry-run mode (no actual changes)
   - Test continuing after one repo fails
   - Test summary generation

5. **Flag handling tests**:
   - Test --push flag enables pushing
   - Test --force-pull enables stashing
   - Test --dry-run prevents changes
   - Test --rebase uses rebase strategy
   - Test --prune flag during fetch
   - Test --project overrides current project
   - Test --repo filters to specific repo

6. **Error handling tests**:
   - Test error when no current project set
   - Test error when uncommitted changes exist
   - Test error when no upstream branch
   - Test error when merge conflicts occur
   - Test error when push is rejected
   - Test error when network fails
   - Test error when repo not cloned
   - Test graceful degradation (continue on error)

### Integration Tests

1. **Full sync workflow** (`tests/integration/test_sync_integration.py`):
   - Create test project with qen init
   - Add test repositories to pyproject.toml
   - Create local and remote git repos
   - Make commits on remote
   - Run qen sync (pull)
   - Verify commits pulled correctly
   - Make local commits
   - Run qen sync --push
   - Verify commits pushed correctly

2. **Pull scenarios**:
   - Test pulling when local is behind remote
   - Test pulling when local is up-to-date
   - Test pulling when local has uncommitted changes
   - Test force-pull with uncommitted changes (stash workflow)
   - Test pull with rebase
   - Test pull with merge conflicts

3. **Push scenarios**:
   - Test pushing when local is ahead of remote
   - Test pushing when local is up-to-date
   - Test pushing when remote is ahead (rejection)
   - Test push after pull (synchronized workflow)

4. **Multi-repo scenarios**:
   - Test syncing multiple repos simultaneously
   - Test syncing when some repos are missing
   - Test syncing with mixed success/failure
   - Test syncing meta + sub-repos
   - Test --repo flag to sync single repo

5. **Stash recovery scenarios**:
   - Test successful stash and pop (force-pull works)
   - Test stash pop with conflicts
   - Test recovery when pull fails mid-operation
   - Test preserving uncommitted changes through force-pull

6. **Dry run scenarios**:
   - Test --dry-run shows planned actions
   - Test --dry-run doesn't modify any repos
   - Test --dry-run output accuracy

### Test Fixtures

Required test fixtures in `tests/fixtures/`:

1. **Mock git repositories**:
   - Clean local repo (synced with remote)
   - Local repo ahead of remote (commits to push)
   - Local repo behind remote (commits to pull)
   - Local repo with uncommitted changes
   - Diverged repo (both ahead and behind)
   - Repo without upstream branch

2. **Remote git repositories**:
   - Mock remote with new commits
   - Mock remote that rejects pushes
   - Mock remote with network errors
   - Mock remote with LFS files (future)

3. **Mock pyproject.toml files**:
   - Valid with multiple repos
   - Valid with single repo
   - Valid with repos using different branches
   - Empty repos array

4. **Mock project configurations**:
   - Valid project with all repos cloned
   - Project with some repos missing
   - Project with no sub-repos

### Test Helpers

Required test helpers in `tests/helpers/`:

1. **Git test utilities**:
   - `create_test_repo()` - Create temporary git repo with commits
   - `create_remote_repo()` - Create temporary bare repo as remote
   - `make_commits()` - Add test commits to a repo
   - `create_uncommitted_changes()` - Add modified/staged/untracked files
   - `setup_remote_tracking()` - Configure upstream branch
   - `simulate_diverged_branches()` - Create diverged repo state

2. **Sync test utilities**:
   - `assert_sync_success()` - Verify sync completed successfully
   - `assert_commits_pulled()` - Verify expected commits were pulled
   - `assert_commits_pushed()` - Verify expected commits were pushed
   - `assert_repo_clean()` - Verify no uncommitted changes
   - `assert_stash_empty()` - Verify stash is empty

### Test Coverage Requirements

- Minimum 85% code coverage for sync command implementation
- 100% coverage for critical paths (pull, push, stash operations)
- 100% coverage for error recovery paths
- All edge cases must have explicit test coverage
- All error conditions must have explicit test coverage
- Stash recovery must be thoroughly tested (data loss prevention)

### Test Isolation

- Each test must use isolated temporary directories
- Each test must clean up git repos after completion
- Tests must not interfere with real user configs
- Tests must not require network access (except integration tests)
- Tests must use mock remotes (not real GitHub repos)

## Future Enhancements

1. **Parallel sync**: Sync multiple repos concurrently for speed
2. **Conflict resolution**: Interactive conflict resolution for merge conflicts
3. **Auto-commit**: `--auto-commit` flag to commit WIP changes before syncing
4. **Branch tracking**: Ensure all repos are on their configured branches before syncing
5. **Sync hooks**: Pre/post sync hooks for custom automation
6. **Selective sync**: `--only-behind` to only sync repos that are behind
7. **Fast-forward only**: `--ff-only` to only allow fast-forward pulls
8. **Progress bars**: Visual progress indicators for long operations
9. **Submodule support**: Handle git submodules within sub-repos
10. **LFS support**: Properly handle Git LFS files during sync
