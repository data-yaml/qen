# qen commit - Commit Changes Across Repositories

## Overview

`qen commit` commits changes across all sub-repositories within a QEN project. It provides a convenient way to commit related changes in multiple repositories with consistent commit messages, while still allowing per-repository customization when needed.

## Command Behavior

### Basic Usage

```bash
qen commit -m "Fix authentication bug"              # Commit all dirty repos
qen commit -m "Add feature" --repo repos/api        # Commit specific repo
qen commit -m "Update docs" --amend                 # Amend previous commits
qen commit --interactive                            # Interactive mode
```

**Note:** `qen commit` only commits repositories that have uncommitted changes. Clean repositories are skipped.

### What It Does

1. **Locates current project** - Uses default project from qen config
2. **Discovers all sub-repositories** - Reads `pyproject.toml` to find repos in `[tool.qen.repos]`
3. **Identifies dirty repos** - Finds repos with uncommitted changes (modified, staged, or untracked)
4. **Stages changes** - Runs `git add -A` to stage all changes (unless `--no-add`)
5. **Creates commits** - Commits staged changes with provided message
6. **Updates metadata** - Updates `updated` timestamp in `pyproject.toml`
7. **Displays summary** - Shows what was committed across all repositories

## Repository State Requirements

### What Gets Committed

`qen commit` handles all types of changes:

1. **Modified files** - Tracked files with changes
2. **Staged files** - Files already staged with `git add`
3. **Untracked files** - New files not yet tracked (with `git add -A`)
4. **Deleted files** - Files removed from working directory

### Skip Clean Repositories

- Repositories without changes are automatically skipped
- Only "dirty" repos with uncommitted changes are processed
- Clear indication in output which repos were skipped

## Output Format

### Summary View

```log
Committing project: feature-work

📦 example-repo (feature/my-work)
   3 files changed: 2 modified, 1 added
   ✓ Committed: "Fix authentication bug"

📦 another-repo (main)
   • No changes to commit (clean)

📦 third-repo (bugfix/issue-456)
   1 file changed: 1 modified
   ✓ Committed: "Fix authentication bug"

Summary:
  3 repositories processed
  2 repositories committed
  1 repository clean (no changes)
```

### Interactive Mode

```log
Committing project: feature-work (interactive mode)

📦 example-repo (feature/my-work)
   3 files changed:
     M src/auth.py
     M tests/test_auth.py
     A docs/auth.md

   Commit this repository? [Y/n/e/s] y
   Commit message (or Enter for default): Fix auth token validation
   ✓ Committed: "Fix auth token validation"

📦 third-repo (bugfix/issue-456)
   1 file changed:
     M src/utils.py

   Commit this repository? [Y/n/e/s] e
   [Opens editor for custom commit message]
   ✓ Committed: "Refactor utility functions

   - Extract common validation logic
   - Add type hints
   - Update docstrings"

Summary:
  2 repositories committed
  1 repository skipped
```

## Commit Message Strategies

### Single Message (Default)

```bash
qen commit -m "Fix authentication bug"
```

All dirty repositories get the same commit message. Simple and fast for related changes.

### Interactive Mode

```bash
qen commit --interactive
# or
qen commit -i
```

Prompts for each repository:
- Review changes
- Decide whether to commit
- Customize commit message per repo
- Open editor for detailed messages

### Per-Repository Messages

```bash
# Commit with custom messages per repo
qen commit --interactive -m "Default message for all"
```

Uses default message as fallback, but allows customization in interactive mode.

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `-m, --message <msg>` | Commit message for all repos | required* |
| `-i, --interactive` | Interactive mode (prompt per repo) | false |
| `--amend` | Amend previous commit in each repo | false |
| `--no-add` | Don't auto-stage changes (commit staged only) | false |
| `--allow-empty` | Allow empty commits | false |
| `--repo <name>` | Commit only specific repository | all |
| `--dry-run` | Show what would be committed | false |
| `--verbose` | Show detailed diff for each repo | false |

\* `-m` is required unless `--interactive` is used

### Flag Usage Notes

**`--interactive`**: Interactive mode for fine-grained control

