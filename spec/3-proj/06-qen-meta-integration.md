# QEN-Meta Integration Analysis

**Status**: Analysis
**Created**: 2025-12-07

## Overview

This document analyzes how QEN functionality could streamline and improve the meta repository workflow described in `~/GitHub/meta/README.md`.

## Current Meta Workflow

The meta repository provides a convention-based approach for managing multi-repo development work:

- Manual git branch creation: `git checkout -b <project-id>`
- Manual directory structure: `mkdir -p proj/<project-id>`
- Documentation-focused: README, spec, arch, plan files
- Philosophy: "Use structure when it helps, skip it when it doesn't"

## Pain Points QEN Solves

### 1. Manual Git Branch Management

**Meta approach**: Manually run `git checkout -b <project-id>`

**QEN improvement**: `uvx qen init my-project` automatically creates the dated branch (`YYMMDD-my-project`) and switches to it

**Benefit**: Enforces consistent naming, eliminates typos, no manual date formatting

### 2. Manual Directory Creation

**Meta approach**: Manually `mkdir -p proj/<project-id>` and `cd proj/<project-id>`

**QEN improvement**: Automatically creates `proj/YYMMDD-my-project/` with proper structure

**Benefit**: One command does everything, impossible to forget the directory or mistype the path

### 3. No Central Repository Tracking

**Meta approach**: No systematic way to track which repos are involved in a project

**QEN improvement**: `pyproject.toml` with `[[tool.qen.repos]]` tracks all sub-repositories

**Benefit**: Machine-readable manifest of dependencies, enables automation

### 4. Manual Git Status Checks Across Repos

**Meta approach**: Must manually `cd` into each repo directory and run `git status`

**QEN improvement**: `uvx qen status` shows git status across all tracked repos at once

**Benefit**: Instant overview of uncommitted changes, unpushed commits across entire project

### 5. No PR Status Visibility

**Meta approach**: Must manually check GitHub for each repo's PRs

**QEN improvement**:
- `uvx qen pr status` shows all PRs across repos
- `uvx qen pr stack` identifies stacked PR dependencies
- `uvx qen pr restack` automatically updates stacked PRs

**Benefit**: See entire PR landscape at a glance, manage complex PR dependencies

### 6. No Configuration Persistence

**Meta approach**: No system for remembering org, meta repo location, etc.

**QEN improvement**: XDG-compliant config stores meta path, GitHub org, active project

**Benefit**: Run QEN commands from anywhere, automatic context switching

### 7. Manual Repository Cloning

**Meta approach**: Manually clone each repo, remember URLs, manage branches

**QEN improvement**: `uvx qen add myrepo` clones to correct location, tracks branch, updates manifest

**Benefit**: Consistent clone locations, branch tracking, automatic gitignore handling

### 8. No Project Context Switching

**Meta approach**: Must manually track which project you're working on

**QEN improvement**:
- `uvx qen config` shows current project
- `uvx qen config --switch other-project` changes active project
- `uvx qen config --list` shows all projects

**Benefit**: Easy context switching when juggling multiple initiatives

### 9. AI Context Enhancement

**Meta approach**: AI must manually discover repos, track locations

**QEN improvement**: `pyproject.toml` gives AI instant project manifest

**Benefit**: AI can immediately understand full project scope without exploration

### 10. Reproducible Setup

**Meta approach**: Project setup is implicit in shell history

**QEN improvement**: `pyproject.toml` is declarative project definition

**Benefit**: Someone else can recreate your workspace: `uvx qen init existing-project` then `uvx qen add` for each repo

### 11. Cross-Platform Config

**Meta approach**: No standard config location

**QEN improvement**: Uses XDG dirs (proper platform conventions)

**Benefit**: Works consistently across macOS, Linux, Windows

## Workflow Comparison

### Before (Pure Meta)

```bash
# Start new project
cd ~/GitHub/meta
git checkout -b 251207-api-refactor
mkdir -p proj/251207-api-refactor
cd proj/251207-api-refactor
touch README.md

# Now manually clone repos...
cd repos  # wait, need to create this
mkdir repos
cd repos
git clone https://github.com/myorg/api
git clone https://github.com/myorg/client

# Check status? cd into each one...
cd api && git status && cd ..
cd client && git status && cd ..

# Check PRs? Visit GitHub manually for each repo...
```

### After (With QEN)

