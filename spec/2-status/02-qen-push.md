# qen push - Push Local Changes Across Repositories

## Overview

`qen push` pushes local commits across all sub-repositories within a QEN project. It safely pushes changes to remote branches while checking for potential issues and providing clear feedback about what was pushed.

## Command Behavior

### Basic Usage

```bash
qen push                    # Push all repos with local commits
qen push --dry-run          # Show what would be pushed without pushing
qen push --force-with-lease # Push with lease (safer force push)
```

**Note:** `qen push` only pushes repositories that have local commits ahead of their remote tracking branch. Repositories already up-to-date are skipped.

### What It Does

1. **Locates current project** - Uses default project from qen config
2. **Discovers all sub-repositories** - Reads `pyproject.toml` to find repos in `[tool.qen.repos]`
3. **Checks local state** - Identifies repos with commits to push
4. **Validates push safety** - Checks for uncommitted changes, detached HEAD, no upstream
5. **Pushes local commits** - Pushes changes to remote branch
6. **Updates metadata** - Updates `updated` timestamp in `pyproject.toml`
7. **Displays summary** - Shows what was pushed across all repositories

## Repository State Requirements

### Pre-Push Validation

Before pushing, `qen push` validates each repository:

1. **Repository exists** - Skip if not cloned locally
2. **No uncommitted changes** - Error unless `--allow-dirty` flag used
3. **Not detached HEAD** - Cannot push from detached HEAD state
4. **Has upstream branch** - Remote tracking branch must be configured
5. **Has commits to push** - Skip if already up-to-date

### Uncommitted Changes Policy

**By default, uncommitted changes block push** to avoid surprises:

- Ensures user has committed all intended changes
- Prevents confusion about what was actually pushed
- Use `--allow-dirty` to explicitly bypass this check
- Suggestion: Run `qen commit` to commit changes before pushing

## Output Format

### Summary View

```log
Pushing project: feature-work

📦 example-repo (feature/my-work)
   ✓ Pushed 3 commits to origin/feature/my-work
   📋 PR #123 (open) → main
   ✓ Checks passing

📦 another-repo (main)
   • Already up-to-date (0 commits to push)

📦 third-repo (bugfix/issue-456)
   ✓ Pushed 2 commits to origin/bugfix/issue-456
   📋 PR #789 (draft) → develop

Summary:
  3 repositories processed
  2 repositories pushed (5 commits total)
  1 repository up-to-date
```

### Dry Run View

```log
[DRY RUN] Pushing project: feature-work

📦 example-repo (feature/my-work)
   Would push: 3 commits to origin/feature/my-work

📦 another-repo (main)
   Already up-to-date: 0 commits to push

📦 third-repo (bugfix/issue-456)
   Would push: 2 commits to origin/bugfix/issue-456

[DRY RUN] Summary:
  Would push 2 repositories (5 commits total)
  1 repository already up-to-date
```

## Error Handling

### Scenarios to Handle

1. **No upstream branch** - Error with setup instructions
2. **Remote ahead** - Push rejected, suggest `qen pull` first
3. **Remote unreachable** - Network error, retry suggestion
4. **Detached HEAD** - Cannot push, suggest checking out a branch
5. **Authentication required** - Prompt or use credential helper
6. **Force push required** - Suggest `--force-with-lease` if diverged
7. **GitHub API unavailable** - Skip PR/issue updates, continue with git operations

### Error Examples

```log
📦 example-repo (feature/my-work)
   ✗ Push rejected: remote has commits you don't have
   Suggestion: Run 'qen pull' first, then push again

📦 another-repo (detached HEAD)
   ✗ Cannot push from detached HEAD
   Suggestion: Checkout a branch first (git checkout main)

📦 third-repo (bugfix/issue-456)
   ✗ No upstream branch configured
   Suggestion: Set upstream with 'git push -u origin bugfix/issue-456'
```

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `--dry-run` | Show what would be pushed without pushing | false |
| `--allow-dirty` | Allow push even with uncommitted changes | false |
| `--force-with-lease` | Force push with lease (safer than --force) | false |
| `--force` | Force push (dangerous, overwrites remote) | false |
| `--set-upstream` | Set upstream for branches without tracking | false |
| `--repo <name>` | Push only specific repository | all |
| `--verbose` | Show detailed git output | false |

### Flag Usage Notes

**`--allow-dirty`**: Allow push with uncommitted changes

- By default, `qen push` fails if uncommitted changes exist
- Use this flag to explicitly allow pushing anyway
- Helps avoid accidentally leaving uncommitted work behind
- Suggestion: Use `qen commit` to commit changes first instead

**`--force-with-lease`**: Safer alternative to `--force`

- Only overwrites remote if your local tracking branch is up-to-date
- Prevents overwriting others' work
- Recommended over `--force` in almost all cases

