# qen rm - Safe Repository Removal

## Overview

The `qen rm` command safely removes repositories from a qen project by:

1. **Safety checks** - Prompt if repository has unpushed/unmerged changes
2. **Config cleanup** - Remove entry from `pyproject.toml`
3. **Filesystem cleanup** - Delete repository directory from `repos/`
4. **Workspace update** - Regenerate workspace files (unless `--no-workspace`)

## Command Design

### Basic Usage

```bash
# Remove repository by URL
qen rm https://github.com/org/repo

# Remove repository by index (from qen status)
qen rm 1

# Remove multiple repositories
qen rm 1 3 5

# Force removal without safety checks
qen rm 2 --force

# Remove but skip workspace regeneration
qen rm 3 --no-workspace
```

### Command Signature

```python
@click.command()
@click.argument("repos", nargs=-1, required=True)
@click.option("--force", "-f", is_flag=True, help="Force removal without safety checks")
@click.option("--yes", "-y", is_flag=True, help="Auto-confirm all prompts")
@click.option("--no-workspace", is_flag=True, help="Skip workspace file regeneration")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def rm(repos: tuple[str, ...], force: bool, yes: bool, no_workspace: bool, verbose: bool) -> None:
    """Remove repositories from the current project.

    REPOS can be:
    - Repository indices (1-based): qen rm 1 3 5
    - Repository URLs: qen rm https://github.com/org/repo
    - Repository org/name: qen rm org/repo
    - Repository name: qen rm repo (requires org in config)

    Safety checks:
    - Warns about unpushed commits (ahead of remote)
    - Warns about uncommitted changes (modified/staged/untracked)
    - Warns about unmerged PRs (PR status != merged)

    Use --force to skip all safety checks.
    Use --yes to auto-confirm prompts.
    """
```

## Implementation Flow

### Phase 1: Parse and Validate Arguments

```python
def parse_repo_identifiers(
    repos: tuple[str, ...],
    project_dir: Path,
    org: str | None
) -> list[RepoToRemove]:
    """Parse repository identifiers into removal targets.

    Args:
        repos: Tuple of repository identifiers (indices, URLs, names)
        project_dir: Path to project directory
        org: Default organization from config

    Returns:
        List of RepoToRemove objects with:
        - index: 1-based index in pyproject.toml
        - url: Repository URL
        - branch: Branch name
        - path: Local path
        - repo_entry: Full repo dict from pyproject.toml

    Raises:
        RepositoryNotFoundError: If identifier doesn't match any repo
        AmbiguousIdentifierError: If identifier matches multiple repos
    """
```

**Identifier Resolution Logic:**

1. **Integer strings** → Treat as 1-based indices
   - `"1"` → First repo in `[[tool.qen.repos]]`
   - `"5"` → Fifth repo
   - Error if index out of range

2. **Full URLs** → Match by exact URL
   - `"https://github.com/org/repo"` → Match `url` field
   - `"git@github.com:org/repo.git"` → Normalize and match

3. **org/repo format** → Parse and match
   - `"data-yaml/qen"` → Match org and repo name
   - Error if multiple branches of same repo

4. **repo name only** → Use org from config
   - `"qen"` → Use `config.org` + repo name
   - Error if no org in config or multiple branches

### Phase 2: Safety Checks

```python
@dataclass
class SafetyCheck:
    """Safety check result for a repository."""

    repo_url: str
    repo_branch: str
    has_unpushed: bool = False
    has_uncommitted: bool = False
    has_unmerged_pr: bool = False
    unpushed_count: int = 0
    uncommitted_files: list[str] = field(default_factory=list)
    pr_number: int | None = None
    pr_status: str | None = None

    def is_safe(self) -> bool:
        """Check if removal is safe without --force."""
        return not (self.has_unpushed or self.has_uncommitted or self.has_unmerged_pr)

    def warning_message(self) -> str:
        """Generate warning message for unsafe removal."""
        parts = []
        if self.has_unpushed:
            parts.append(f"{self.unpushed_count} unpushed commit(s)")
        if self.has_uncommitted:
            parts.append(f"{len(self.uncommitted_files)} uncommitted file(s)")
        if self.has_unmerged_pr:
            parts.append(f"unmerged PR #{self.pr_number} ({self.pr_status})")
        return ", ".join(parts)


def check_repo_safety(repo_path: Path, repo_entry: dict[str, Any]) -> SafetyCheck:
    """Perform safety checks on a repository before removal.

    Checks:
    1. Unpushed commits - git rev-list @{upstream}..HEAD
    2. Uncommitted changes - git status --porcelain
    3. Unmerged PRs - pr_status field != "merged"

    Args:
        repo_path: Path to repository directory
        repo_entry: Repository entry from pyproject.toml

    Returns:
        SafetyCheck object with all check results
    """
```