```bash
# Start new project (from anywhere)
uvx qen init api-refactor

# Add repos
uvx qen add api
uvx qen add client

# Check everything at once
uvx qen status

# Check PRs across both repos
uvx qen pr status

# View stacked PR dependencies
uvx qen pr stack
```

## What Meta Does Better (Keep These)

### 1. Flexibility
Meta's README explicitly says "use structure when it helps, skip it when it doesn't"

### 2. Documentation Focus
Meta emphasizes planning docs (spec, arch, plan)

### 3. Lightweight
No tool required, just conventions

### 4. Clear Philosophy
"By writing down your thoughts and context, you expose that to external processing"

## Ideal Hybrid Approach

### Use QEN For

- **Project lifecycle**: init, add repos, switch contexts
- **Git/PR operations**: status, PR management across repos
- **Repository manifest**: tracking URLs, branches, paths
- **Configuration**: persistent state, context switching

### Use Meta Conventions For

- **Documentation structure**: README, spec, arch, plan
- **Helper scripts**: project-specific utilities
- **Artifacts**: logs, test results, design docs
- **Planning and tracking**: task checklists, progress notes

### Result

QEN handles the mechanical/git operations, Meta philosophy guides the documentation and planning. QEN becomes the automation layer beneath Meta's human-focused workflow.

## Integration Opportunities

### 1. Enhanced Project Initialization

QEN could create meta-style documentation stubs:

```bash
uvx qen init my-project --meta-template
# Creates:
# - proj/YYMMDD-my-project/README.md (with meta template)
# - proj/YYMMDD-my-project/01-spec.md
# - proj/YYMMDD-my-project/02-arch.md
# - proj/YYMMDD-my-project/03-plan.md
# - proj/YYMMDD-my-project/pyproject.toml
# - proj/YYMMDD-my-project/repos/ (gitignored)
```

### 2. Documentation Commands

```bash
# Open project documentation
uvx qen doc            # Opens README in $EDITOR
uvx qen doc spec       # Opens 01-spec.md
uvx qen doc arch       # Opens 02-arch.md
uvx qen doc plan       # Opens 03-plan.md
```

### 3. AI Context Export

```bash
# Generate AI context from project
uvx qen export-context
# Creates comprehensive context file with:
# - Project README
# - All spec/arch/plan docs
# - pyproject.toml manifest
# - Git status of all repos
# - PR status across repos
```

### 4. Project Templates

Support different project templates in config:

```toml
[templates.meta]
files = [
    "README.md",
    "01-spec.md",
    "02-arch.md",
    "03-plan.md"
]

[templates.minimal]
files = ["README.md"]
```

### 5. Workspace Commands

```bash
# Open project in IDE with all repos
uvx qen open --ide vscode

# Generate AI briefing
uvx qen brief          # Shows project overview for AI context
```

## Implementation Priority

### Phase 1: Core Integration (Current)
- ✅ Project initialization with dated branches
- ✅ Repository tracking in pyproject.toml
- ✅ Git status across repos
- ✅ PR management commands

### Phase 2: Meta Workflow Enhancement
- [ ] Meta-style documentation templates
- [ ] Documentation commands (doc spec/arch/plan)
- [ ] Template system

### Phase 3: AI Context Enhancement
- [ ] Context export command
- [ ] AI briefing generation
- [ ] Workspace opening commands

## Recommendations

### For Meta Repository Users

1. **Adopt QEN for mechanics**: Use `uvx qen init` instead of manual git/mkdir
2. **Keep meta conventions**: Continue using README, spec, arch, plan structure
3. **Use QEN for operations**: Leverage `qen status`, `qen pr status` for visibility
4. **Store manifest**: Use `pyproject.toml` to track which repos are involved

### For QEN Development

1. **Support meta templates**: Add `--template` flag to `qen init`
2. **Document integration**: Update README with meta workflow examples
3. **Add doc commands**: Quick access to project documentation files
4. **Export capabilities**: Generate comprehensive context for AI tools

## Conclusion

QEN and meta are complementary:

- **Meta provides**: Philosophy, documentation structure, human-readable context
- **QEN provides**: Automation, consistency, mechanical operations, machine-readable manifest

Together they create a powerful workflow where:
- Project setup is automated and consistent
- Documentation follows proven patterns
- Git/PR operations work across all repos
- AI tools have full context via manifest
- Developers can focus on planning and coding rather than setup and status checks

The integration is natural because both share the same core philosophy: lightweight structure that increases velocity without adding bureaucracy.
