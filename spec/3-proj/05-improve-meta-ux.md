# Improve Meta Repository User Experience

## Goal

Make the `meta` repository easier to use by leveraging QEN's existing capabilities to improve discoverability, onboarding, and day-to-day workflows.

## Current State

**What QEN Already Does:**

- Creates dated project folders: `proj/YYMMDD-project-name/`
- Manages multiple repos per project via `pyproject.toml`
- Tracks git status across all repos: `qen status`
- Manages stacked PRs: `qen pr stack`, `qen pr restack`
- Switches between projects: `qen config --switch`

**Current Meta Structure:**

- Mixed structure: some projects in `proj/`, some at root (e.g., `2025-12-01-speed-week/`)
- No clear onboarding guide in meta itself
- Users must know QEN exists and how to use it
- No discoverability of active projects or how to join them

## Problems to Solve

### 1. **Discoverability**: How do new team members discover QEN?

- Meta repo has no README explaining the QEN workflow
- No visible guide for "I just cloned meta, now what?"

### 2. **Project Discovery**: How do users find active projects?

- No easy way to see what projects exist
- No way to know which projects are active vs archived
- Can't tell what a project is about without diving into folders

### 3. **Onboarding**: How do new users get started?

- No step-by-step guide in meta itself
- Users must read QEN README separately
- No "quick win" to validate setup

### 4. **Consistency**: Mixed project structure causes confusion

- Some projects in `proj/`, some at root level
- Inconsistent naming (dated vs non-dated)
- No clear migration path for old projects

## Proposed Improvements

### Improvement 1: Add Meta README

**File**: `~/GitHub/meta/README.md`

**Content**:

```markdown
# Meta Repository

This repository uses [QEN](https://github.com/data-yaml/qen) to manage multi-repository projects.

## Quick Start

### First Time Setup

```bash
# Initialize QEN (discovers meta repo location)
uvx qen init

# List available projects
uvx qen config --list

# Switch to a project
uvx qen config --switch PROJECT_NAME
```

### Working on a Project

```bash
# Check status of all repos in current project
uvx qen status

# Check PR status
uvx qen pr status

# Manage stacked PRs
uvx qen pr stack
uvx qen pr restack
```

### Creating a New Project

```bash
# Create a new project (auto-creates dated folder + branch)
uvx qen init my-new-project

# Add repositories to your project
uvx qen add myorg/myrepo --branch feature-branch
```

## Active Projects

See `proj/` directory for all projects. Each project folder contains:

- `README.md` - Project overview and context
- `pyproject.toml` - Repository configuration
- `repos/` - Working copies of repositories (gitignored)

## Requirements

- Python 3.12+
- Git
- GitHub CLI (`gh`) for PR operations

## Documentation

- [QEN User Guide](https://github.com/data-yaml/qen#readme)
- [QEN for Developers](https://github.com/data-yaml/qen/blob/main/AGENTS.md)

```log

### Improvement 2: Add Project List Command

**New Command**: `qen list`

**Purpose**: Show all projects in meta repo with status

**Output**:
```log

Active Projects:
  2025-12-05-benchling-stacked  (4 repos, 2 open PRs)
  2025-12-01-speed-week         (3 repos)

Use 'qen config --switch PROJECT_NAME' to switch projects
Use 'qen status' to see details for current project

```

**Implementation**:

- Scan `proj/` directory for project folders
- Read each `pyproject.toml` to count repos
- Optionally check for open PRs (if `gh` available)
- Show current project with indicator

### Improvement 3: Migration Tool for Legacy Projects

**New Command**: `qen migrate PROJECT_PATH`

**Purpose**: Move root-level projects to `proj/` structure

**Example**:

```bash
# Migrate old project structure
qen migrate 2025-12-01-speed-week

# Creates: proj/2025-12-01-speed-week/
# Moves: README.md, pyproject.toml, etc.
# Updates: git branch, config references
```

### Improvement 4: Project Templates

**Enhancement**: Improve `qen init` to create better project READMEs

**Current**: Minimal README stub
**Improved**: Template with sections:

```markdown
# project-name

Project created on (date)

## Overview

[Describe the project purpose and goals]

## Repositories

See `pyproject.toml` ([tool.qen] section) for the list of repositories.

## Getting Started

```bash
# Check status
qen status

# Check PRs
qen pr status
```

## Links

- [Related Issue](https://github.com/org/repo/issues/XXX)
- [Design Doc](link)

```log

### Improvement 5: Better Status Output

**Enhancement**: Make `qen status` output more informative

**Current**: Basic git status per repo
**Improved**:
- Show ahead/behind commit counts
- Highlight uncommitted changes
- Show PR status inline (if available)
- Color coding for quick scanning

### Improvement 6: Project Archive Command

**New Command**: `qen archive PROJECT_NAME`

**Purpose**: Mark projects as archived without deleting

**Behavior**:
- Moves to `proj/archived/PROJECT_NAME/`
- Updates config to mark as archived
- `qen list` shows separately

## Implementation Priority

### Phase 1: Documentation (Immediate)
1. ✅ Add `meta/README.md` with QEN quick start
2. ✅ Update project template README in `qen init`

### Phase 2: Discoverability (High Priority)
3. ✅ Add `qen list` command to show all projects
4. ✅ Enhance `qen status` with better formatting

### Phase 3: Migration (Medium Priority)
5. Add `qen migrate` command for legacy projects
6. Document migration process in meta README

### Phase 4: Organization (Nice to Have)
7. Add `qen archive` command
8. Add project search/filter to `qen list`

## Success Metrics

1. **New team members can get started in < 5 minutes**
   - Clone meta → Read README → Run `uvx qen init` → Done

2. **Project discovery is instant**
   - Run `qen list` → See all projects → Switch to one

3. **Consistent structure**
   - All projects in `proj/`
   - All use dated naming
   - All have proper READMEs

4. **Better daily workflow**
   - `qen status` gives clear overview
   - `qen pr status` shows everything at a glance
   - No manual git commands needed

## Open Questions

1. Should `qen init` automatically create a meta README if it doesn't exist?
2. Should `qen list` be the default command (no arguments)?
3. Should archived projects be in `proj/archived/` or `archived/`?
4. Should `qen status` auto-fetch by default?

## Files to Modify

- `src/qen/commands/list.py` (NEW) - Project listing
- `src/qen/commands/migrate.py` (NEW) - Legacy migration
- `src/qen/commands/archive.py` (NEW) - Project archival
- `src/qen/commands/status.py` (MODIFY) - Better formatting
- `src/qen/project.py` (MODIFY) - Better README template
- `src/qen/cli.py` (MODIFY) - Register new commands

## Non-Goals

- ❌ Changing QEN's core philosophy (lightweight, minimal)
- ❌ Adding heavy dependencies or complex features
- ❌ Enforcing strict workflows (remain flexible)
- ❌ Breaking existing projects or configurations
