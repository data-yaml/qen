# Implementation Spec: Per-Project Meta Clone Architecture

**Date:** 2025-12-10
**Status:** Planning Complete - Ready for Implementation
**Design Reference:** [02-qen-clone-design.md](02-qen-clone-design.md)

---

## Executive Summary

This spec documents all implementation tasks for the per-project meta clone architecture. All critical design decisions have been resolved.

**Key Principle:** Each active project gets its own physical clone of the meta repository, cloned from the remote, enabling true multi-project workflows without branch-switching friction.

**Critical Insight:** Clone from **remote** meta repository (not local meta prime) to ensure clean source, no local state pollution, and always up-to-date starting point.

---

## Resolved Design Decisions

### 1. Naming Convention

**Decision:** `meta-{project}` (e.g., `meta-myproj`)
**Rationale:** Project names are unique in config, no collision risk

### 2. Migration Strategy

**Decision:** Pure breaking change (no migration tooling)
**Rationale:** Clean break, users needing old model use `uvx qen@0.3.0`

### 3. Clone Source

**Decision:** Clone from remote meta repository, not local meta prime
**Rationale:** Clean source, no local state pollution, always up-to-date
**Implementation:** `git clone <remote_url> <path> --branch main`

### 4. Configuration Storage

**Decision:** Store `meta_remote`, `meta_parent`, and `meta_default_branch` in global config (BUG FIX + OPTIMIZATION)
**Rationale:** Need remote URL to clone per-project metas, parent directory to determine where to clone them, and default branch name to avoid repeated detection
**Schema:**

```toml
meta_path = "/Users/ernest/GitHub/meta"
meta_remote = "git@github.com:my-org/meta.git"  # NEW
meta_parent = "/Users/ernest/GitHub"  # NEW - where to clone per-project metas
meta_default_branch = "main"  # NEW - detected once during init
org = "my-org"
```

### 5. Project Config Schema

**Decision:** Store absolute path to per-project meta clone
**Schema:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
repo = "/Users/ernest/GitHub/meta-myproj"  # NEW
created = "2025-12-10T12:34:56Z"
```

### 6. Auto-Push Behavior

**Decision:** Keep current behavior (auto-push and prompt for PR)
**Rationale:** Maintains existing user workflow expectations

### 7. Force Mode Behavior

**Decision:** Delete entire `meta-{project}/` directory with safety checks
**Safety Requirements:**

- Check for uncommitted changes
- Check for unpushed commits
- Display warnings with specifics
- Require confirmation prompt
- Support `--yes` flag to skip confirmation
- Leave remote branch alone (user can delete manually)

### 8. Current Project Semantics

**Decision:** Pure config state (no directory switching)
**Rationale:** Design doc: "current_project is QEN state - independent of current working directory"

---

## Implementation Tasks

### Phase 1: Configuration Schema Changes

#### Task 1.0: Extend Global Config with Meta Repository Metadata

**Priority:** CRITICAL - Required for all other tasks

**What:** Add three new fields to global config: `meta_remote`, `meta_parent`, `meta_default_branch`

**Where:**

- `src/qen/config.py:write_main_config()` (add three parameters)
- `src/qen/config.py:read_main_config()` (return new fields)
- `src/qen/commands/init.py:init_qen()` (extract and store all metadata)

**Current Signature:**

```python
def write_main_config(
    self, meta_path: str, org: str, current_project: str | None = None
) -> None:
    config: dict[str, Any] = {
        "meta_path": meta_path,
        "org": org,
    }
```

**New Signature:**

```python
def write_main_config(
    self,
    meta_path: str,
    meta_remote: str,         # NEW - remote URL for cloning
    meta_parent: str,         # NEW - parent directory for clones
    meta_default_branch: str, # NEW - default branch (main/master)
    org: str,
    current_project: str | None = None
) -> None:
    config: dict[str, Any] = {
        "meta_path": meta_path,
        "meta_remote": meta_remote,
        "meta_parent": meta_parent,
        "meta_default_branch": meta_default_branch,
        "org": org,
    }
```

**Extraction Logic in init_qen():**

```python
# 1. Extract remote URL
from .git_utils import get_remote_url
meta_prime_path = Path(meta_path)
remote_url = get_remote_url(meta_prime_path)

