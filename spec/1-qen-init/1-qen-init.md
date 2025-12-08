# Spec: qen init

## Overview

Two-mode command for initializing qen tooling and creating new projects in a meta repository.

## Commands

### `qen init` - Initialize qen tooling

**Behavior:**
1. Search for `meta` repo: current dir → parent dirs → ERROR if not found
2. Extract org from git remote URL → ERROR if ambiguous/multiple orgs
3. Create `$XDG_CONFIG_HOME/qen/config.toml` with meta repo info

**Config structure:**
```toml
meta_path = "/path/to/meta"
org = "myorg"
current_project = null
```

### `qen init <proj-name>` - Create new project

**Behavior:**
1. ERROR if project config `$XDG_CONFIG_HOME/qen/<proj-name>.toml` already exists
2. Create branch `YYMMDD-<proj-name>` in meta repo
3. Create directory `proj/YYMMDD-<proj-name>/` with:
   - `README.md` (stub)
   - `pyproject.toml` ([tool.qen] configuration)
   - `repos/` (gitignored)
4. Create `$XDG_CONFIG_HOME/qen/<proj-name>.toml`
5. Update main config: set `current_project = "proj-name"`

**Project config structure:**
```toml
name = "proj-name"
branch = "YYMMDD-proj-name"
folder = "proj/YYMMDD-proj-name"
created = "2025-12-05T10:30:00Z"
```

**pyproject.toml structure:**
```toml
[tool.qen]
created = "2025-12-05T10:30:00Z"

# Will be populated by `qen add`:
# [[tool.qen.repos]]
# url = "https://github.com/org/repo"
# branch = "main"
# path = "repos/repo"
```

## Design Decisions

1. **Fail fast:** Error on any unexpected condition (duplicate names, missing meta, ambiguous org)
2. **Date prefixes:** Use `YYMMDD-` prefix for branches/folders to enable temporal sorting and prevent collisions
3. **Separate configs:** One file per project in qen config dir for future `qen use` command
4. **Simple clones:** Use plain git clones in `repos/`, not gitmodules/worktrees
5. **Use qenvy:** Leverage existing qenvy library for XDG-compliant config management

## Tasks

1. Implement meta repo discovery (upward directory search)
2. Implement git remote parsing for org inference
3. Implement project name uniqueness check
4. Implement branch creation in meta repo
5. Implement directory structure creation
6. Implement stub file generation (README.md, pyproject.toml)
7. Implement config file management (create, update)
8. Add .gitignore entry for `repos/` folder

## Error Conditions

- `meta` repo not found: "Cannot find meta repository. Run from within meta or a subdirectory."
- Ambiguous org: "Multiple organizations detected in git remotes. Please specify explicitly."
- Duplicate project: "Project 'proj-name' already exists at <path-to-config>."
- Not in git repo: "Not in a git repository. qen requires a meta git repository."