- Review changes in each repo before committing
- Customize commit message per repository
- Skip repos selectively
- Options per repo: `[Y/n/e/s]`
  - `Y` - Commit with default message (or prompted message)
  - `n` - Skip this repository
  - `e` - Open editor for custom message
  - `s` - Show detailed diff first

**`--amend`**: Amend previous commits

- Amends the most recent commit in each dirty repo
- Useful for "oops, forgot to include this file" scenarios
- **Warning**: Don't amend commits already pushed to remote
- Requires confirmation in interactive mode

**`--no-add`**: Only commit staged changes

- Doesn't run `git add -A` automatically
- Only commits files already staged with `git add`
- Useful when you've carefully staged specific changes
- Untracked files are ignored

**`--allow-empty`**: Allow commits with no changes

- Useful for triggering CI/CD pipelines
- Or recording notes in commit history
- By default, empty commits are rejected

## Error Handling

### Scenarios to Handle

1. **No uncommitted changes** - Skip repo, not an error
2. **Merge in progress** - Error, cannot commit during merge
3. **Rebase in progress** - Error, cannot commit during rebase
4. **Detached HEAD** - Error, checkout a branch first
5. **No commit message** - Error in non-interactive mode
6. **Commit hook failure** - Show hook output, mark repo as failed

### Error Examples

```log
📦 example-repo (feature/my-work)
   ✗ Merge in progress
   Suggestion: Complete or abort merge first (git merge --abort)

📦 another-repo (detached HEAD)
   ✗ Cannot commit from detached HEAD
   Suggestion: Checkout a branch first (git checkout main)

📦 third-repo (bugfix/issue-456)
   ✗ Pre-commit hook failed
   [hook output shown here]
```

## Integration Points

### With Other Commands

- `qen push` - Push commits after committing
- `qen status` - Check which repos have uncommitted changes
- `qen pull` - Pull before committing to get latest changes

### External Tools

- **git** - Required. All git operations via subprocess calls to git CLI.
- **git hooks** - Pre-commit hooks run normally (can fail commit)
- **editor** - Uses `$EDITOR` or `$GIT_EDITOR` for interactive mode

## Configuration

### Project-Level Settings (Optional)

```toml
[tool.qen.commit]
auto_add = true                         # Auto-stage changes (git add -A)
interactive_default = false             # Default to interactive mode
require_sign_off = false                # Add Signed-off-by line
parallel = false                        # Commit repos in parallel (advanced)
```

### Global Settings (Optional)

```toml
[commit]
default_editor = "vim"                  # Editor for interactive mode
require_message = true                  # Require commit message (no default)
```

## Success Criteria

### Must Accomplish

1. **Commit all dirty repos** - Successfully commit each repo with uncommitted changes
2. **Skip clean repos** - Don't attempt to commit repos without changes
3. **Handle commit failures** - One repo failure doesn't stop others
4. **Show clear summary** - User understands what was committed and what failed
5. **Respect git hooks** - Pre-commit hooks run normally

### Should Accomplish

1. **Interactive mode** - Allow per-repo customization
2. **Flexible staging** - Support both auto-add and manual staging
3. **Amend support** - Allow amending previous commits
4. **Smart error messages** - Suggest fixes for common issues

### Nice to Have

1. **Parallel commits** - Commit multiple repos concurrently
2. **Commit templates** - Support for commit message templates
3. **Conventional commits** - Optional conventional commit format validation

## Non-Goals

- **Not a git wrapper** - Don't replicate all git commit options
- **Not an interactive rebase** - Don't modify commit history (except --amend)
- **Not a staging tool** - Don't provide granular staging UI (use git add for that)
- **Not a commit message validator** - Don't enforce commit message format (use git hooks)

## Design Decisions