**Safety Check Details:**

1. **Unpushed Commits Check**
   - Use `get_sync_status(repo_path)` from [git_utils.py](../src/qen/git_utils.py:470-506)
   - Flag if `sync.ahead > 0`

2. **Uncommitted Changes Check**
   - Use `get_repo_status(repo_path)` from [git_utils.py](../src/qen/git_utils.py:509-569)
   - Flag if any of: `modified`, `staged`, `untracked` non-empty

3. **Unmerged PR Check**
   - Read `pr_status` from `repo_entry`
   - Flag if PR exists and status is not `"merged"`
   - Show PR number if available

### Phase 3: User Confirmation

```python
def confirm_removal(
    repos_to_remove: list[RepoToRemove],
    safety_checks: dict[str, SafetyCheck],
    force: bool,
    yes: bool
) -> bool:
    """Confirm removal with user, showing safety warnings.

    Args:
        repos_to_remove: List of repositories to remove
        safety_checks: Map of repo URL to SafetyCheck result
        force: Skip safety checks (still show summary)
        yes: Auto-confirm without prompt

    Returns:
        True if user confirms removal
    """
```

**Confirmation Display:**

```text
Will remove 3 repositories:

[1] https://github.com/org/repo1 (main)
    Path: repos/repo1
    ⚠️  2 unpushed commits, 3 uncommitted files

[3] https://github.com/org/repo2 (feature-branch)
    Path: repos/repo2
    ⚠️  unmerged PR #42 (open)

[5] https://github.com/org/repo3 (main)
    Path: repos/repo3
    ✓ Safe to remove

Remove these repositories? [y/N]: _
```

**Behavior:**

- With `--force`: Show summary, skip safety warnings, still prompt unless `--yes`
- With `--yes`: Auto-confirm, no prompt
- With `--force --yes`: Skip everything, immediate removal
- Without flags: Show warnings, require confirmation

### Phase 4: Removal Execution

```python
def remove_repository(
    repo: RepoToRemove,
    project_dir: Path,
    verbose: bool = False
) -> None:
    """Remove repository from config and filesystem.

    Steps:
    1. Remove entry from pyproject.toml via remove_repo_from_pyproject()
    2. Remove repository directory via shutil.rmtree()
    3. Handle errors gracefully (log but continue)

    Args:
        repo: Repository to remove
        project_dir: Project directory
        verbose: Enable verbose output

    Raises:
        PyProjectUpdateError: If config update fails (fatal)
        OSError: If directory removal fails (non-fatal, warn and continue)
    """
```

**Error Handling:**

- **Config update fails** → Fatal error, abort entire operation
- **Directory removal fails** → Warn, continue with next repo
- **Directory already gone** → Log if verbose, continue
- **Partial failure** → Remove what we can, report errors at end

### Phase 5: Workspace Update

```python
def update_workspace_after_removal(
    project_dir: Path,
    current_project: str,
    no_workspace: bool,
    verbose: bool
) -> None:
    """Regenerate workspace files after repository removal.

    Uses the same logic as qen add command:
    - Read updated repos from pyproject.toml
    - Call create_workspace_files() with new repo list
    - Non-fatal: warn if regeneration fails

    Args:
        project_dir: Project directory
        current_project: Current project name
        no_workspace: Skip workspace regeneration
        verbose: Enable verbose output
    """
```

## User Experience Examples

### Example 1: Safe Removal

```bash
$ qen rm 2

Will remove 1 repository:

[2] https://github.com/data-yaml/qen-test (main)
    Path: repos/qen-test
    ✓ Safe to remove

Remove this repository? [y/N]: y

✓ Removed repository: https://github.com/data-yaml/qen-test
  Removed: repos/qen-test
  Updated: pyproject.toml
  Updated: workspace files

Next steps:
  - Commit changes: git add pyproject.toml && git commit -m "Remove qen-test"
```

### Example 2: Unsafe Removal (Uncommitted Changes)