# 2. Resolve symlinks and get parent directory
if meta_prime_path.is_symlink():
    meta_prime_path = meta_prime_path.resolve()

if not meta_prime_path.exists():
    raise ConfigError(f"Meta path does not exist: {meta_path}")

target_parent_dir = meta_prime_path.parent

if not target_parent_dir.is_dir() or not os.access(target_parent_dir, os.W_OK):
    raise ConfigError(f"Parent directory not writable: {target_parent_dir}")

# 3. Detect default branch from remote
from .git_utils import get_default_branch
default_branch = get_default_branch(remote_url)

# 4. Store all metadata in config
config.write_main_config(
    meta_path=str(meta_prime_path),
    meta_remote=remote_url,
    meta_parent=str(target_parent_dir),
    meta_default_branch=default_branch,
    org=org,
)
```

**Helper Functions Needed (src/qen/git_utils.py):**

```python
def get_remote_url(repo_path: Path, remote_name: str = "origin") -> str:
    """Get remote URL from repository.

    Returns: Remote URL
    Raises: GitError if remote doesn't exist
    """
    result = run_git_command(
        ["remote", "get-url", remote_name],
        cwd=repo_path,
    )
    return result.stdout.strip()


def get_default_branch(remote_url: str) -> str:
    """Detect default branch name from remote (main or master).

    Implementation:
        # Try: git ls-remote --symref <url> HEAD
        # Parse: ref: refs/heads/main HEAD
        # Extract: "main"
        # Fallback: "main"
    """
```

**Rationale:** Extract and store all meta repository metadata once during `qen init`, avoiding repeated git queries and path computations

---

#### Task 1.1: Add repo Field to Project Config

**What:** Add `repo` field to project configuration

**Where:**

- `src/qen/config.py:write_project_config()` (add repo parameter)
- `src/qen/config.py:read_project_config()` (return repo field)

**Changes:**

```python
def write_project_config(
    self,
    project_name: str,
    branch: str,
    folder: str,
    repo: str,  # NEW - absolute path to per-project meta clone
    created: str | None = None,
) -> None:
    config = {
        "name": project_name,
        "branch": branch,
        "folder": folder,
        "repo": repo,  # NEW
        "created": created,
    }
```

**Validation:** Should we error if `repo` path doesn't exist? (Decision needed)

---

#### Task 1.2: Auto-Update Legacy Global Config

**What:** Extend `ensure_initialized()` to auto-update legacy global configs missing new fields

**Where:** `src/qen/init_utils.py:ensure_initialized()`

**Current Behavior:** Returns immediately if `main_config_exists()` returns True (line 84-85)

**New Behavior:** Check for missing fields and auto-update if needed

**Implementation:**

```python
def ensure_initialized(
    config_dir: Path | str | None = None,
    storage: QenvyBase | None = None,
    meta_path_override: Path | str | None = None,
    current_project_override: str | None = None,
    verbose: bool = False,
) -> QenConfig:
    """Ensure qen is initialized, auto-initializing if possible."""
    # Create QenConfig instance
    config = QenConfig(...)

    # Check if config exists
    if not config.main_config_exists():
        # Config doesn't exist - attempt auto-initialization (existing logic)
        ...
        return config

    # Config exists - check for missing fields (NEW LOGIC)
    main_config = config.read_main_config()

    # Check if we need to upgrade
    needs_upgrade = (
        "meta_remote" not in main_config or
        "meta_parent" not in main_config or
        "meta_default_branch" not in main_config
    )

    if not needs_upgrade:
        return config  # Config is up to date

    # Need to upgrade - extract missing fields
    if verbose:
        click.echo("Upgrading configuration to new format...")

    try:
        from .commands.init import extract_remote_and_org
        from .git_utils import get_default_branch

        # Get meta_path
        meta_path = Path(main_config["meta_path"])

        # Resolve symlinks and validate
        if meta_path.is_symlink():
            meta_path = meta_path.resolve()

        if not meta_path.exists():
            click.echo(
                f"Error: Meta path no longer exists: {meta_path}\n"
                f"Please reinitialize: qen init",
                err=True
            )
            raise click.Abort()

        # Extract remote URL and org
        remote_url, org = extract_remote_and_org(meta_path)

        # Get parent directory
        meta_parent = meta_path.parent
        if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
            click.echo(
                f"Error: Parent directory not writable: {meta_parent}\n"
                f"Cannot auto-upgrade configuration.",
                err=True
            )
            raise click.Abort()

        # Detect default branch
        default_branch = get_default_branch(remote_url)

        # Update config with new fields
        config.write_main_config(
            meta_path=str(meta_path),
            meta_remote=remote_url,
            meta_parent=str(meta_parent),
            meta_default_branch=default_branch,
            org=org,
            current_project=main_config.get("current_project"),
        )

        if verbose:
            click.echo("✓ Configuration upgraded successfully")

        return config

    except (GitError, KeyError) as e:
        click.echo(
            f"Error: Cannot auto-upgrade configuration: {e}\n"
            f"Please reinitialize: qen init",
            err=True
        )
        raise click.Abort() from e