1. **Auto-stage by default** - `git add -A` unless `--no-add` (convenience over safety)
2. **Skip clean repos** - Don't create empty commits by default
3. **Same message for all** - Default mode uses one message (simplicity)
4. **Interactive for customization** - Use `--interactive` for per-repo control
5. **Respect git hooks** - All hooks run normally (don't bypass)

## Implementation Details

### Commit Operation

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class CommitResult:
    success: bool
    files_changed: int
    message: str
    skipped: bool = False
    error_message: str | None = None
    no_changes: bool = False

def commit_repo(
    repo_path: Path,
    message: str,
    amend: bool = False,
    no_add: bool = False,
    allow_empty: bool = False,
) -> CommitResult:
    """Commit changes in a repository."""

    # Check for special git states
    if is_merge_in_progress(repo_path):
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Merge in progress. Complete or abort merge first.",
        )

    if is_rebase_in_progress(repo_path):
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Rebase in progress. Complete or abort rebase first.",
        )

    # Check for detached HEAD
    try:
        branch = run_git_command(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
        ).strip()
        if branch == "HEAD":
            return CommitResult(
                success=False,
                files_changed=0,
                message="",
                error_message="Detached HEAD. Checkout a branch first.",
            )
    except GitError:
        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message="Cannot determine current branch.",
        )

    # Stage changes if auto-add enabled
    if not no_add:
        try:
            run_git_command(["add", "-A"], cwd=repo_path)
        except GitError as e:
            return CommitResult(
                success=False,
                files_changed=0,
                message="",
                error_message=f"Failed to stage changes: {e}",
            )

    # Check if there are changes to commit
    try:
        status = run_git_command(
            ["status", "--porcelain", "--untracked-files=no"],
            cwd=repo_path,
        )
        if not status.strip() and not allow_empty:
            return CommitResult(
                success=True,
                files_changed=0,
                message="",
                no_changes=True,
            )
    except GitError:
        pass  # Continue anyway

    # Count files changed
    files_changed = count_files_changed(repo_path)

    # Build commit command
    cmd = ["commit", "-m", message]
    if amend:
        cmd.append("--amend")
    if allow_empty:
        cmd.append("--allow-empty")

    # Commit
    try:
        run_git_command(cmd, cwd=repo_path)

        return CommitResult(
            success=True,
            files_changed=files_changed,
            message=message,
        )

    except GitError as e:
        # Check if it's a hook failure
        if "hook" in e.stderr.lower():
            error_msg = f"Pre-commit hook failed:\n{e.stderr}"
        else:
            error_msg = f"Commit failed: {e.stderr}"

        return CommitResult(
            success=False,
            files_changed=0,
            message="",
            error_message=error_msg,
        )

def count_files_changed(repo_path: Path) -> int:
    """Count number of files changed (staged for commit)."""
    try:
        result = run_git_command(
            ["diff", "--cached", "--numstat"],
            cwd=repo_path,
        )
        lines = result.strip().split("\n")
        return len([line for line in lines if line])
    except GitError:
        return 0

def is_merge_in_progress(repo_path: Path) -> bool:
    """Check if merge is in progress."""
    return (repo_path / ".git" / "MERGE_HEAD").exists()

def is_rebase_in_progress(repo_path: Path) -> bool:
    """Check if rebase is in progress."""
    git_dir = repo_path / ".git"
    return (
        (git_dir / "rebase-merge").exists() or
        (git_dir / "rebase-apply").exists()
    )
```

### Interactive Mode

```python
def commit_interactive(
    project_name: str,
    default_message: str | None = None,
    amend: bool = False,
    no_add: bool = False,
) -> CommitSummary:
    """Commit repositories interactively."""

    config = load_project_config(project_name)
    meta_path = Path(config.meta_path)
    project_dir = meta_path / config.folder

    repos = load_repos_from_pyproject(project_dir)
    results = []

    print(f"Committing project: {config.name} (interactive mode)\n")

    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Check if repo has changes
        if not has_uncommitted_changes(repo_path):
            continue

        print(f"\n📦 {repo_name} ({repo_config.branch})")

        # Show changes
        show_changes_summary(repo_path)

        # Prompt user
        choice = input("\n   Commit this repository? [Y/n/e/s] ").strip().lower()

        if choice == "n":
            print("   Skipped")
            results.append((repo_name, CommitResult(
                success=True,
                files_changed=0,
                message="",
                skipped=True,
            )))
            continue

        if choice == "s":
            # Show detailed diff
            show_detailed_diff(repo_path)
            choice = input("\n   Commit this repository? [Y/n/e] ").strip().lower()
            if choice == "n":
                print("   Skipped")
                results.append((repo_name, CommitResult(
                    success=True,
                    files_changed=0,
                    message="",
                    skipped=True,
                )))
                continue

        # Get commit message
        if choice == "e":
            message = get_message_from_editor(repo_path, default_message)
        elif default_message:
            use_default = input(f"   Use default message? [Y/n] ").strip().lower()
            if use_default != "n":
                message = default_message
            else:
                message = input("   Commit message: ").strip()
        else:
            message = input("   Commit message: ").strip()

        if not message:
            print("   ✗ No commit message provided. Skipped.")
            results.append((repo_name, CommitResult(
                success=False,
                files_changed=0,
                message="",
                error_message="No message provided",
            )))
            continue

        # Commit
        result = commit_repo(
            repo_path,
            message,
            amend=amend,
            no_add=no_add,
        )

        if result.success:
            print(f"   ✓ Committed: \"{message}\"")
        else:
            print(f"   ✗ {result.error_message}")

        results.append((repo_name, result))

    return print_commit_summary(results)