```bash
$ qen rm 3

Will remove 1 repository:

[3] https://github.com/org/myrepo (feature-branch)
    Path: repos/myrepo
    ⚠️  2 unpushed commits, 5 uncommitted files:
        - src/main.py (modified)
        - tests/test_new.py (untracked)
        - README.md (staged)
        ... and 2 more

This repository has uncommitted/unpushed work that will be lost!

Remove this repository? [y/N]: n

Aborted. No repositories were removed.

Tip: Use --force to skip safety checks, or commit/push your changes first.
```

### Example 3: Unmerged PR Warning

```bash
$ qen rm 1

Will remove 1 repository:

[1] https://github.com/org/myrepo (pr-branch)
    Path: repos/myrepo
    ⚠️  unmerged PR #123 (open)
        View PR: https://github.com/org/myrepo/pull/123

This repository has an open PR that has not been merged!

Remove this repository? [y/N]: n

Aborted. No repositories were removed.

Tip: Use --force to skip this check.
```

### Example 4: Force Removal

```bash
$ qen rm 2 --force

Will remove 1 repository:

[2] https://github.com/org/myrepo (main)
    Path: repos/myrepo
    (skipped safety checks due to --force)

Remove this repository? [y/N]: y

✓ Removed repository: https://github.com/org/myrepo
  Warning: Repository had uncommitted changes that were deleted
  Removed: repos/myrepo
  Updated: pyproject.toml
  Updated: workspace files
```

### Example 5: Batch Removal

```bash
$ qen rm 1 3 5 --yes

Removing 3 repositories...

✓ Removed [1]: https://github.com/org/repo1
✓ Removed [3]: https://github.com/org/repo2
✓ Removed [5]: https://github.com/org/repo3

Updated pyproject.toml
Updated workspace files

Next steps:
  - Commit changes: git add pyproject.toml && git commit -m "Remove 3 repositories"
```

### Example 6: Error Handling

```bash
$ qen rm 2

Removing 1 repository...

✓ Updated pyproject.toml
✗ Failed to remove repos/myrepo: Permission denied

Repository entry removed from config, but directory could not be deleted.
You may need to manually remove: /path/to/proj/repos/myrepo

Updated workspace files
```

## Integration with Existing Code

### Reuse from [add.py](../src/qen/commands/add.py)

```python
# Reuse remove_existing_repo() logic (lines 52-80)
# But add safety checks before calling it

# Reuse workspace regeneration pattern (lines 292-329)
# Call create_workspace_files() after removal
```

### Reuse from [pyproject_utils.py](../src/qen/pyproject_utils.py)

```python
# Use remove_repo_from_pyproject() for config cleanup (line 218)
# Use load_repos_from_pyproject() to enumerate repos (line 71)
```

### Reuse from [git_utils.py](../src/qen/git_utils.py)

```python
# Use get_sync_status() to check unpushed commits (line 470)
# Use get_repo_status() to check uncommitted changes (line 509)
```

## Testing Strategy

### Unit Tests ([tests/unit/qen/commands/test_rm.py](../../tests/unit/qen/commands/))

1. **Identifier Parsing**
   - Test index resolution (1-based)
   - Test URL matching (exact and normalized)
   - Test org/repo format
   - Test repo name with org from config
   - Test error cases (not found, ambiguous)

2. **Safety Checks**
   - Mock git status to simulate unpushed commits
   - Mock git status to simulate uncommitted changes
   - Mock PR status from pyproject.toml
   - Test SafetyCheck.is_safe() logic
   - Test warning message generation

3. **User Confirmation**
   - Mock click.confirm() for prompt testing
   - Test --force skips checks
   - Test --yes skips prompt
   - Test --force --yes behavior

4. **Removal Logic**
   - Mock pyproject.toml updates
   - Mock filesystem operations
   - Test partial failure handling
   - Test error reporting

5. **Workspace Updates**
   - Mock workspace file regeneration
   - Test --no-workspace flag

### Integration Tests ([tests/integration/test_rm_real.py](../../tests/integration/))

**IMPORTANT:** Integration tests MUST use real GitHub API, no mocks.

1. **Setup Test Environment**

   ```python
   @pytest.fixture
   def test_project_with_repos(tmp_path, real_test_repo):
       """Create test project with multiple repos added."""
       # Initialize qen project
       # Add 3 repos from qen-test with different branches
       # Return project_dir and repo list
   ```

2. **Test Safe Removal**

   ```python
   def test_rm_clean_repo(test_project_with_repos):
       """Remove repository with no uncommitted changes."""
       # Add repo, commit everything
       # Run qen rm --yes
       # Verify config updated, directory removed
   ```

