# Revised Spec: `qen init` - Discovery-First Project Setup

**Date:** 2025-12-11
**Status:** Draft - Ready for Review
**Supersedes:** [03-qen-clone-spec.md](03-qen-clone-spec.md) (Phase 3 only)

---

## Core Philosophy Change

### OLD Model (Wrong)

```bash
qen init myproj  # "Create a NEW project"
```

- Assumes this is the first/only machine
- Always creates new things
- No detection of existing work
- No collaboration support

### NEW Model (Correct)

```bash
qen init myproj  # "I want to work on project myproj"
```

- Discover-first, create-if-needed
- Works for first user AND tenth user
- Detects existing state (local + remote)
- Collaborative by default

---

## Key Insight

**User B on Machine 2 types:** `uvx qen init myproj`

They're NOT trying to create a new project.
They're trying to work on the SAME project User A started on Machine 1.

**Therefore `qen init` must be idempotent and discovery-first.**

---

## What `qen init` Does

### 1. Local-Only Operations

**Never pushes to remote automatically.**

- Create/update config: `$XDG_CONFIG_HOME/qen/projects/<project>.toml`
- Clone/create per-project meta: `{meta_parent}/meta-{project}/`
- Checkout existing branch OR create new branch
- User pushes manually when ready

### 2. Detection Logic (Before Creating Anything)

Check three places:

1. **Remote branch exists?** → Query origin for matching branch
2. **Local config exists?** → `$XDG_CONFIG_HOME/qen/projects/<project>.toml`
3. **Local repo exists?** → `{meta_parent}/meta-{project}/`

### 3. Interactive Prompt (After Detection)

Show user what exists and what will happen.

#### Scenario A: Nothing Exists (First Machine, New Project)

```text
Project: myproj (251211-myproj)

No existing state found:
  ✗ Remote branch: Not found
  ✗ Local config: Not found
  ✗ Local repo: Not found

Actions:
  • Clone meta-myproj from git@github.com:org/meta.git
  • Create new branch 251211-myproj from main
  • Create project folder proj/251211-myproj/
  • Create config at ~/.config/qen/projects/myproj.toml

Continue? [Y/n]
```

**User types:** `y` (or presses Enter)

**What happens:**

1. Clone `meta-myproj` from remote
2. Create branch `251211-myproj`
3. Create `proj/251211-myproj/` structure
4. Commit locally
5. Write config
6. **User pushes manually later**

#### Scenario B: Remote Branch Exists (Second Machine, Existing Project)

```text
Project: myproj (251210-myproj)

Found existing state:
  ✓ Remote branch: 251210-myproj (3 commits, last updated 2 days ago)
  ✗ Local config: Not found
  ✗ Local repo: Not found

Actions:
  • Clone meta-myproj from origin/251210-myproj
  • Checkout existing branch 251210-myproj
  • Pull latest changes
  • Create config at ~/.config/qen/projects/myproj.toml

Continue? [Y/n]
```

**User types:** `y`

**What happens:**

1. Clone `meta-myproj` from remote, using branch `251210-myproj`
2. Pull latest changes
3. Write config pointing to `meta-myproj`
4. Done - user can now work on existing project

#### Scenario C: Local Config + Repo Exist (Already Setup)

```text
Project: myproj (251210-myproj)

Already configured:
  ✓ Local config: ~/.config/qen/projects/myproj.toml
  ✓ Local repo: ~/GitHub/meta-myproj
  ✓ Remote branch: 251210-myproj (up to date)

Nothing to do. Project is ready to use.

Switch to it with: qen config myproj
```

**No action needed.**

#### Scenario D: Remote Mismatch (Ambiguous)

```text
Project: myproj

Found multiple possible branches on remote:
  [1] 251210-myproj (5 commits, last updated 5 days ago)
  [2] 251205-myproj (12 commits, last updated 2 weeks ago)

Which branch should be used?
  1) 251210-myproj
  2) 251205-myproj
  3) Create new branch (251211-myproj)

Choice [1]:
```

**User types:** `1` (or presses Enter)

**What happens:**