```

**Project Config Migration:**

Project configs missing `repo` field CANNOT be auto-migrated (no way to infer per-project meta path). Commands should error with:

```python
# In commands that need project config:
project_config = config.read_project_config(current_project)

if "repo" not in project_config:
    click.echo(
        f"Error: Project '{current_project}' uses old configuration format.\n"
        f"This version requires per-project meta clones.\n"
        f"To migrate: qen init --force {current_project}",
        err=True
    )
    raise click.Abort()
```

**Rationale:** Global config can be auto-upgraded because we can derive missing fields from existing `meta_path`. Project configs cannot because there's no way to know where the per-project meta clone should be.

---

### Phase 2: Clone Creation Logic

#### Task 2.1: Implement Clone from Remote Function

**What:** Create function to clone from remote → per-project meta

**Where:** New function in `src/qen/git_utils.py`

**Signature:**

```python
def clone_per_project_meta(
    meta_remote_url: str,
    project_name: str,
    target_parent_dir: Path,
    default_branch: str,
) -> Path:
    """Clone meta repository from remote to create per-project meta.

    Args:
        meta_remote_url: Remote URL (e.g., git@github.com:org/meta.git)
        project_name: Project name for directory naming
        target_parent_dir: Parent directory (e.g., ~/GitHub/)
        default_branch: Branch to clone (from config, e.g., "main" or "master")

    Returns:
        Path to created per-project meta clone

    Raises:
        GitError: If clone fails
    """
    clone_path = target_parent_dir / f"meta-{project_name}"

    # Check if already exists
    if clone_path.exists():
        raise GitError(f"Directory already exists: {clone_path}")

    # Clone from remote, checking out specified branch
    # git clone <url> <path> --branch <branch>
    run_git_command(
        ["clone", meta_remote_url, str(clone_path), "--branch", default_branch],
        cwd=target_parent_dir,
    )

    return clone_path
```

**Edge Cases:**

- Target directory already exists → Error
- Remote unreachable → Let git error propagate
- Specified branch doesn't exist → Let git error propagate
- Insufficient permissions → Let OS error propagate

---

### Phase 3: Init Command Refactoring

#### Task 3.1: Refactor init_project() Flow

**What:** Update to create per-project meta clone

**Where:** `src/qen/commands/init.py:init_project()`

**Current Flow:**

1. Load config → get meta_path
2. Create branch in meta_path
3. Create project structure in meta_path
4. Write project config (no repo field)

**New Flow:**

1. Load config → get meta_remote, meta_parent, meta_default_branch
2. Clone from remote → per-project meta (using stored config values)
3. Create branch in per-project meta
4. Create project structure in per-project meta
5. Push branch to remote
6. Write project config WITH repo field
7. Set current_project

**Code Changes:**

```python
# OLD:
meta_path = Path(main_config["meta_path"])
branch_name, folder_path = create_project(meta_path, project_name, ...)

# NEW:
meta_remote = main_config["meta_remote"]
meta_parent = Path(main_config["meta_parent"])
meta_default_branch = main_config["meta_default_branch"]

# Clone from remote
per_project_meta = clone_per_project_meta(
    meta_remote,
    project_name,
    meta_parent,
    meta_default_branch  # Use stored default branch
)