3. **Test Uncommitted Changes Warning**

   ```python
   def test_rm_warns_uncommitted(test_project_with_repos):
       """Warn when removing repo with uncommitted changes."""
       # Add repo, make changes, don't commit
       # Run qen rm without --force (should prompt)
       # Test that --force bypasses check
   ```

4. **Test Unpushed Commits Warning**

   ```python
   def test_rm_warns_unpushed(test_project_with_repos):
       """Warn when removing repo with unpushed commits."""
       # Add repo, make commits, don't push
       # Run qen rm (should warn about ahead status)
       # Test that --force bypasses check
   ```

5. **Test Unmerged PR Detection**

   ```python
   def test_rm_warns_unmerged_pr(test_project_with_repos):
       """Warn when removing repo with unmerged PR."""
       # Add repo with PR branch
       # Ensure pr_status != "merged" in config
       # Run qen rm (should warn about open PR)
       # Test that --force bypasses check
   ```

6. **Test Batch Removal**

   ```python
   def test_rm_multiple_repos(test_project_with_repos):
       """Remove multiple repositories in one command."""
       # Add 3 repos
       # Run qen rm 1 2 3 --yes
       # Verify all removed, workspace updated once
   ```

7. **Test Index-Based Removal**

   ```python
   def test_rm_by_index(test_project_with_repos):
       """Remove repository by 1-based index."""
       # Add 3 repos
       # Run qen rm 2 --yes
       # Verify correct repo removed
   ```

8. **Test Error Recovery**

   ```python
   def test_rm_handles_missing_directory(test_project_with_repos):
       """Handle case where directory already deleted."""
       # Add repo
       # Manually delete repos/ directory
       # Run qen rm (should update config, warn about missing dir)
   ```

## File Structure

```text
src/qen/commands/
├── rm.py                    # New command implementation

tests/unit/qen/commands/
├── test_rm.py              # Unit tests with mocks

tests/integration/
├── test_rm_real.py         # Integration tests (NO MOCKS)

spec/4-tests/
└── qen-rm-command.md       # This specification
```

## Success Criteria

### Implementation Checklist

- [ ] Implement `parse_repo_identifiers()` with all identifier types
- [ ] Implement `check_repo_safety()` with all three safety checks
- [ ] Implement `confirm_removal()` with clear warning display
- [ ] Implement `remove_repository()` with error handling
- [ ] Implement workspace file regeneration after removal
- [ ] Add `rm` command to CLI in [cli.py](../src/qen/cli.py)
- [ ] Handle --force, --yes, --no-workspace flags correctly
- [ ] Support batch removal (multiple repos in one command)

### Testing Checklist

- [ ] Unit tests for identifier parsing (all formats)
- [ ] Unit tests for safety checks (all three conditions)
- [ ] Unit tests for confirmation logic (all flag combinations)
- [ ] Unit tests for removal logic (success and error cases)
- [ ] Integration test for safe removal (clean repo)
- [ ] Integration test for uncommitted changes warning
- [ ] Integration test for unpushed commits warning
- [ ] Integration test for unmerged PR detection
- [ ] Integration test for batch removal
- [ ] Integration test for index-based removal
- [ ] Integration test for error recovery (missing directory)
- [ ] All tests pass: `./poe test-all`

### User Experience Checklist

- [ ] Clear warning messages for unsafe removals
- [ ] Helpful error messages for invalid identifiers
- [ ] Next steps guidance after removal
- [ ] Consistent with `qen add` patterns
- [ ] Works with `--verbose` for debugging
- [ ] Handles edge cases gracefully (no crash)

## References

### Related Code

- [src/qen/commands/add.py](../src/qen/commands/add.py:52-80) - `remove_existing_repo()` pattern
- [src/qen/pyproject_utils.py](../src/qen/pyproject_utils.py:218-277) - `remove_repo_from_pyproject()`
- [src/qen/git_utils.py](../src/qen/git_utils.py:470-569) - Git status utilities

### Related Specs

- [spec/1-qen-init/3-pyproject.md](../1-qen-init/3-pyproject.md) - pyproject.toml schema
- [spec/2-status/01-qen-pull.md](../2-status/01-qen-pull.md) - PR status metadata
- [spec/3-proj/03-add-force-idempotent.md](../3-proj/03-add-force-idempotent.md) - Force flag patterns

---

*This specification follows the testing philosophy from [AGENTS.md](../../AGENTS.md):*
*Unit tests use mocks for speed, integration tests NEVER use mocks.*
