# Spec: `qen add --force` - Idempotent Repository Addition

**Status:** Approved
**Created:** 2025-12-07
**Related Issues:** Corrupted repository additions

## Problem

Currently, `qen add` fails when attempting to re-add a repository that already exists in the project:

```bash
$ qen add deployment
Error: Repository already exists in project: https://github.com/quiltdata/deployment (branch: 2025-12-05-benchling-stacked)
Aborted!
```

This blocking behavior prevents users from:

- Fixing corrupted repository clones (incomplete clones, wrong permissions, etc.)
- Re-cloning repositories after accidental deletion of clone directory
- Recovering from partial `qen add` failures
- Updating repository state when something goes wrong

### Root Cause

The existence check in `src/qen/commands/add.py:149-161` blocks re-addition before any validation or cloning occurs, making recovery impossible without manual intervention (editing `pyproject.toml` and removing directories).

## Solution: Add `--force` Flag

Add a `--force` flag to `qen add` that makes the command idempotent by removing existing entries before re-adding.

### Behavior

**Without `--force` (default - preserves current behavior):**

```bash
$ qen add myrepo
✓ Added repository: https://github.com/org/myrepo

$ qen add myrepo
Error: Repository already exists in project: https://github.com/org/myrepo (branch: main)
Aborted!
```

**With `--force` (new idempotent behavior):**

```bash
$ qen add myrepo
✓ Added repository: https://github.com/org/myrepo

$ qen add myrepo --force
Repository exists. Removing and re-adding with --force...
Removing existing clone at repos/main/myrepo
✓ Added repository: https://github.com/org/myrepo
  Branch: main
  Path: /path/to/proj/2025-12-07-project/repos/main/myrepo
```

### Command Signature

```bash
qen add <repo> [--branch <branch>] [--path <path>] [--force] [--verbose]
```

**New Flag:**

- `--force`: Force re-add even if repository exists (removes and re-clones)

## Implementation Design

### Architecture

The implementation follows a clean separation of concerns:

1. **CLI Layer** (`src/qen/cli.py`) - Accepts `--force` flag, passes to business logic
2. **Business Logic** (`src/qen/commands/add.py`) - Conditional removal based on flag
3. **Data Layer** (`src/qen/pyproject_utils.py`) - CRUD operations on config
4. **Filesystem** - Direct `shutil.rmtree()` for clone cleanup

### Key Components

#### 1. CLI Command Update

**File:** `src/qen/cli.py:71-111`

```python
@main.command("add")
@click.argument("repo")
@click.option("--branch", "-b", help="Branch to track (default: main)")
@click.option("--path", "-p", help="Local path (default: repos/<name>)")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--force", is_flag=True, help="Force re-add if repository exists")
def add(repo: str, branch: str | None, path: str | None, verbose: bool, force: bool) -> None:
    """Add a repository to the current project."""
    add_repository(repo, branch, path, verbose, force)
```

#### 2. Business Logic Update

**File:** `src/qen/commands/add.py:49-161`

Add `force` parameter to function signature:

```python
def add_repository(
    repo: str,
    branch: str | None = None,
    path: str | None = None,
    verbose: bool = False,
    force: bool = False,  # NEW
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
) -> None:
```

Modify existence check to be conditional:

```python
# Check if repository already exists in pyproject.toml
try:
    if repo_exists_in_pyproject(project_dir, url, branch):
        if not force:
            # Existing behavior - block and abort
            click.echo(
                f"Error: Repository already exists in project: {url} (branch: {branch})",
                err=True,
            )
            raise click.Abort()
        else:
            # New behavior - remove existing entry and re-add
            if verbose:
                click.echo(f"Repository exists. Removing and re-adding with --force...")
            remove_existing_repo(project_dir, url, branch, verbose)
except PyProjectNotFoundError as e:
    click.echo(f"Error: {e}", err=True)
    raise click.Abort() from e
```

#### 3. Removal Helper Function

**File:** `src/qen/commands/add.py` (new function before `add_repository`)