# Create project in the clone
branch_name, folder_path = create_project(
    per_project_meta,  # Use clone, not meta prime
    project_name,
    ...
)

# Store repo path in config
config.write_project_config(
    project_name=project_name,
    branch=branch_name,
    folder=folder_path,
    repo=str(per_project_meta),  # NEW
    created=now.isoformat(),
)
```

---

#### Task 3.2: Update Force Mode Cleanup

**What:** Delete entire per-project meta directory with safety checks

**Where:** `src/qen/commands/init.py:init_project()` (lines 217-335)

**Current Behavior:** Deletes branch and folder from meta prime

**New Behavior:** Delete entire `meta-{project}/` directory

**Safety Checks (MUST IMPLEMENT):**

```python
# 1. Get per-project meta path
old_config = config.read_project_config(project_name)
per_project_meta = Path(old_config["repo"])

if not per_project_meta.exists():
    # Already gone, just delete config
    config.delete_project_config(project_name)
    return

# 2. Check for uncommitted changes
result = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=per_project_meta,
    capture_output=True,
    text=True,
)
uncommitted_files = [line for line in result.stdout.split('\n') if line.strip()]

# 3. Check for unpushed commits
branch = old_config.get("branch")
result = subprocess.run(
    ["git", "log", f"origin/{branch}..{branch}", "--oneline"],
    cwd=per_project_meta,
    capture_output=True,
    text=True,
)
unpushed_commits = [line for line in result.stdout.split('\n') if line.strip()]

# 4. Display warnings
warnings = []
if uncommitted_files:
    warnings.append(f"  • {len(uncommitted_files)} uncommitted file(s)")
if unpushed_commits:
    warnings.append(f"  • {len(unpushed_commits)} unpushed commit(s)")

if warnings:
    click.echo("⚠️  Warning: The following will be lost:", err=True)
    for warning in warnings:
        click.echo(warning, err=True)
    click.echo()

# 5. Confirm deletion (unless --yes flag)
if not yes:
    click.echo(f"This will permanently delete: {per_project_meta}")
    if not click.confirm("Continue?", default=False):
        click.echo("Aborted.")
        raise click.Abort()

# 6. Delete directory
shutil.rmtree(per_project_meta)
config.delete_project_config(project_name)

# 7. Leave remote branch alone (user can delete manually)
```

---

#### Task 3.3: Update Auto-Initialization

**What:** Ensure auto-init extracts remote URL

**Where:** `src/qen/commands/init.py:init_project()` (lines 186-196)

**Current:** Calls `init_qen()` which extracts org only

**New:** Ensure `init_qen()` extracts and stores remote URL

**No Changes Needed:** Task 1.0 handles this

---

### Phase 4: Update All Commands

**Commands to Update:** (All 10 commands that use meta_path)

1. `src/qen/commands/add.py`
2. `src/qen/commands/status.py`
3. `src/qen/commands/pull.py`
4. `src/qen/commands/push.py`
5. `src/qen/commands/pr.py`
6. `src/qen/commands/sh.py`
7. `src/qen/commands/rm.py`
8. `src/qen/commands/workspace.py`
9. `src/qen/commands/config.py`
10. `src/qen/commands/init.py` (already covered above)

**Pattern Change:**

```python
# OLD PATTERN:
main_config = config.read_main_config()
meta_path = Path(main_config["meta_path"])  # ← Points to meta prime
project_config = config.read_project_config(current_project)
folder = project_config["folder"]
project_dir = meta_path / folder  # ← Uses meta prime