**`--force`**: Dangerous, overwrites remote unconditionally

- Only use when you're certain you want to overwrite remote
- Requires confirmation prompt

**`--set-upstream`**: Automatically set upstream for new branches

- Useful for newly created branches without remotes
- Equivalent to `git push -u origin <branch>`

## Integration Points

### With Other Commands

- `qen pull` - Fetch and pull changes before pushing
- `qen status` - Check which repos have commits to push
- `qen sync` - Bidirectional sync (pull + push)
- `qen add` - Set up new repos with upstream tracking

### External Tools

- **gh CLI** - Optional for PR/issue information. If not installed, GitHub features are skipped.
- **git** - Required. All git operations via subprocess calls to git CLI.

## Configuration

### Project-Level Settings (Optional)

```toml
[tool.qen.push]
force_with_lease = false                # Default to force-with-lease
set_upstream = false                    # Auto-set upstream for new branches
parallel = true                         # Push repos in parallel
max_workers = 4                         # Parallel worker count
```

### Global Settings (Optional)

```toml
[push]
github_cli = "gh"                       # Path to GitHub CLI (default: "gh")
require_confirmation = true             # Confirm before force push
```

## Success Criteria

### Must Accomplish

1. **Push all repos with commits** - Successfully push each repository ahead of remote
2. **Query current state** - Show which repos need pushing before attempting
3. **Validate push safety** - Check upstream, detached HEAD, remote ahead
4. **Handle failures gracefully** - One repo failure doesn't stop others
5. **Show clear summary** - User understands what was pushed and what failed

### Should Accomplish

1. **Parallel execution** - Push multiple repos concurrently
2. **GitHub integration** - Update PR/issue metadata if available
3. **Smart error messages** - Suggest fixes for common issues (no upstream, remote ahead)

### Nice to Have

1. **Progress indication** - Show progress for long-running operations
2. **Selective push** - Push specific repos only
3. **Branch protection checks** - Warn if pushing to protected branches

## Non-Goals

- **Not a git wrapper** - Don't replicate all git push options
- **Not CI/CD** - Don't run builds or tests before pushing
- **Not a merge tool** - Don't resolve conflicts on push
- **Not a code review tool** - Don't enforce review before push
- **Not a branch manager** - Don't create or delete remote branches

## Design Decisions

1. **Multiple remotes** - Only push to `origin`. Other remotes are out of scope.
2. **Uncommitted changes** - Warn but don't block (committed work is safe to push)
3. **Force push safety** - Require `--force-with-lease` or `--force` flag explicitly
4. **Upstream tracking** - Require upstream unless `--set-upstream` flag used
5. **Continue on error** - Keep pushing other repos even if one fails

## Implementation Details

### Push Operation

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PushResult:
    success: bool
    commits_pushed: int
    nothing_to_push: bool
    skipped: bool = False
    error_message: str | None = None

def push_repo(
    repo_path: Path,
    branch: str,
    force_with_lease: bool = False,
    force: bool = False,
    set_upstream: bool = False,
    allow_dirty: bool = False,
) -> PushResult:
    """Push local commits to remote branch."""

    # Check for uncommitted changes
    if not allow_dirty and has_uncommitted_changes(repo_path):
        return PushResult(
            success=False,
            commits_pushed=0,
            nothing_to_push=False,
            error_message="Uncommitted changes detected. Commit changes or use --allow-dirty.",
        )

    # Check if there's anything to push
    try:
        # Get commit count ahead of remote
        counts = run_git_command(
            ["rev-list", "--count", "@{upstream}..HEAD"],
            cwd=repo_path,
        )
        commits_to_push = int(counts.strip())

        if commits_to_push == 0:
            return PushResult(
                success=True,
                commits_pushed=0,
                nothing_to_push=True,
            )
    except GitError as e:
        # No upstream branch
        if set_upstream:
            # Will set upstream during push
            commits_to_push = count_local_commits(repo_path)
        else:
            return PushResult(
                success=False,
                commits_pushed=0,
                nothing_to_push=False,
                error_message="No upstream branch configured. Use --set-upstream.",
            )

    # Build push command
    cmd = ["push"]

    if force:
        cmd.append("--force")
    elif force_with_lease:
        cmd.append("--force-with-lease")

    if set_upstream:
        cmd.extend(["-u", "origin", branch])
    else:
        cmd.extend(["origin", branch])

    # Push with appropriate flags
    try:
        run_git_command(cmd, cwd=repo_path)

        return PushResult(
            success=True,
            commits_pushed=commits_to_push,
            nothing_to_push=False,
        )

    except GitError as e:
        error_msg = parse_push_error(e)
        return PushResult(
            success=False,
            commits_pushed=0,
            nothing_to_push=False,
            error_message=error_msg,
        )