```python
def remove_existing_repo(project_dir: Path, url: str, branch: str, verbose: bool = False) -> None:
    """Remove existing repository from both config and filesystem.

    Args:
        project_dir: Path to project directory
        url: Repository URL to remove
        branch: Branch to remove
        verbose: Enable verbose output

    Raises:
        PyProjectUpdateError: If removal from pyproject.toml fails
    """
    # Get the stored path from config and remove entry
    repo_path_str = remove_repo_from_pyproject(project_dir, url, branch)

    if repo_path_str:
        # Convert relative path to absolute
        repo_path = project_dir / repo_path_str

        # Remove clone directory if it exists
        if repo_path.exists():
            if verbose:
                click.echo(f"Removing existing clone at {repo_path}")
            shutil.rmtree(repo_path)
        elif verbose:
            click.echo(f"Clone directory not found: {repo_path} (already removed)")
    elif verbose:
        click.echo("Repository entry not found in pyproject.toml (already removed)")
```

#### 4. Data Layer - Removal Function

**File:** `src/qen/pyproject_utils.py` (after line 216)

```python
def remove_repo_from_pyproject(project_dir: Path, url: str, branch: str) -> str | None:
    """Remove a repository entry from pyproject.toml.

    Args:
        project_dir: Path to project directory
        url: Repository URL to remove
        branch: Branch name to remove

    Returns:
        The path of the removed repository (for cleanup), or None if not found

    Raises:
        PyProjectNotFoundError: If pyproject.toml does not exist
        PyProjectUpdateError: If update fails
    """
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise PyProjectNotFoundError(f"pyproject.toml not found in {project_dir}")

    handler = TOMLHandler()

    try:
        config = handler.read(pyproject_path)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to read pyproject.toml: {e}") from e

    # Navigate to [tool.qen.repos]
    if "tool" not in config or "qen" not in config["tool"] or "repos" not in config["tool"]["qen"]:
        return None

    repos = config["tool"]["qen"]["repos"]
    if not isinstance(repos, list):
        return None

    # Find and remove matching repo
    removed_path = None
    new_repos = []
    for repo in repos:
        if isinstance(repo, dict):
            if repo.get("url") == url and repo.get("branch") == branch:
                removed_path = repo.get("path")
            else:
                new_repos.append(repo)

    if removed_path is None:
        return None  # Repo not found

    # Update config
    config["tool"]["qen"]["repos"] = new_repos

    # Write back to file
    try:
        handler.write(pyproject_path, config)
    except Exception as e:
        raise PyProjectUpdateError(f"Failed to write pyproject.toml: {e}") from e

    return removed_path
```

### Import Updates

**File:** `src/qen/commands/add.py` (line 9-10)

```python
import shutil  # Ensure this is imported
from pathlib import Path
```

**File:** `src/qen/commands/add.py` (line 17-22)

```python
from ..pyproject_utils import (
    PyProjectNotFoundError,
    PyProjectUpdateError,
    add_repo_to_pyproject,
    repo_exists_in_pyproject,
    remove_repo_from_pyproject,  # ADD THIS
)
```

## Testing Strategy

### Unit Tests

**File:** `tests/qen/test_add.py`

#### 1. Test `remove_repo_from_pyproject` Function

Add new test class after `TestPyProjectUpdates`:

```python
class TestRemoveRepoFromPyproject:
    """Tests for removing repositories from pyproject.toml."""

    def test_remove_existing_repo(self, tmp_path: Path) -> None:
        """Test removing an existing repository."""
        # Setup: Create pyproject.toml with two repos
        # Action: Remove one repo
        # Assert: Only remaining repo exists in config

    def test_remove_nonexistent_repo(self, tmp_path: Path) -> None:
        """Test removing a repo that doesn't exist."""
        # Setup: Create pyproject.toml with one repo
        # Action: Try to remove different repo
        # Assert: Returns None, original repo unchanged

    def test_remove_repo_no_pyproject(self, tmp_path: Path) -> None:
        """Test removing repo when pyproject.toml doesn't exist."""
        # Action: Try to remove repo
        # Assert: Raises PyProjectNotFoundError
```

#### 2. Test `--force` Flag Behavior

Modify existing test and add new test:

