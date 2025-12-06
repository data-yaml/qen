# qen config - Manage QEN Configuration

## Overview

`qen config` manages QEN configuration, including viewing and switching between projects. It provides visibility into current settings and allows switching the active project context.

## Command Behavior

### Basic Usage

```bash
qen config                          # Show current project config
qen config --list                   # List all projects
qen config my-feature              # Switch to project "my-feature"
qen config --global                # Show global configuration
```

**Note:** The "current project" determines which project commands like `qen status`, `qen push`, and `qen commit` operate on by default.

### What It Does

1. **No arguments** - Displays current project configuration and status
2. **`--list`** - Shows all available projects with their details
3. **Project name argument** - Switches current project to the specified name
4. **`--global`** - Shows global QEN settings

## Current Project Display

### Default View (No Arguments)

```bash
$ qen config
Current project: feature-work

Project Configuration:
  Name:          feature-work
  Branch:        2025-12-05-feature-work
  Created:       2025-12-05T14:30:00Z
  Meta path:     /Users/user/meta-repo
  Project path:  /Users/user/meta-repo/proj/2025-12-05-feature-work

Repositories (3):
  📦 repos/api (feature/api-update)
  📦 repos/frontend (feature/ui-update)
  📦 repos/backend (main)

Quick Actions:
  qen status              Show detailed status
  qen config --list       List all projects
  qen config <name>       Switch projects
```

### When No Project Set

```bash
$ qen config
No current project set.

Available projects (use 'qen config --list' to see all):
  - feature-work
  - bugfix-auth
  - refactor-api

Switch to a project:
  qen config feature-work
```

## List All Projects

### List View

```bash
$ qen config --list
Available projects:

* feature-work (current)
  Branch:        2025-12-05-feature-work
  Created:       2025-12-05T14:30:00Z
  Repositories:  3
  Path:          /Users/user/meta-repo/proj/2025-12-05-feature-work

  bugfix-auth
  Branch:        2025-12-04-bugfix-auth
  Created:       2025-12-04T09:15:00Z
  Repositories:  2
  Path:          /Users/user/meta-repo/proj/2025-12-04-bugfix-auth

  refactor-api
  Branch:        2025-12-01-refactor-api
  Created:       2025-12-01T16:45:00Z
  Repositories:  4
  Path:          /Users/user/meta-repo/proj/2025-12-01-refactor-api

3 projects total
* = current project

Quick Actions:
  qen config <name>       Switch to a project
  qen init <name>         Create new project
```

### Compact List View

```bash
$ qen config --list --compact
Available projects:

* feature-work      3 repos    2025-12-05
  bugfix-auth       2 repos    2025-12-04
  refactor-api      4 repos    2025-12-01

* = current project
```

## Switch Project

### Successful Switch

```bash
$ qen config bugfix-auth
Switched to project: bugfix-auth

Project Configuration:
  Name:          bugfix-auth
  Branch:        2025-12-04-bugfix-auth
  Repositories:  2

Use 'qen status' to see detailed status.
```

### Failed Switch (Project Not Found)

```bash
$ qen config nonexistent-project
Error: Project "nonexistent-project" not found.

Available projects:
  - feature-work
  - bugfix-auth
  - refactor-api

Create a new project:
  qen init nonexistent-project
```

### Fuzzy Matching (Optional Enhancement)

```bash
$ qen config bug
Multiple projects match "bug":
  - bugfix-auth
  - bugfix-payments

Please specify the full project name.
```

## Global Configuration

### Global Settings View

```bash
$ qen config --global
Global QEN Configuration:

Meta Repository:
  Path:         /Users/user/meta-repo
  GitHub org:   myorg

Current Project:
  Name:         feature-work
  Branch:       2025-12-05-feature-work

Settings:
  GitHub CLI:   gh (found)
  Git:          git version 2.39.0

Configuration files:
  Global:       /Users/user/.config/qen/config.toml
  Projects:     /Users/user/.config/qen/projects/

Quick Actions:
  qen config --edit        Edit global config
  qen config --path        Show config file paths
```

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `--list` | List all available projects | false |
| `--compact` | Compact list format (with --list) | false |
| `--global` | Show global configuration | false |
| `--edit` | Open global config in editor | false |
| `--path` | Show configuration file paths | false |
| `--json` | Output in JSON format | false |
| `--repos` | Show repository details (with no args) | false |