def parse_push_error(error: GitError) -> str:
    """Parse git push error and return user-friendly message."""
    stderr = error.stderr.lower()

    if "rejected" in stderr and "non-fast-forward" in stderr:
        return "Remote has commits you don't have. Run 'qen pull' first."

    if "no upstream" in stderr or "does not track" in stderr:
        return "No upstream branch configured. Use --set-upstream."

    if "could not resolve host" in stderr:
        return "Network error: Cannot reach remote."

    if "authentication failed" in stderr or "permission denied" in stderr:
        return "Authentication failed. Check credentials."

    if "protected branch" in stderr:
        return "Branch is protected. Check repository settings."

    return f"Push failed: {error.stderr}"

def count_local_commits(repo_path: Path) -> int:
    """Count commits on current branch (for new branches without upstream)."""
    try:
        result = run_git_command(
            ["rev-list", "--count", "HEAD"],
            cwd=repo_path,
        )
        return int(result.strip())
    except GitError:
        return 0
```

### Pre-Push Validation

```python
from dataclasses import dataclass

@dataclass
class RepoState:
    exists: bool
    has_commits_to_push: bool
    has_uncommitted_changes: bool
    is_detached_head: bool
    has_upstream: bool
    current_branch: str | None

def validate_repo_state(repo_path: Path) -> RepoState:
    """Validate repository state before pushing."""

    if not repo_path.exists():
        return RepoState(
            exists=False,
            has_commits_to_push=False,
            has_uncommitted_changes=False,
            is_detached_head=False,
            has_upstream=False,
            current_branch=None,
        )

    # Check for detached HEAD
    try:
        branch = run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
        ).strip()
        is_detached = branch == "HEAD"
    except GitError:
        is_detached = True
        branch = None

    # Check for uncommitted changes
    has_uncommitted = has_uncommitted_changes(repo_path)

    # Check for upstream branch
    has_upstream = False
    try:
        run_git_command(
            ["rev-parse", "@{upstream}"],
            cwd=repo_path,
        )
        has_upstream = True
    except GitError:
        pass

    # Check if there are commits to push
    has_commits = False
    if has_upstream and not is_detached:
        try:
            count = run_git_command(
                ["rev-list", "--count", "@{upstream}..HEAD"],
                cwd=repo_path,
            )
            has_commits = int(count.strip()) > 0
        except GitError:
            pass
    elif not is_detached:
        # No upstream, check if there are local commits
        has_commits = count_local_commits(repo_path) > 0

    return RepoState(
        exists=True,
        has_commits_to_push=has_commits,
        has_uncommitted_changes=has_uncommitted,
        is_detached_head=is_detached,
        has_upstream=has_upstream,
        current_branch=branch,
    )
```

### Push Orchestration

```python
def push_project(
    project_name: str,
    dry_run: bool = False,
    force_with_lease: bool = False,
    force: bool = False,
    set_upstream: bool = False,
    allow_dirty: bool = False,
    specific_repo: str | None = None,
) -> PushSummary:
    """Push all repositories in a project."""

    # Confirm force push if requested
    if force and not dry_run:
        confirm = input("⚠️  Force push will overwrite remote. Continue? [y/N] ")
        if confirm.lower() != "y":
            print("Push cancelled.")
            return PushSummary(cancelled=True)

    # Load project configuration
    config = load_project_config(project_name)
    meta_path = Path(config.meta_path)
    project_dir = meta_path / config.folder

    # Load repositories from pyproject.toml
    repos = load_repos_from_pyproject(project_dir)

    # Initialize results
    results = []

    # Push sub-repositories
    print(f"Pushing project: {config.name}\n")

    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Skip if specific repo requested and this isn't it
        if specific_repo and repo_name != specific_repo:
            continue

        print(f"📦 {repo_name} ({repo_config.branch})")

        # Validate repo state
        state = validate_repo_state(repo_path)

        if not state.exists:
            print("   ⚠ Repository not cloned. Skipping.")
            results.append((repo_name, PushResult(
                success=False,
                commits_pushed=0,
                nothing_to_push=False,
                skipped=True,
            )))
            continue

        if state.is_detached_head:
            print("   ✗ Cannot push from detached HEAD")
            print("   Suggestion: Checkout a branch first")
            results.append((repo_name, PushResult(
                success=False,
                commits_pushed=0,
                nothing_to_push=False,
                error_message="Detached HEAD",
            )))
            continue

        if not state.has_commits_to_push:
            print("   • Already up-to-date (0 commits to push)")
            results.append((repo_name, PushResult(
                success=True,
                commits_pushed=0,
                nothing_to_push=True,
            )))
            continue

        # Check for uncommitted changes
        if state.has_uncommitted_changes and not allow_dirty:
            print("   ✗ Uncommitted changes detected")
            print("   Suggestion: Run 'qen commit' to commit changes first")
            results.append((repo_name, PushResult(
                success=False,
                commits_pushed=0,
                nothing_to_push=False,
                error_message="Uncommitted changes",
            )))
            continue

        if state.has_uncommitted_changes and allow_dirty:
            print("   ⚠ Uncommitted changes (will not be pushed)")

        if dry_run:
            # Count commits without pushing
            if state.has_upstream:
                count = run_git_command(
                    ["rev-list", "--count", "@{upstream}..HEAD"],
                    cwd=repo_path,
                )
            else:
                count = count_local_commits(repo_path)

            commits = int(count.strip()) if count else 0
            print(f"   Would push: {commits} commits to origin/{repo_config.branch}")
            results.append((repo_name, PushResult(
                success=True,
                commits_pushed=commits,
                nothing_to_push=False,
            )))
        else:
            # Actually push
            result = push_repo(
                repo_path,
                repo_config.branch,
                force_with_lease=force_with_lease,
                force=force,
                set_upstream=set_upstream,
                allow_dirty=allow_dirty,
            )

            if result.success:
                if not result.nothing_to_push:
                    print(f"   ✓ Pushed {result.commits_pushed} commits to origin/{repo_config.branch}")

                    # Update metadata timestamp
                    update_repo_metadata(project_dir, repo_name, {
                        "updated": datetime.utcnow().isoformat() + "Z"
                    })
            else:
                print(f"   ✗ {result.error_message}")

            results.append((repo_name, result))

    # Print summary
    return print_push_summary(results, dry_run=dry_run)