1. Clone using selected branch `251210-myproj`
2. Store config using user-typed name `myproj` → `projects/myproj.toml`
3. Config contains `branch = "251210-myproj"` for disambiguation

---

## Fully-Qualified Project Names

Users can specify exact branch name to avoid ambiguity:

```bash
# Short name (auto-generates date prefix)
qen init myproj          # Uses 251211-myproj (or finds existing)

# Fully-qualified name (use exact branch name)
qen init 251210-myproj   # Uses exactly 251210-myproj
```

**Config folder matches what user typed:**

- `qen init myproj` → config at `projects/myproj.toml`
- `qen init 251210-myproj` → config at `projects/251210-myproj.toml`

**This allows multiple "instances" of same project with different dates.**

---

## Discovery Algorithm

### Step 1: Parse Project Name

```python
def parse_project_name(name: str) -> tuple[str, str | None]:
    """Parse project name into (name, explicit_branch).

    Examples:
        "myproj" → ("myproj", None)
        "251210-myproj" → ("251210-myproj", "251210-myproj")

    Returns:
        (config_name, explicit_branch)
    """
    if re.match(r'^\d{6}-', name):
        # Fully-qualified: use as-is
        return (name, name)
    else:
        # Short name: generate branch later
        return (name, None)
```

### Step 2: Check Remote for Existing Branches

```python
def find_remote_branches(meta_remote: str, project_name: str) -> list[str]:
    """Find branches matching project on remote.

    Implementation:
        git ls-remote --heads <remote> refs/heads/*-{project_name}

    Returns:
        List of branch names (e.g., ["251210-myproj", "251205-myproj"])
    """
```

### Step 3: Check Local Config

```python
def check_local_config(config_name: str) -> dict | None:
    """Check if project config already exists.

    Returns:
        Config dict if exists, else None
    """
    config_path = config_dir / "projects" / f"{config_name}.toml"
    if config_path.exists():
        return tomli.loads(config_path.read_text())
    return None
```

### Step 4: Check Local Repo

```python
def check_local_repo(meta_parent: Path, project_name: str) -> Path | None:
    """Check if per-project meta clone exists.

    Returns:
        Path if exists and is valid git repo, else None
    """
    repo_path = meta_parent / f"meta-{project_name}"
    if repo_path.exists() and (repo_path / ".git").exists():
        return repo_path
    return None
```

### Step 5: Decision Matrix

| Remote Branch | Local Config | Local Repo | Action |
|---------------|--------------|------------|--------|
| ✗ | ✗ | ✗ | Create new (Scenario A) |
| ✓ (1) | ✗ | ✗ | Clone existing (Scenario B) |
| ✓ (>1) | ✗ | ✗ | Prompt user (Scenario D) |
| ✓ | ✓ | ✓ | Already setup (Scenario C) |
| ✗ | ✓ | ✓ | Validate and sync |
| ✗ | ✓ | ✗ | Config orphaned - offer to recreate |
| ✗ | ✗ | ✓ | Repo orphaned - offer to adopt |
| ✓ | ✗ | ✓ | Sync config with repo |

---

## Command Flow