### Flag Usage Notes

**`--list`**: List all projects

- Shows all projects in XDG config directory
- Marks current project with `*`
- Shows key details: branch, date, repo count
- Use `--compact` for shorter output

**`--global`**: Show global settings

- Displays meta repo path, GitHub org
- Shows current project
- Checks external tools (gh, git)
- Lists config file locations

**`--edit`**: Edit configuration

- Opens global config in `$EDITOR`
- Validates config after editing
- Shows errors if invalid TOML

**`--json`**: JSON output

- Machine-readable format
- Useful for scripts and integrations
- All data, no formatting

## Configuration File Locations

QEN uses XDG-compliant configuration:

```toml
# Global config: $XDG_CONFIG_HOME/qen/config.toml
# (typically ~/.config/qen/config.toml)

# Current project and meta repo settings
current_project = "feature-work"
meta_path = "/Users/user/meta-repo"
github_org = "myorg"

# Optional settings
[pull]
github_cli = "gh"

[push]
require_confirmation = true

[commit]
auto_add = true
```

```toml
# Per-project config: $XDG_CONFIG_HOME/qen/projects/<project>.toml
# (typically ~/.config/qen/projects/feature-work.toml)

name = "feature-work"
branch = "2025-12-05-feature-work"
folder = "proj/2025-12-05-feature-work"
meta_path = "/Users/user/meta-repo"
created = "2025-12-05T14:30:00Z"
```

## JSON Output Format

### Current Project JSON

```bash
$ qen config --json
```

```json
{
  "current_project": "feature-work",
  "project": {
    "name": "feature-work",
    "branch": "2025-12-05-feature-work",
    "folder": "proj/2025-12-05-feature-work",
    "meta_path": "/Users/user/meta-repo",
    "created": "2025-12-05T14:30:00Z",
    "repositories": [
      {
        "path": "repos/api",
        "url": "https://github.com/myorg/api",
        "branch": "feature/api-update",
        "added": "2025-12-05T14:35:00Z",
        "updated": "2025-12-05T16:20:00Z"
      },
      {
        "path": "repos/frontend",
        "url": "https://github.com/myorg/frontend",
        "branch": "feature/ui-update",
        "added": "2025-12-05T14:36:00Z",
        "updated": "2025-12-05T16:21:00Z"
      }
    ]
  }
}
```

### List Projects JSON

```bash
$ qen config --list --json
```

```json
{
  "current_project": "feature-work",
  "projects": [
    {
      "name": "feature-work",
      "branch": "2025-12-05-feature-work",
      "created": "2025-12-05T14:30:00Z",
      "repository_count": 3,
      "is_current": true
    },
    {
      "name": "bugfix-auth",
      "branch": "2025-12-04-bugfix-auth",
      "created": "2025-12-04T09:15:00Z",
      "repository_count": 2,
      "is_current": false
    }
  ]
}
```

## Integration Points

### With Other Commands

- `qen init <project>` - Creates new project, automatically switches to it
- `qen status` - Uses current project from config
- `qen push` - Uses current project from config
- `qen commit` - Uses current project from config
- `qen pull` - Uses current project from config

### Environment Variables

**`QEN_PROJECT`**: Override current project for single command

```bash
QEN_PROJECT=bugfix-auth qen status
```

Useful for scripts and automation without changing global config.

## Implementation Details

### Loading Current Project

```python
from pathlib import Path
from qen.config import QenConfig

def get_current_project() -> str | None:
    """Get the current project name from global config."""
    config = QenConfig.load()
    return config.current_project

def load_current_project_config() -> ProjectConfig:
    """Load configuration for current project."""
    project_name = get_current_project()
    if not project_name:
        raise ValueError("No current project set. Use 'qen config <project>'.")

    return load_project_config(project_name)
```

### Listing Projects