# NEW PATTERN:
project_config = config.read_project_config(current_project)
per_project_meta = Path(project_config["repo"])  # ← NEW field
folder = project_config["folder"]
project_dir = per_project_meta / folder  # ← Uses per-project meta
```

**Task 4.1-4.10:** Apply this pattern to each command

**Error Handling:** Use Task 1.2 pattern for missing `repo` field

---

### Phase 5: Git Utilities

#### Task 5.1: Review find_meta_repo() Usage

**What:** Verify find_meta_repo() still works correctly

**Where:** `src/qen/git_utils.py:find_meta_repo()`

**Current Usage:** Used by init_qen() to find meta prime

**New Model:** Still needed to find meta prime (to extract remote URL)

**Question:** Should it distinguish between meta prime and per-project metas?

**Answer:** No - it searches for directory named "meta", which is always meta prime by convention

**Action:** No changes needed, but add comment clarifying it finds meta prime

---

### Phase 6: Testing

#### Task 6.1: Update Unit Tests for Config

**Where:** `tests/unit/qen/test_config.py`

**Tests to Add:**

- Write main config with all new fields (`meta_remote`, `meta_parent`, `meta_default_branch`)
- Read main config with all new fields
- Error on main config missing new fields
- Write project config with `repo` field
- Read project config with `repo` field
- Error on project config missing `repo` field (with helpful message)

---

#### Task 6.2: Update Unit Tests for Init

**Where:** `tests/unit/qen/commands/test_init.py`

**Tests to Update:**

- Mock `clone_per_project_meta()` instead of branch creation
- Verify clone called with correct remote URL
- Verify project config written with `repo` field
- Test force mode with safety checks (mock git commands)

---

#### Task 6.3: Update Integration Tests

**Where:** `tests/integration/`

**Tests to Update:**

- Use real remote cloning (slower but accurate)
- Test multiple simultaneous projects (isolation)
- Verify per-project metas are truly independent

**Note:** Integration tests may need to be run against real GitHub repo or local git server

---

#### Task 6.4: Add Multi-Project Tests

**New Test File:** `tests/integration/test_multi_project.py`

**Test Cases:**

- Create two projects simultaneously
- Verify independent directory structure
- Verify both can push to same remote
- Switch between projects (config state only)
- Verify changes in one don't affect other

---

### Phase 7: Documentation

#### Task 7.1: Update README.md

**What:** Document new per-project meta architecture

**Sections to Update:**

- Architecture overview → explain meta prime vs per-project metas
- Directory structure example → show multiple `meta-*` directories
- Workflow examples → emphasize physical isolation

---

#### Task 7.2: Update CLAUDE.md (AGENTS.md)

**What:** Update agent guide

**Sections to Update:**

- Key concepts → meta prime vs per-project meta terminology
- Configuration schema → new `meta_remote` and `repo` fields
- Command behavior → all commands now use per-project metas

---

#### Task 7.3: Create Migration Guide

**New File:** `spec/5-clone/04-migration-guide.md`

**Content:**

- Breaking change notice
- How to use old version: `uvx qen@0.3.0`
- Manual migration: Delete old project configs, recreate with `qen init --force`

---

### Phase 8: Edge Cases

#### Task 8.1: Handle Meta Prime Not Found

**Where:** `init_qen()`, `init_project()`

**Error Message:**

```log
Error: Could not find meta repository.
Please ensure you are in or near a directory named 'meta',
or specify the path with: qen --meta <path> init
```

---

#### Task 8.2: Handle Clone Failures

**Where:** `clone_per_project_meta()`

**Cleanup:** Delete partial clone on failure

```python
try:
    run_git_command(["clone", ...])
except GitError:
    # Cleanup partial clone
    if clone_path.exists():
        shutil.rmtree(clone_path)
    raise