def show_changes_summary(repo_path: Path) -> None:
    """Show summary of changes in repository."""
    try:
        status = run_git_command(
            ["status", "--short"],
            cwd=repo_path,
        )
        lines = status.strip().split("\n")
        print(f"   {len(lines)} files changed:")
        for line in lines[:10]:  # Show first 10 files
            print(f"     {line}")
        if len(lines) > 10:
            print(f"     ... and {len(lines) - 10} more")
    except GitError:
        print("   (Cannot determine changes)")

def show_detailed_diff(repo_path: Path) -> None:
    """Show detailed diff of changes."""
    try:
        diff = run_git_command(
            ["diff", "HEAD"],
            cwd=repo_path,
        )
        print("\n" + diff)
    except GitError:
        print("   (Cannot show diff)")

def get_message_from_editor(repo_path: Path, default: str | None) -> str:
    """Open editor to get commit message."""
    import tempfile
    import subprocess
    import os

    # Create temp file with default message
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        if default:
            f.write(default + "\n")
        f.write("\n# Enter commit message above\n")
        temp_path = f.name

    try:
        # Open editor
        editor = os.environ.get("GIT_EDITOR") or os.environ.get("EDITOR", "vi")
        subprocess.run([editor, temp_path], check=True)

        # Read message
        with open(temp_path) as f:
            lines = [line for line in f.readlines() if not line.startswith("#")]
            message = "".join(lines).strip()

        return message
    finally:
        os.unlink(temp_path)
```

### Commit Orchestration

```python
def commit_project(
    project_name: str,
    message: str | None = None,
    interactive: bool = False,
    amend: bool = False,
    no_add: bool = False,
    allow_empty: bool = False,
    specific_repo: str | None = None,
    dry_run: bool = False,
) -> CommitSummary:
    """Commit all repositories in a project."""

    # Validate arguments
    if not interactive and not message:
        raise ValueError("Commit message required (use -m or --interactive)")

    # Interactive mode
    if interactive:
        return commit_interactive(
            project_name,
            default_message=message,
            amend=amend,
            no_add=no_add,
        )

    # Load project configuration
    config = load_project_config(project_name)
    meta_path = Path(config.meta_path)
    project_dir = meta_path / config.folder

    repos = load_repos_from_pyproject(project_dir)
    results = []

    print(f"Committing project: {config.name}\n")

    for repo_config in repos:
        repo_path = project_dir / repo_config.path
        repo_name = repo_config.path

        # Skip if specific repo requested and this isn't it
        if specific_repo and repo_name != specific_repo:
            continue

        print(f"📦 {repo_name} ({repo_config.branch})")

        # Check if repo has changes
        if not has_uncommitted_changes(repo_path):
            print("   • No changes to commit (clean)")
            results.append((repo_name, CommitResult(
                success=True,
                files_changed=0,
                message="",
                no_changes=True,
            )))
            continue

        if dry_run:
            # Count files without committing
            files = count_files_to_commit(repo_path, no_add)
            print(f"   Would commit: {files} files")
            results.append((repo_name, CommitResult(
                success=True,
                files_changed=files,
                message=message or "",
            )))
        else:
            # Actually commit
            result = commit_repo(
                repo_path,
                message or "",
                amend=amend,
                no_add=no_add,
                allow_empty=allow_empty,
            )

            if result.success and not result.no_changes:
                print(f"   {result.files_changed} files changed")
                print(f"   ✓ Committed: \"{message}\"")

                # Update metadata timestamp
                update_repo_metadata(project_dir, repo_name, {
                    "updated": datetime.utcnow().isoformat() + "Z"
                })
            elif result.no_changes:
                print("   • No changes to commit (clean)")
            else:
                print(f"   ✗ {result.error_message}")

            results.append((repo_name, result))

    # Print summary
    return print_commit_summary(results, dry_run=dry_run)