```python
from pathlib import Path
from qenvy import XDGStorage

def list_all_projects() -> list[ProjectSummary]:
    """List all available projects."""
    storage = XDGStorage("qen", "projects")
    project_files = storage.config_path.glob("*.toml")

    projects = []
    for project_file in project_files:
        try:
            config = storage.load_profile(project_file.stem)
            projects.append(ProjectSummary(
                name=config["name"],
                branch=config["branch"],
                created=config["created"],
                repository_count=count_repositories(config),
            ))
        except Exception:
            # Skip invalid project files
            continue

    return sorted(projects, key=lambda p: p.created, reverse=True)

def count_repositories(project_config: dict) -> int:
    """Count repositories in project."""
    from qen.pyproject_utils import load_repos_from_pyproject

    meta_path = Path(project_config["meta_path"])
    project_dir = meta_path / project_config["folder"]

    try:
        repos = load_repos_from_pyproject(project_dir)
        return len(repos)
    except Exception:
        return 0
```

### Switching Projects

```python
def switch_project(project_name: str) -> None:
    """Switch to a different project."""
    # Verify project exists
    project_config = load_project_config(project_name)

    # Update global config
    config = QenConfig.load()
    config.current_project = project_name
    config.save()

    print(f"Switched to project: {project_name}")

def load_project_config(project_name: str) -> dict:
    """Load configuration for a specific project."""
    storage = XDGStorage("qen", "projects")

    try:
        config = storage.load_profile(project_name)
        return config
    except FileNotFoundError:
        raise ValueError(f"Project \"{project_name}\" not found.")
```

### Display Functions

```python
def display_current_project() -> None:
    """Display current project configuration."""
    try:
        project_name = get_current_project()
        if not project_name:
            display_no_current_project()
            return

        config = load_project_config(project_name)
        repos = load_repos_from_pyproject(
            Path(config["meta_path"]) / config["folder"]
        )

        print(f"Current project: {project_name}\n")
        print("Project Configuration:")
        print(f"  Name:          {config['name']}")
        print(f"  Branch:        {config['branch']}")
        print(f"  Created:       {config['created']}")
        print(f"  Meta path:     {config['meta_path']}")
        print(f"  Project path:  {config['meta_path']}/{config['folder']}")

        print(f"\nRepositories ({len(repos)}):")
        for repo in repos:
            print(f"  📦 {repo.path} ({repo.branch})")

        print("\nQuick Actions:")
        print("  qen status              Show detailed status")
        print("  qen config --list       List all projects")
        print("  qen config <name>       Switch projects")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def display_no_current_project() -> None:
    """Display message when no project is set."""
    print("No current project set.\n")

    # List available projects
    projects = list_all_projects()
    if projects:
        print("Available projects (use 'qen config --list' to see all):")
        for project in projects[:5]:  # Show first 5
            print(f"  - {project.name}")
        if len(projects) > 5:
            print(f"  ... and {len(projects) - 5} more")
    else:
        print("No projects found. Create one:")
        print("  qen init <project-name>")

    print("\nSwitch to a project:")
    print("  qen config <project-name>")

def display_project_list(compact: bool = False) -> None:
    """Display list of all projects."""
    projects = list_all_projects()
    current = get_current_project()

    if not projects:
        print("No projects found.")
        print("\nCreate a project:")
        print("  qen init <project-name>")
        return

    print("Available projects:\n")

    for project in projects:
        is_current = project.name == current
        marker = "* " if is_current else "  "

        if compact:
            date = project.created.split("T")[0]
            print(f"{marker}{project.name:<20} {project.repository_count} repos    {date}")
        else:
            print(f"{marker}{project.name}{' (current)' if is_current else ''}")
            print(f"  Branch:        {project.branch}")
            print(f"  Created:       {project.created}")
            print(f"  Repositories:  {project.repository_count}")
            if project.path:
                print(f"  Path:          {project.path}")
            print()

    print(f"{len(projects)} projects total")
    print("* = current project\n")

    print("Quick Actions:")
    print("  qen config <name>       Switch to a project")
    print("  qen init <name>         Create new project")
```

## Error Conditions