```

---

#### Task 8.3: Handle Remote Unreachable

**Where:** `clone_per_project_meta()`

**Error Message:**

```log
Error: Could not reach remote repository: <url>
Ensure you have network access and correct credentials.
```

---

#### Task 8.4: Handle Per-Project Meta Already Exists

**Where:** `clone_per_project_meta()`

**Error Message:**

```log
Error: Directory already exists: <path>
Use --force to delete and recreate the project.
```

---

## Implementation Order

**Recommended Sequence:**

1. **Phase 1** (Config changes) - Foundation
   - Task 1.0 (extend global config with meta_remote, meta_parent, meta_default_branch) - CRITICAL FIRST
   - Task 1.1 (add repo field to project config)
   - Task 1.2 (auto-upgrade legacy configs in ensure_initialized)

2. **Phase 2** (Clone logic) - Core functionality
   - Task 2.1 (clone function - uses stored config values)

3. **Phase 3** (Init refactor) - Critical path
   - Task 3.1 (new flow)
   - Task 3.2 (force mode)
   - Task 3.3 (auto-init check)

4. **Phase 5** (Git utilities) - Support functions
   - Task 5.1 (review find_meta_repo)

5. **Phase 4** (Command updates) - Make everything work
   - Update all 10 commands

6. **Phase 6** (Testing) - Validation
   - Unit tests
   - Integration tests

7. **Phase 7** (Documentation) - User-facing
   - README
   - CLAUDE.md
   - Migration guide

8. **Phase 8** (Edge cases) - Polish

---

## Risk Areas

### High Risk

- **Data loss:** Force mode deleting entire directories
  - **Mitigation:** Safety checks, confirmation prompts
- **Remote unreachable:** Network or auth issues
  - **Mitigation:** Clear error messages, fallback suggestions
- **Config migration:** Existing projects become invalid
  - **Mitigation:** Clear error with instructions

### Medium Risk

- **Clone failures:** Disk space, permissions, partial clones
  - **Mitigation:** Cleanup on failure, validate preconditions
- **Multiple remotes:** Edge case handling
  - **Mitigation:** Use `origin` by default, document limitation

### Low Risk

- **Symlink handling:** Meta prime as symlink
  - **Mitigation:** Resolve symlinks before operations
- **Naming collisions:** Unlikely with validation
  - **Mitigation:** Check before creating

---

## Files Modified

### Core Implementation (6 files)

- `src/qen/config.py` - Add `meta_remote` and `repo` fields
- `src/qen/project.py` - Use per-project meta for operations
- `src/qen/commands/init.py` - Refactor init_project()
- `src/qen/git_utils.py` - Add clone and remote utilities

### Command Updates (9 files)

- `src/qen/commands/add.py`
- `src/qen/commands/status.py`
- `src/qen/commands/pull.py`
- `src/qen/commands/push.py`
- `src/qen/commands/pr.py`
- `src/qen/commands/sh.py`
- `src/qen/commands/rm.py`
- `src/qen/commands/workspace.py`
- `src/qen/commands/config.py`

### Testing (4 areas)

- `tests/unit/qen/test_config.py`
- `tests/unit/qen/test_project.py`
- `tests/unit/qen/commands/test_init.py`
- `tests/integration/` (all tests)

### Documentation (3 files)

- `README.md`
- `AGENTS.md` (CLAUDE.md symlink)
- `spec/5-clone/04-migration-guide.md` (new)

---

## Success Criteria

- [ ] Can create multiple projects simultaneously
- [ ] Each project has independent per-project meta clone
- [ ] All clones created from remote (not local meta prime)
- [ ] Projects work in isolation (no cross-contamination)
- [ ] Force mode safely deletes with warnings
- [ ] Old project configs show clear migration error
- [ ] All tests pass
- [ ] Documentation complete

---

## Breaking Changes

### Config Format

**Main Config:**

```toml
# OLD (missing new fields)
meta_path = "/Users/ernest/GitHub/meta"
org = "my-org"

# NEW (adds meta_remote, meta_parent, meta_default_branch)
meta_path = "/Users/ernest/GitHub/meta"
meta_remote = "git@github.com:my-org/meta.git"
meta_parent = "/Users/ernest/GitHub"
meta_default_branch = "main"
org = "my-org"
```

**Project Config:**

```toml
# OLD (missing repo)
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"

# NEW (adds repo)
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
repo = "/Users/ernest/GitHub/meta-myproj"
```

### Directory Structure

```text
# OLD
~/GitHub/
└── meta/                    # All projects in one repo
    ├── proj/251210-proj1/
    └── proj/251209-proj2/

# NEW
~/GitHub/
├── meta/                    # Meta prime (user reviews/merges)
├── meta-proj1/              # Per-project meta
│   └── proj/251210-proj1/
└── meta-proj2/              # Another per-project meta
    └── proj/251209-proj2/
```

### User Workflow

**OLD:** Switch projects by checking out branches
**NEW:** Navigate to different directories, switch config with `qen config <project>`

---

## Version Compatibility

**Breaking Change:** v0.4.0

**Old Projects:** Use `uvx qen@0.3.0`

**No Automatic Migration:** Users must recreate projects

NOTE: The branch name remains the same, and remote origins are re-used.
So, recreation will reuse / should pull those branches.