```python
def test_add_duplicate_repository_fails_without_force(self, ...):
    """Test that adding duplicate repository fails WITHOUT --force flag."""
    # Add repo first time
    # Try to add same repo without force
    # Assert: Raises click.Abort

def test_add_duplicate_repository_with_force(self, ...):
    """Test that adding duplicate repository succeeds WITH --force flag."""
    # Add repo first time
    # Modify clone to add marker file
    # Add same repo WITH force=True
    # Assert:
    #   - Marker file is gone (re-cloned)
    #   - pyproject.toml has only one entry (not duplicated)
    #   - Repository is functional
```

### Test Coverage Goals

- ✅ `remove_repo_from_pyproject()` unit tests
- ✅ `--force` flag integration tests
- ✅ Edge cases: missing clone, missing config entry, missing pyproject.toml
- ✅ Idempotency: multiple `--force` calls succeed

## Edge Cases and Error Handling

### 1. Repository in Config, Clone Missing

**Scenario:**

```toml
[[tool.qen.repos]]
url = "https://github.com/org/repo"
branch = "main"
path = "repos/main/repo"
```

But `repos/main/repo` directory doesn't exist.

**Behavior with `--force`:**

- Removes entry from pyproject.toml
- Attempts to remove directory (silently succeeds if missing)
- Re-clones repository
- ✅ **Result:** Clean state restored

### 2. Clone Exists, Not in Config

**Scenario:**

- `repos/main/repo` directory exists
- No entry in pyproject.toml

**Behavior with `--force`:**

- `repo_exists_in_pyproject()` returns False
- Regular add flow proceeds
- Cloning fails (destination exists)
- ❌ **Result:** Error (expected - this is filesystem corruption, not config corruption)

**Manual fix:** User must remove directory manually

### 3. Partial Clone (Corrupted Git Repository)

**Scenario:**

- Repository entry exists in pyproject.toml
- Clone directory exists but `.git` is corrupted

**Behavior with `--force`:**

- Removes entry from pyproject.toml
- Removes entire clone directory (including corrupted `.git`)
- Re-clones repository
- ✅ **Result:** Clean state restored

### 4. Multiple Rapid `--force` Calls

**Scenario:**

```bash
qen add myrepo --force &
qen add myrepo --force &
```

**Behavior:**

- First call: Removes and re-adds
- Second call: Removes and re-adds again
- ✅ **Result:** Both succeed, final state is consistent (idempotent)

**Race condition:** Could leave inconsistent state if both run simultaneously. This is acceptable - user error.

## Design Decisions

### 1. Why `--force` Flag?

**Alternatives considered:**

- Automatic idempotency (always allow re-add)
- Separate `qen remove` command + manual re-add
- `qen reset <repo>` command

**Decision: `--force` flag**

**Rationale:**

- ✅ Explicit opt-in preserves safety
- ✅ Familiar pattern (git, docker, etc.)
- ✅ Single command workflow
- ✅ Clear intent when reading scripts/docs

### 2. Why Remove-Then-Add vs. Update-In-Place?

**Alternative:** Update existing entry without removing

**Decision: Remove-then-add**

**Rationale:**

- ✅ Simpler implementation
- ✅ Guarantees clean state
- ✅ Handles all corruption scenarios
- ✅ Re-uses existing tested add flow
- ✅ More predictable behavior

**Trade-off:** Slightly slower (extra I/O), but acceptable for recovery operation

### 3. Why Not Prompt for Confirmation?

**Alternative:** `--force` triggers interactive "Are you sure?" prompt

**Decision: No prompt**

**Rationale:**

- ✅ Non-interactive by default (script-friendly)
- ✅ `--force` flag is explicit enough
- ✅ Consistent with unix philosophy
- ❌ Could add `--interactive` flag later if needed

## Backwards Compatibility

### Breaking Changes: None

- Default behavior unchanged (still blocks duplicates)
- Existing scripts and workflows continue to work
- No changes to config file format

### Migration: Not Required

This is a purely additive feature. No migration needed.

## Success Criteria

After implementation, the following workflow must succeed:

```bash
# Initial add
$ qen add deployment
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2025-12-05-benchling-stacked
  Path: /path/to/proj/repos/2025-12-05-benchling-stacked/deployment

# Duplicate add WITHOUT --force (blocks as before)
$ qen add deployment
Error: Repository already exists in project: https://github.com/quiltdata/deployment (branch: 2025-12-05-benchling-stacked)
Aborted!

# Duplicate add WITH --force (succeeds)
$ qen add deployment --force
Repository exists. Removing and re-adding with --force...
Removing existing clone at repos/2025-12-05-benchling-stacked/deployment
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2025-12-05-benchling-stacked
  Path: /path/to/proj/repos/2025-12-05-benchling-stacked/deployment

# Multiple --force calls (idempotent)
$ qen add deployment --force
Repository exists. Removing and re-adding with --force...
✓ Added repository: https://github.com/quiltdata/deployment
```

## Future Enhancements

Potential improvements for future versions:

1. **`qen remove <repo>`** - Explicit removal command
2. **`qen reset <repo>`** - Alias for `qen add --force`
3. **`--interactive`** - Confirmation prompt before removal
4. **`--dry-run`** - Show what would be removed without doing it
5. **Backup before removal** - Copy clone to `.qen/backup/` before removing

## References

- Implementation Plan: `/Users/ernest/.claude/plans/replicated-conjuring-scott.md`
- Related Issue: User reported "Repository already exists" blocking recovery
- Similar Feature: `git clone --force` (doesn't exist - git requires manual removal)
- Similar Feature: `docker run --force` (removes existing container first)

## Approval

**Approved by:** User
**Date:** 2025-12-07
**Implementation Status:** Ready for implementation

---

## Appendix A: Remote Branch Tracking Bug

### NEW Problem

**Current Behavior (WRONG):**

When `qen add` clones a repository with a specific branch, it creates a LOCAL-ONLY branch if the remote branch doesn't exist. This causes:

```bash
$ qen add deployment --branch 2025-12-05-benchling-stacked
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2025-12-05-benchling-stacked

$ cd repos/2025-12-05-benchling-stacked/deployment
$ git pull
There is no tracking information for the current branch.
```

**Root Cause:**

In `src/qen/repo_utils.py:176-201`, the code silently creates a local branch when the remote doesn't exist:

```python
# Lines 176-191 - Creates local branch without tracking
if branch and branch != "main" and branch != "master":
    try:
        run_git_command(["checkout", branch], cwd=dest_path)
    except GitError:
        try:
            run_git_command(["checkout", "-b", branch, f"origin/{branch}"], cwd=dest_path)
        except GitError:
            # ❌ BUG: Silently creates local-only branch
            run_git_command(["checkout", "-b", branch], cwd=dest_path)
```

### Correct Behavior

**QEN should ALWAYS use remote branches with tracking:**

1. **Check if remote branch exists** using `git ls-remote`
2. **If remote branch exists**: Checkout with tracking (`git checkout -b branch origin/branch`)
3. **If remote branch does NOT exist**:
   - Prompt user: "Branch 'X' does not exist on remote. Create local branch? [y/N]"
   - If `--yes` flag: Auto-create without prompt
   - If user declines: Abort with error

### Implementation

**File:** `src/qen/repo_utils.py:147-202`

**Updated `clone_repository()` function:**

```python
def clone_repository(
    url: str,
    dest_path: Path,
    branch: str | None = None,
    verbose: bool = False,
    yes: bool = False,  # NEW: Auto-confirm prompts
) -> None:
    """Clone a git repository to a destination path.

    Args:
        url: Git clone URL
        dest_path: Destination path for the clone
        branch: Optional branch to checkout after cloning
        verbose: Enable verbose output
        yes: Auto-confirm prompts (create local branch without asking)

    Raises:
        GitError: If clone fails or destination already exists
    """
    # Check if destination already exists
    if dest_path.exists():
        raise GitError(f"Destination already exists: {dest_path}")

    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone the repository
    clone_args = ["clone", url, str(dest_path)]
    if not verbose:
        clone_args.append("--quiet")

    run_git_command(clone_args)

    # Checkout specific branch if requested
    if branch and branch != "main" and branch != "master":
        # Check if remote branch exists
        remote_branch_exists = check_remote_branch_exists(dest_path, branch)

        if remote_branch_exists:
            # Remote branch exists - checkout with tracking
            try:
                run_git_command(["checkout", "-b", branch, f"origin/{branch}"], cwd=dest_path)
            except GitError as e:
                raise GitError(f"Failed to checkout remote branch '{branch}': {e}") from e
        else:
            # Remote branch does NOT exist - prompt user
            if not yes:
                import click
                if not click.confirm(
                    f"Branch '{branch}' does not exist on remote '{url}'. "
                    f"Create local branch?",
                    default=False
                ):
                    raise GitError(f"Branch '{branch}' does not exist on remote")

            # Create local-only branch (user confirmed or --yes)
            try:
                run_git_command(["checkout", "-b", branch], cwd=dest_path)
                if verbose:
                    import click
                    click.echo(f"Created local-only branch '{branch}' (not on remote)")
            except GitError as e:
                raise GitError(f"Failed to create local branch '{branch}': {e}") from e


def check_remote_branch_exists(repo_path: Path, branch: str) -> bool:
    """Check if a branch exists on the remote repository.

    Args:
        repo_path: Path to local git repository
        branch: Branch name to check

    Returns:
        True if remote branch exists, False otherwise
    """
    try:
        result = run_git_command(
            ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=repo_path,
            capture_output=True
        )
        # If output is non-empty, remote branch exists
        return bool(result.stdout.strip())
    except GitError:
        return False
```

### Updated Call Sites

**File:** `src/qen/commands/add.py`

Update `add_repository()` to accept and pass `yes` parameter:

```python
def add_repository(
    repo: str,
    branch: str | None = None,
    path: str | None = None,
    verbose: bool = False,
    force: bool = False,
    yes: bool = False,  # NEW
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
) -> None:
    """Add a repository to the current project."""
    # ... existing code ...

    # Clone the repository
    clone_repository(url, clone_dest, branch, verbose, yes=yes)  # Pass yes flag
```

**File:** `src/qen/cli.py`

Add `--yes` flag to `qen add` command:

```python
@main.command("add")
@click.argument("repo")
@click.option("--branch", "-b", help="Branch to track (default: main)")
@click.option("--path", "-p", help="Local path (default: repos/<name>)")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("--force", is_flag=True, help="Force re-add if repository exists")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm prompts")  # NEW
def add(repo: str, branch: str | None, path: str | None, verbose: bool, force: bool, yes: bool) -> None:
    """Add a repository to the current project."""
    add_repository(repo, branch, path, verbose, force, yes)
```

### Phase Success Criteria

After implementation:

#### **Scenario 1: Remote branch exists**

```bash
$ qen add deployment --branch feature-123
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: feature-123 (tracking origin/feature-123)

$ cd repos/feature-123/deployment
$ git pull  # ✅ Works! Has tracking info
```

#### **Scenario 2: Remote branch does NOT exist (interactive)**

```bash
$ qen add deployment --branch new-feature
Branch 'new-feature' does not exist on remote 'https://github.com/quiltdata/deployment'.
Create local branch? [y/N]: y
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: new-feature (local only - push to create remote)
```

#### **Scenario 3: Remote branch does NOT exist (auto-confirm)**

```bash
$ qen add deployment --branch new-feature --yes
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: new-feature (local only - push to create remote)
```

#### **Scenario 4: Remote branch does NOT exist (user declines)**

```bash
$ qen add deployment --branch new-feature
Branch 'new-feature' does not exist on remote 'https://github.com/quiltdata/deployment'.
Create local branch? [y/N]: n
Error: Branch 'new-feature' does not exist on remote
Aborted!
```

### Testing

**Unit Tests** (`tests/unit/qen/test_repo_utils.py`):

- `test_check_remote_branch_exists_true` - Remote branch exists
- `test_check_remote_branch_exists_false` - Remote branch doesn't exist
- `test_clone_with_remote_branch` - Checkout remote branch with tracking
- `test_clone_with_nonexistent_branch_prompt_yes` - User confirms local branch
- `test_clone_with_nonexistent_branch_prompt_no` - User declines, operation aborts
- `test_clone_with_nonexistent_branch_yes_flag` - Auto-confirm with --yes

**Integration Tests** (`tests/integration/test_add_branches.py`):

- Test adding repo with existing remote branch
- Test adding repo with non-existent branch (using --yes flag in tests)
- Verify tracking info is set correctly

### Related Issues

- Fixes issue where `git pull` fails after `qen add` due to missing tracking info
- Aligns with QEN philosophy: "Always work with remote branches, never local-only"
- Prevents confusion when branches diverge without user awareness
