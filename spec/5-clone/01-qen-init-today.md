# qen init <proj> - Quick Reference

## Command
```bash
qen init <project-name>
```

## Steps

### 1. Auto-initialize (if needed)
- Checks if `$XDG_CONFIG_HOME/qen/config.toml` exists
- If not: runs `init_qen()` silently (finds meta repo, extracts org, creates config)

### 2. Generate names (using local time)
```python
branch_name = f"{YYMMDD}-{project_name}"  # e.g., "251210-myproj"
folder_path = f"proj/{YYMMDD}-{project_name}"  # e.g., "proj/251210-myproj"
```

### 3. Create branch
```bash
git checkout -b {branch_name}
```

### 4. Create structure
```text
proj/YYMMDD-project-name/
├── README.md          # from proj/README.md template
├── pyproject.toml     # from proj/pyproject.toml template
├── .gitignore         # from proj/.gitignore template
├── qen                # executable wrapper (chmod +x)
└── repos/             # empty directory (gitignored)
```

### 5. Stage and commit
```bash
git add proj/YYMMDD-project-name
git commit -m "Initialize project: {project_name}"
```

### 6. Push branch
```bash
git push -u origin {branch_name}
```

### 7. Create project config
**File:** `$XDG_CONFIG_HOME/qen/projects/{project_name}.toml`
```toml
branch = "YYMMDD-project-name"
folder = "proj/YYMMDD-project-name"
created = "2025-12-10T12:34:56.789012+00:00"  # ISO8601 UTC
```

### 8. Update main config
**File:** `$XDG_CONFIG_HOME/qen/config.toml`
```toml
current_project = "project-name"
```

### 9. Prompt for PR (if not --yes)
```bash
gh pr create \
  --base main \
  --head {branch_name} \
  --title "Project: {project_name}" \
  --body "Initialize project {project_name}\n\nThis PR creates the project structure for {project_name}."
```

## Source Files
- [src/qen/commands/init.py](../../src/qen/commands/init.py) - Command implementation (`init_project()`)
- [src/qen/project.py](../../src/qen/project.py) - Core logic (`create_project()`)
- [src/qen/config.py](../../src/qen/config.py) - Config management
- [proj/](../../proj/) - Template directory (README.md, pyproject.toml, .gitignore, qen)

## Output
```text
Project 'myproj' created successfully!
  Branch: 251210-myproj
  Directory: /path/to/meta/proj/251210-myproj
  Config: /Users/user/.config/qen/projects/myproj.toml

Would you like to create a pull request for this project? [y/N]: y

✓ Pull request created: https://github.com/org/meta/pull/123

Next steps:
  cd /path/to/meta/proj/251210-myproj
  # Add repositories with: qen add <repo-url>
```

## Key Behaviors
- **Date format:** YYMMDD using **local time** (user-facing)
- **Timestamps:** ISO8601 UTC in config files (machine-facing)
- **Auto-init:** Runs `qen init` automatically if config doesn't exist
- **Force mode:** `--force` deletes existing branch/folder/config before recreating
- **PR creation:** Interactive prompt unless `--yes` flag provided
- **Draft PRs:** Not implemented yet (always creates regular PR)