- **No current project**: "No current project set. Use 'qen config <project>' to switch."
- **Project not found**: "Project '<name>' not found. Use 'qen config --list' to see available projects."
- **Invalid config file**: "Configuration file is invalid: <error details>"
- **Config file not writable**: "Cannot write to configuration file: <error details>"
- **No projects found**: "No projects found. Create one with 'qen init <project>'."

## Examples

### Example 1: Show current project

```bash
$ qen config
Current project: feature-work

Project Configuration:
  Name:          feature-work
  Branch:        2025-12-05-feature-work
  Created:       2025-12-05T14:30:00Z
  Meta path:     /Users/user/meta-repo
  Project path:  /Users/user/meta-repo/proj/2025-12-05-feature-work

Repositories (3):
  📦 repos/api (feature/api-update)
  📦 repos/frontend (feature/ui-update)
  📦 repos/backend (main)

Quick Actions:
  qen status              Show detailed status
  qen config --list       List all projects
  qen config <name>       Switch projects
```

### Example 2: List all projects

```bash
$ qen config --list
Available projects:

* feature-work (current)
  Branch:        2025-12-05-feature-work
  Created:       2025-12-05T14:30:00Z
  Repositories:  3
  Path:          /Users/user/meta-repo/proj/2025-12-05-feature-work

  bugfix-auth
  Branch:        2025-12-04-bugfix-auth
  Created:       2025-12-04T09:15:00Z
  Repositories:  2
  Path:          /Users/user/meta-repo/proj/2025-12-04-bugfix-auth

2 projects total
* = current project

Quick Actions:
  qen config <name>       Switch to a project
  qen init <name>         Create new project
```

### Example 3: Switch projects

```bash
$ qen config bugfix-auth
Switched to project: bugfix-auth

Project Configuration:
  Name:          bugfix-auth
  Branch:        2025-12-04-bugfix-auth
  Repositories:  2

Use 'qen status' to see detailed status.
```

### Example 4: Show global config

```bash
$ qen config --global
Global QEN Configuration:

Meta Repository:
  Path:         /Users/user/meta-repo
  GitHub org:   myorg

Current Project:
  Name:         feature-work
  Branch:       2025-12-05-feature-work

Settings:
  GitHub CLI:   gh (found)
  Git:          git version 2.39.0

Configuration files:
  Global:       /Users/user/.config/qen/config.toml
  Projects:     /Users/user/.config/qen/projects/

Quick Actions:
  qen config --edit        Edit global config
  qen config --path        Show config file paths
```

### Example 5: Compact list

```bash
$ qen config --list --compact
Available projects:

* feature-work      3 repos    2025-12-05
  bugfix-auth       2 repos    2025-12-04
  refactor-api      4 repos    2025-12-01

* = current project
```

### Example 6: JSON output

```bash
$ qen config --json
{
  "current_project": "feature-work",
  "project": {
    "name": "feature-work",
    "branch": "2025-12-05-feature-work",
    "folder": "proj/2025-12-05-feature-work",
    "meta_path": "/Users/user/meta-repo",
    "created": "2025-12-05T14:30:00Z",
    "repositories": [
      {
        "path": "repos/api",
        "url": "https://github.com/myorg/api",
        "branch": "feature/api-update"
      }
    ]
  }
}
```

### Example 7: Environment variable override

```bash
$ QEN_PROJECT=bugfix-auth qen status
# Shows status for bugfix-auth project without switching globally
```

## Design Decisions

1. **Current project persistence** - Stored in global config, survives shell sessions
2. **XDG compliance** - Uses `$XDG_CONFIG_HOME/qen/` for all configuration
3. **Project detection** - Scans `projects/*.toml` files to list available projects
4. **No project merging** - Switching projects is complete context switch
5. **Environment override** - `QEN_PROJECT` env var allows temporary override

## Related Specifications

- [1-qen-init.md](../1-qen-init/1-qen-init.md) - Creating new projects
- [4-qen-status.md](../1-qen-init/4-qen-status.md) - Viewing project status
- [01-qen-pull.md](01-qen-pull.md) - Pull operations use current project
- [02-qen-push.md](02-qen-push.md) - Push operations use current project