def count_files_to_commit(repo_path: Path, no_add: bool) -> int:
    """Count files that would be committed."""
    try:
        if not no_add:
            # Would run git add -A, count all changes
            status = run_git_command(
                ["status", "--porcelain"],
                cwd=repo_path,
            )
        else:
            # Only staged changes
            status = run_git_command(
                ["diff", "--cached", "--name-only"],
                cwd=repo_path,
            )
        lines = status.strip().split("\n")
        return len([line for line in lines if line])
    except GitError:
        return 0
```

## Error Conditions

- **No current project**: "No current project. Run 'qen init <project>' or use --project flag."
- **No commit message**: "Commit message required. Use -m or --interactive."
- **Merge in progress**: "Merge in progress in <repo>. Complete or abort merge first."
- **Rebase in progress**: "Rebase in progress in <repo>. Complete or abort rebase first."
- **Detached HEAD**: "Cannot commit from detached HEAD in <repo>. Checkout a branch first."
- **Pre-commit hook failed**: "Pre-commit hook failed in <repo>: [hook output]"
- **Staging failed**: "Failed to stage changes in <repo>: [error message]"

## Examples

### Example 1: Basic commit

```bash
$ qen commit -m "Fix authentication bug"
Committing project: feature-work

📦 example-repo (feature/my-work)
   3 files changed
   ✓ Committed: "Fix authentication bug"

📦 another-repo (main)
   • No changes to commit (clean)

📦 third-repo (bugfix/issue-456)
   1 file changed
   ✓ Committed: "Fix authentication bug"

Summary:
  3 repositories processed
  2 repositories committed (4 files total)
  1 repository clean
```

### Example 2: Interactive mode

```bash
$ qen commit --interactive
Committing project: feature-work (interactive mode)

📦 example-repo (feature/my-work)
   3 files changed:
     M src/auth.py
     M tests/test_auth.py
     A docs/auth.md

   Commit this repository? [Y/n/e/s] y
   Commit message: Fix auth token validation
   ✓ Committed: "Fix auth token validation"

📦 third-repo (bugfix/issue-456)
   1 file changed:
     M src/utils.py

   Commit this repository? [Y/n/e/s] n
   Skipped

Summary:
  1 repository committed
  1 repository skipped
```

### Example 3: Commit specific repo

```bash
$ qen commit -m "Update API docs" --repo repos/api
Committing project: feature-work

📦 repos/api (feature/api-update)
   2 files changed
   ✓ Committed: "Update API docs"

Summary:
  1 repository committed (2 files)
```

### Example 4: Amend previous commit

```bash
$ qen commit --amend -m "Fix authentication bug (include tests)"
Committing project: feature-work

📦 example-repo (feature/my-work)
   1 file changed
   ✓ Amended: "Fix authentication bug (include tests)"

Summary:
  1 repository amended (1 file)
```

### Example 5: Error (merge in progress)

```bash
$ qen commit -m "Fix bug"
Committing project: feature-work

📦 example-repo (feature/my-work)
   ✗ Merge in progress
   Suggestion: Complete or abort merge first (git merge --abort)

Summary:
  0 repositories committed
  1 repository failed
```

## Related Specifications

- [02-qen-push.md](02-qen-push.md) - Push commits after committing
- [01-qen-pull.md](01-qen-pull.md) - Pull before committing to get latest changes
- [4-qen-status.md](../1-qen-init/4-qen-status.md) - Check status before committing
