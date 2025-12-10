# Design: Per-Project Meta Architecture

## Problem

The current single-branch-per-project model has critical flaws:

1. **Cannot work on multiple projects simultaneously** - switching branches disrupts workspace
2. **Repos directory thrashing** - every branch switch means re-cloning or losing state in `repos/`
3. **IDE/tooling confusion** - language servers, file watchers disrupted on branch switches
4. **Accidental cross-contamination** - easy to commit wrong changes to wrong project branch

## Solution: Per-Project Meta Clones

Each active project gets its own physical clone of the meta repository.

## Architecture

### Directory Structure

```text
~/GitHub/                        # (or wherever meta prime is found)
├── meta/                        # Meta prime (user-controlled)
│   ├── main branch             # User manually reviews/merges here
│   └── .git/                   # Original git database
├── meta-myproj/                # Per-project meta (qen-managed, user-edited)
│   ├── branch: 251210-myproj  # Project branch checked out
│   ├── proj/251210-myproj/    # Project directory
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   └── repos/             # Sub-repos cloned here
│   └── .git/                   # Independent git database
└── meta-other/                 # Another per-project meta
    ├── branch: 251209-other
    └── proj/251209-other/
        └── repos/
```

### Terminology

**Informal:** meta / meta clone

**Formal:**

- **meta prime** - User's original `meta/` repository (manually controlled)
- **per-project meta** - QEN-managed `meta-{project}/` clones

### Key Properties

1. **Physical isolation** - Each project is a separate directory with separate git state
2. **Simultaneous work** - Can work on multiple projects at once without conflicts
3. **Human-editable** - Lives alongside other repos, not hidden in `~/.config/`
4. **Standard tooling** - IDEs, git tools work normally
5. **Shared remote** - All per-project metas push to same remote for archival

## Configuration Changes

### Project Config

**File:** `~/.config/qen/projects/{project}.toml`

**Old structure:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
created = "2025-12-10T12:34:56Z"
```

**New structure:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
repo = "/Users/ernest/GitHub/meta-myproj"  # NEW: path to per-project meta
created = "2025-12-10T12:34:56Z"
```

### Main Config

**File:** `~/.config/qen/config.toml`

**No changes needed:**

```toml
meta_path = "/Users/ernest/GitHub/meta"  # Still points to meta prime
org = "my-org"
current_project = "myproj"
```

### Current Project Semantics

**`current_project` is QEN state** - independent of:

- Current working directory
- Which meta clone you're in
- What git branch you're on

**When set to "myproj", qen commands:**

- Read project config: `~/.config/qen/projects/myproj.toml`
- Get `repo` field: `/Users/ernest/GitHub/meta-myproj`
- Operate on that per-project meta's `pyproject.toml`

## Workflow Changes

### Init Flow

**Command:** `qen init <project>`

**New behavior:**

1. Find meta prime (already works - `find_meta_repo()`)
2. Get meta prime's parent directory (e.g., `~/GitHub/`)
3. Clone meta prime → sibling `meta-{project}/`
4. In per-project meta: create branch `YYMMDD-{project}`
5. In per-project meta: create `proj/YYMMDD-{project}/` structure
6. Commit and push branch to remote
7. Store per-project meta path in project config (`repo` field)
8. Set `current_project` to new project

**Result:**

- Per-project meta exists at `~/GitHub/meta-{project}/`
- User can immediately start working (add repos, etc.)
- Branch exists on remote for eventual PR/merge

### Add Flow

**Command:** `qen add <repo-url>`

**Behavior (unchanged in concept, different in implementation):**

1. Read `current_project` from main config
2. Read project config to get `repo` field
3. Clone sub-repo into `{repo}/{folder}/repos/`
4. Update `{repo}/{folder}/pyproject.toml`

### Status/PR Commands

**Commands:** `qen status`, `qen pr status`, etc.

**Behavior (unchanged in concept, different in implementation):**

1. Read `current_project` from main config
2. Read project config to get `repo` field
3. Operate on repos in `{repo}/{folder}/repos/`

## Archive Model

**Remote meta repository** (e.g., `github.com/org/meta`) serves as:

- **Archive** of all project work
- **PR workflow** for reviewing project contexts
- **Historical record** of development

**Flow:**

1. Developer creates project: `qen init myproj`
   - Creates `meta-myproj/` locally
   - Pushes branch `251210-myproj` to remote

2. Developer works in `meta-myproj/`
   - Adds repos, makes changes
   - Commits to local branch

3. Developer pushes updates
   - `git push` from within `meta-myproj/`
   - Branch `251210-myproj` updated on remote

4. Developer creates PR (manually or via qen)
   - PR: `251210-myproj` → `main`
   - Review/discussion happens on remote

5. Project merged/archived
   - PR merged to `main` (or closed)
   - `meta-myproj/` can be deleted locally when done

## Benefits

1. **True multi-project support** - Work on multiple projects simultaneously
2. **Zero branch-switching friction** - Each project stays in its state
3. **IDE-friendly** - No disruption from branch switches
4. **Safe isolation** - Impossible to accidentally commit to wrong project
5. **Standard git workflow** - Each per-project meta is just a normal git clone
6. **Visible workspaces** - All projects visible in directory listing
7. **Simple cleanup** - Delete `meta-{project}/` when done

## Trade-offs

**Pros:**

- Solves all four critical problems
- Simpler mental model (each project is a directory)
- Works with standard git tooling

**Cons:**

- Disk space (multiple meta clones)
  - **Mitigation:** Meta repos are tiny (just metadata)
- More directories in workspace
  - **Mitigation:** Standard practice for multi-repo development

## THIS IS A BREAKING CHANGE

Nobody else is using multiple projects with the old model.
Let's make a clean break.

Anyone who needs to work on the old can use `uvx qen@0.3.0`