```

## Error Conditions

- **No current project**: "No current project. Run 'qen init <project>' or use --project flag."
- **No upstream branch**: "No upstream branch configured for <repo>. Use --set-upstream."
- **Remote ahead**: "Push rejected for <repo>. Remote has commits you don't have. Run 'qen pull' first."
- **Detached HEAD**: "Cannot push from detached HEAD in <repo>. Checkout a branch first."
- **Authentication failed**: "Authentication failed for <repo>. Check credentials."
- **Network error**: "Failed to reach remote for <repo>: <error message>"
- **Repository not cloned**: "Repository <repo> not found. Run 'qen add <repo>' first."
- **Protected branch**: "Cannot push to protected branch in <repo>. Check repository settings."

## Examples

### Example 1: Basic push

```bash
$ qen push
Pushing project: feature-work

📦 example-repo (feature/my-work)
   ✓ Pushed 3 commits to origin/feature/my-work

📦 another-repo (main)
   • Already up-to-date (0 commits to push)

Summary:
  2 repositories processed
  1 repository pushed (3 commits)
  1 repository up-to-date
```

### Example 2: Dry run

```bash
$ qen push --dry-run
[DRY RUN] Pushing project: feature-work

📦 example-repo (feature/my-work)
   Would push: 3 commits to origin/feature/my-work

📦 another-repo (main)
   Already up-to-date: 0 commits to push

[DRY RUN] Summary:
  Would push 1 repository (3 commits)
  1 repository already up-to-date
```

### Example 3: Push blocked by uncommitted changes

```bash
$ qen push
Pushing project: feature-work

📦 example-repo (feature/my-work)
   ✗ Uncommitted changes detected

    Modified files:
      - src/main.py
      - tests/test_main.py

    Options:
      1. Commit changes: qen commit -m "your message"
      2. Stash changes:  git stash
      3. Allow anyway:   qen push --allow-dirty

Push failed: 1 repository has uncommitted changes
```

### Example 3b: Push with --allow-dirty

```bash
$ qen push --allow-dirty
Pushing project: feature-work

📦 example-repo (feature/my-work)
   ⚠ Uncommitted changes (will not be pushed)
   ✓ Pushed 2 commits to origin/feature/my-work

Summary:
  1 repository pushed (2 commits)
  ⚠ Reminder: 1 repository has uncommitted changes
```

### Example 4: Push rejected (remote ahead)

```bash
$ qen push
Pushing project: feature-work

📦 example-repo (feature/my-work)
   ✗ Remote has commits you don't have. Run 'qen pull' first.

Summary:
  0 repositories pushed
  1 repository failed
```

### Example 5: Push with --set-upstream

```bash
$ qen push --set-upstream
Pushing project: feature-work

📦 example-repo (feature/new-feature)
   ✓ Set upstream and pushed 5 commits to origin/feature/new-feature

Summary:
  1 repository pushed (5 commits)
  1 upstream branch configured
```

## Related Specifications

- [01-qen-pull.md](01-qen-pull.md) - Pull operations and metadata updates
- [4-qen-status.md](../1-qen-init/4-qen-status.md) - Status display using this metadata
- [5-qen-sync.md](../1-qen-init/5-qen-sync.md) - Bidirectional sync (pull + push)