```python
@click.command()
@click.argument("project", required=True)
@click.option("--yes", is_flag=True, help="Skip confirmation prompts")
@click.option("--force", is_flag=True, help="Delete existing and recreate")
def init_project(project: str, yes: bool, force: bool):
    """Setup a project (discover existing or create new)."""

    # 1. Ensure global config exists (auto-init if needed)
    config = ensure_initialized()
    main_config = config.read_main_config()

    # 2. Parse project name
    config_name, explicit_branch = parse_project_name(project)

    # 3. Handle --force mode (delete and recreate)
    if force:
        handle_force_mode(config, config_name, yes)
        # Continue to create new

    # 4. Discover existing state
    remote_branches = find_remote_branches(main_config["meta_remote"], config_name)
    local_config = check_local_config(config_name)
    local_repo = check_local_repo(Path(main_config["meta_parent"]), config_name)

    # 5. Decide action based on state
    if local_config and local_repo and remote_branches:
        # Already setup - nothing to do
        show_already_setup(config_name, local_config, local_repo)
        return

    if explicit_branch:
        # User specified exact branch - use it
        target_branch = explicit_branch
    elif len(remote_branches) == 1:
        # One remote branch found - use it
        target_branch = remote_branches[0]
    elif len(remote_branches) > 1:
        # Multiple branches - prompt user
        target_branch = prompt_branch_choice(remote_branches, config_name)
    else:
        # No remote branch - generate new
        target_branch = f"{datetime.now().strftime('%y%m%d')}-{config_name}"

    # 6. Show plan and confirm
    plan = build_plan(remote_branches, local_config, local_repo, target_branch)
    if not yes:
        show_plan(plan)
        if not click.confirm("Continue?", default=True):
            click.echo("Aborted.")
            return

    # 7. Execute plan
    if target_branch in remote_branches:
        # Clone existing branch
        repo_path = clone_from_remote(
            main_config["meta_remote"],
            config_name,
            target_branch,
            Path(main_config["meta_parent"]),
        )
    else:
        # Create new branch
        repo_path = create_new_project(
            main_config["meta_remote"],
            config_name,
            target_branch,
            Path(main_config["meta_parent"]),
            main_config["meta_default_branch"],
        )

    # 8. Write config
    config.write_project_config(
        project_name=config_name,
        branch=target_branch,
        folder=f"proj/{target_branch}",
        repo=str(repo_path),
        created=datetime.now(timezone.utc).isoformat(),
    )

    # 9. Set as current project
    config.write_main_config(
        **main_config,
        current_project=config_name,
    )

    # 10. Success message
    click.echo(f"✓ Project '{config_name}' ready at {repo_path}")
```

---

## New Command: `qen del`

Delete project (local config and/or repo).

```bash
qen del <project>
```

### Options

- `--config-only` - Delete only config, leave repo
- `--repo-only` - Delete only repo, leave config
- `--remote` - Also delete remote branch (WARNING)
- `--yes` - Skip confirmation

### Default Behavior (No Options)

Prompt user:

```text
Delete project 'myproj':
  ✓ Config: ~/.config/qen/projects/myproj.toml
  ✓ Repo: ~/GitHub/meta-myproj (branch: 251210-myproj)
  ✗ Remote: origin/251210-myproj (will NOT be deleted)

⚠️  Warning: Uncommitted changes:
  • 3 uncommitted file(s)
  • 2 unpushed commit(s)

Delete local config and repo? [y/N]:
```

### Safety Checks

1. Check for uncommitted changes
2. Check for unpushed commits
3. Display warnings with counts
4. Require explicit confirmation
5. Never delete remote by default

---

## Relationship: `qen init` vs `qen config`

### `qen init <project>`

**Purpose:** "I want to setup a project on my machine (which might already exist elsewhere)"

**What it does:**

- Discovers existing state (remote, local config, local repo)
- Clones or creates per-project meta as needed
- Writes config
- Sets as current project

### `qen config <project>`

**Purpose:** "I want to switch to a project I already believe is configured"

**What it does:**

- Reads existing config (errors if not found)
- Sets `current_project` in main config
- Does NOT clone, create, or discover

**They could be the same command:** Open to argument, but instinct is separate code paths.

---

## Decision Rules (General Philosophy)

**a) If the obvious thing exists, use it**

- One remote branch found → use it
- Config + repo exist → already setup

**b) If a non-obvious thing exists, ask**

- Multiple remote branches → prompt user
- Config exists but repo missing → offer to recreate

**c) If nothing exists, create it**

- No remote, no config, no repo → create new

---

## Breaking Changes from v0.4.0 Spec

### 1. No Auto-Push

**OLD:** `qen init` pushes branch to remote automatically

**NEW:** `qen init` creates branch locally, user pushes manually

### 2. No Auto-PR Prompt

**OLD:** Prompts to create PR after init

**NEW:** User creates PR manually when ready (using `gh pr create` or web UI)

### 3. Discovery-First

**NEW:** Always checks for existing remote branches before creating

### 4. Fully-Qualified Names Supported

**NEW:** Can type `qen init 251210-myproj` to explicitly use that branch

---

## Edge Cases

### 1. Config Exists, Repo Missing

```text
Warning: Config exists but repo is missing.
  Config: ~/.config/qen/projects/myproj.toml
  Expected repo: ~/GitHub/meta-myproj

Options:
  1) Delete config and recreate (recommended)
  2) Re-clone repo to expected location
  3) Abort

Choice [1]:
```

### 2. Repo Exists, Config Missing

```text
Found existing repo without config:
  Repo: ~/GitHub/meta-myproj
  Branch: 251210-myproj

Create config for this repo? [Y/n]:
```

### 3. Config and Repo Exist, Remote Missing

```text
Warning: Local project exists but remote branch not found.
  Config: ~/.config/qen/projects/myproj.toml
  Repo: ~/GitHub/meta-myproj
  Branch: 251210-myproj
  Remote: Not found

This is normal if you haven't pushed yet.

Push branch to remote? [Y/n]:
```

### 4. Remote Branch Name Doesn't Match Config

```text
Warning: Branch name mismatch
  Config name: myproj
  Config branch: 251210-myproj
  Current repo branch: 251209-myproj

Options:
  1) Update config to match repo (251209-myproj)
  2) Checkout branch from config (251210-myproj)
  3) Abort

Choice [1]:
```

---

## Success Criteria

- [ ] User A on Machine 1 can create new project
- [ ] User B on Machine 2 can setup same project (clone existing)
- [ ] User C can work on multiple projects simultaneously
- [ ] `qen init myproj` is idempotent (safe to run multiple times)
- [ ] Detects and uses existing remote branches
- [ ] Supports fully-qualified names (e.g., `251210-myproj`)
- [ ] No auto-push (user controls when to push)
- [ ] Clear prompts show what exists and what will happen
- [ ] Safe force mode with uncommitted/unpushed warnings
- [ ] `qen del` safely removes projects

---

## Implementation Notes

### Remote Branch Detection

```bash
# List branches matching pattern
git ls-remote --heads origin refs/heads/*-myproj

# Output:
# 1a2b3c4d5e6f  refs/heads/251210-myproj
# 7g8h9i0j1k2l  refs/heads/251205-myproj

# Parse to get branch names and metadata
```

### Clone from Specific Branch

```bash
# Clone with specific branch checked out
git clone --branch 251210-myproj git@github.com:org/meta.git meta-myproj
```

### Branch Metadata (Last Updated, Commit Count)

```bash
# Get branch metadata from remote
git ls-remote --heads origin refs/heads/251210-myproj | cut -f1 | \
  xargs git show --format="%cr (%h)" --no-patch
```

---

## Files Modified (Additional to v0.4.0 Spec)

### Core Implementation

- `src/qen/commands/init.py` - Rewrite with discovery-first logic
- `src/qen/git_utils.py` - Add remote branch detection functions

### New Files

- `src/qen/commands/del.py` - New `qen del` command

### Tests

- `tests/unit/qen/commands/test_init.py` - Update for new behavior
- `tests/integration/test_init_discovery.py` - NEW - test multi-machine scenarios

---

## Open Questions

1. **Should `qen init` and `qen config` be merged?**
   - Separate feels cleaner, but could be argued as same intent

2. **What if local branch exists but isn't tracking remote?**
   - Set upstream automatically?
   - Warn user?

3. **Should we support cloning from arbitrary remotes?**
   - E.g., `qen init myproj --remote git@other-host:org/meta.git`
   - Or always use `meta_remote` from global config?

4. **What if remote branch exists but project folder missing inside?**
   - Recreate `proj/YYMMDD-myproj/` structure?
   - Error and ask user to investigate?

5. **Should `--force` require explicit confirmation even with `--yes`?**
   - Or does `--yes` mean "skip ALL prompts"?

---

## Migration from v0.3.0 (No Change)

Users with old projects still use `uvx qen@0.3.0` or recreate with `qen init --force`.

No automatic migration tooling.
