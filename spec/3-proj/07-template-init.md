# Spec: Template-Based Project Initialization

## Overview

Move hardcoded README.md and pyproject.toml content from Python strings into template files stored in `./proj` directory at the repository root. Use Python's `string.Template` for variable substitution.

## User Requirements

1. Templates must be in `./proj` at repository root (flat structure)
2. Use `string.Template` for variable substitution
3. Include all known variables that would be helpful
4. Template files MUST be included in distribution package
5. Fail hard if template files are missing (no fallback)
6. Template files: README.md, pyproject.toml, and .gitignore

## Current State

### Files Affected

- `src/qen/project.py:111-196` - `create_project_structure()` function
- `src/qen/project.py:199-232` - `add_gitignore_entry()` function (will be removed)
- `src/qen/commands/init.py` - Pass github_org to create_project()
- `pyproject.toml` - Package data configuration

### Current Implementation

```python
def create_project_structure(meta_path, project_name, branch_name, folder_path):
    # Creates project directory
    # Hardcoded README.md content (lines 140-169)
    readme_content = f"""# {project_name}
    ...
    """

    # Hardcoded pyproject.toml content (lines 172-189)
    pyproject_content = f"""# qen proj configuration
    ...
    """
```

## Proposed Solution

### 1. Create Template Files

Create three template files in repository root:

**`./proj/README.md`**

```markdown
# ${project_name}

Project created on ${date}

## Overview

(Add project description here)

## Repositories

See `pyproject.toml` ([tool.qen] section) for the list of repositories in this project.

## Getting Started

```bash
# Clone all repositories
qen clone

# Pull latest changes
qen pull

# Check status
qen status
```

**`./proj/pyproject.toml`**

```toml
# qen proj configuration
# Add repositories using: qen add <repo-url>

[tool.qen]
created = "${timestamp}"
branch = "${branch_name}"

# Example repository:
# [[tool.qen.repos]]
# url = "https://github.com/${github_org}/repo"
# branch = "main"
# path = "repos/repo"
```

**`./proj/.gitignore`**

```text
repos/
```

### 2. Template Variables

Make these variables available to templates:

- `${project_name}` - Project name (e.g., "my-feature")
- `${date}` - Creation date in YYYY-MM-DD format (note: branch/folder use YYMMDD)
- `${timestamp}` - ISO 8601 timestamp (full datetime)
- `${branch_name}` - Git branch name (e.g., "251207-my-feature")
- `${folder_path}` - Relative folder path (e.g., "proj/251207-my-feature")
- `${github_org}` - GitHub organization from config

### 3. Update `src/qen/project.py`

Modify `create_project_structure()` function:

```python
from string import Template
from pathlib import Path
import importlib.resources

def get_template_path(template_name: str) -> Path:
    """Get path to template file, ensuring it exists in distribution.

    Raises:
        ProjectError: If template file is missing
    """
    # Try to get from package data first (for installed package)
    try:
        if hasattr(importlib.resources, 'files'):
            # Python 3.9+
            template_file = importlib.resources.files('qen') / '..' / '..' / 'proj' / template_name
            if template_file.is_file():
                return Path(str(template_file))
    except Exception:
        pass

    # Fallback to relative path (for development)
    # Find package root by going up from this file
    package_root = Path(__file__).parent.parent.parent
    template_path = package_root / 'proj' / template_name

    if not template_path.exists():
        raise ProjectError(
            f"Template file not found: {template_name}. "
            f"Expected at: {template_path}. "
            "This indicates a packaging error - templates must be included in distribution."
        )

    return template_path

def render_template(template_path: Path, **variables) -> str:
    """Render template file with given variables using string.Template.

    Args:
        template_path: Path to template file
        **variables: Template variables

    Returns:
        Rendered template content

    Raises:
        ProjectError: If template rendering fails
    """
    try:
        template_content = template_path.read_text()
        template = Template(template_content)
        return template.substitute(**variables)
    except KeyError as e:
        raise ProjectError(f"Missing template variable: {e}") from e
    except Exception as e:
        raise ProjectError(f"Failed to render template {template_path.name}: {e}") from e

def create_project_structure(
    meta_path: Path,
    project_name: str,
    branch_name: str,
    folder_path: str,
    github_org: str | None = None
) -> None:
    """Create project directory structure from templates.

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        branch_name: Git branch name
        folder_path: Project folder path (relative to meta repo)
        github_org: GitHub organization (optional)
    """
    # Create project directory
    project_dir = meta_path / folder_path
    try:
        project_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise ProjectError(f"Project directory already exists: {project_dir}") from None
    except Exception as e:
        raise ProjectError(f"Failed to create project directory: {e}") from e

    # Prepare template variables
    now = datetime.now(UTC)
    template_vars = {
        'project_name': project_name,
        'date': now.strftime("%Y-%m-%d"),
        'timestamp': now.isoformat(),
        'branch_name': branch_name,
        'folder_path': folder_path,
        'github_org': github_org or 'your-org',
    }

    # Render and write README.md
    try:
        readme_template = get_template_path('README.md')
        readme_content = render_template(readme_template, **template_vars)
        (project_dir / "README.md").write_text(readme_content)
    except Exception as e:
        raise ProjectError(f"Failed to create README.md: {e}") from e

    # Render and write pyproject.toml
    try:
        pyproject_template = get_template_path('pyproject.toml')
        pyproject_content = render_template(pyproject_template, **template_vars)
        (project_dir / "pyproject.toml").write_text(pyproject_content)
    except Exception as e:
        raise ProjectError(f"Failed to create pyproject.toml: {e}") from e

    # Render and write .gitignore
    try:
        gitignore_template = get_template_path('.gitignore')
        gitignore_content = render_template(gitignore_template, **template_vars)
        (project_dir / ".gitignore").write_text(gitignore_content)
    except Exception as e:
        raise ProjectError(f"Failed to create .gitignore: {e}") from e

    # Create repos/ directory
    try:
        (project_dir / "repos").mkdir(exist_ok=False)
    except Exception as e:
        raise ProjectError(f"Failed to create repos/ directory: {e}") from e
```

### 4. Update `create_project()` function

Modify the function signature to pass `github_org`:

```python
def create_project(
    meta_path: Path,
    project_name: str,
    date: datetime | None = None,
    github_org: str | None = None,
) -> tuple[str, str]:
    """Create a new project in the meta repository.

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        date: Date to use for prefixes (default: current date)
        github_org: GitHub organization (default: None)
    """
    # ... existing code ...

    # Create project structure with github_org
    try:
        create_project_structure(
            meta_path,
            project_name,
            branch_name,
            folder_path,
            github_org
        )
    except Exception as e:
        raise e

    # REMOVE the add_gitignore_entry() call - now handled by template

    # ... rest of function ...
```

### 5. Update `src/qen/commands/init.py`

Pass `github_org` from config to `create_project()`:

```python
def init_project(project_name: str, ...):
    # ... existing code ...

    # Read main config to get meta_path and org
    try:
        main_config = config.read_main_config()
        meta_path = Path(main_config["meta_path"])
        github_org = main_config.get("org")  # Get org from config
    except QenConfigError as e:
        click.echo(f"Error reading configuration: {e}", err=True)
        raise click.Abort() from e

    # ... existing code ...

    # Create project with github_org
    try:
        branch_name, folder_path = create_project(
            meta_path,
            project_name,
            date=now,
            github_org=github_org  # Pass org to create_project
        )
    except ProjectError as e:
        click.echo(f"Error creating project: {e}", err=True)
        raise click.Abort() from e
```

### 6. Update `pyproject.toml` Package Data

Ensure template files are included in distribution:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/qen", "src/qenvy"]

[tool.hatch.build.targets.wheel.force-include]
"proj/README.md" = "proj/README.md"
"proj/pyproject.toml" = "proj/pyproject.toml"
"proj/.gitignore" = "proj/.gitignore"

# OR use patterns:
[tool.hatch.build]
include = [
    "src/**",
    "proj/README.md",
    "proj/pyproject.toml",
    "proj/.gitignore",
]
```

## Implementation Steps

1. **Create template files**
   - Create `./proj/README.md` with variable placeholders
   - Create `./proj/pyproject.toml` with variable placeholders
   - Create `./proj/.gitignore` with variable placeholders

2. **Update project.py**
   - Add `get_template_path()` helper function
   - Add `render_template()` helper function
   - Modify `create_project_structure()` to use templates
   - Update `create_project()` signature to accept `github_org`
   - **Remove** `add_gitignore_entry()` function (replaced by template)

3. **Update init.py**
   - Pass `github_org` from config to `create_project()`

4. **Update pyproject.toml**
   - Add template files to package distribution

5. **Test**
   - Unit tests: Template rendering with all variables
   - Unit tests: Missing template file error handling
   - Unit tests: Invalid template variable error handling
   - Integration tests: Full project creation with templates
   - Manual test: Install package and verify templates are included

## Success Criteria

- ✅ Template files exist at `./proj/README.md`, `./proj/pyproject.toml`, and `./proj/.gitignore`
- ✅ Templates use `${variable}` syntax for substitution
- ✅ All variables are properly substituted during project creation
- ✅ Template files are included in distribution package
- ✅ Hard failure with clear error if templates are missing
- ✅ Existing tests pass
- ✅ New tests cover template rendering and error cases
- ✅ Manual verification: `pip install` includes templates

## Testing Strategy

### Unit Tests (`tests/unit/qen/test_project.py`)

1. Test `get_template_path()`:
   - Returns correct path for existing templates
   - Raises ProjectError for missing templates

2. Test `render_template()`:
   - Renders all variables correctly
   - Raises ProjectError for missing variables
   - Handles special characters in variables

3. Test `create_project_structure()`:
   - Creates files with rendered template content
   - All variables appear in output files
   - Proper error handling

### Integration Tests

1. End-to-end project creation with templates
2. Verify all template variables in created files
3. Test with and without github_org

## Rollout

This is a breaking change only if:

- Users have customized the hardcoded templates (not possible)
- Distribution package is missing template files (caught by tests)

Mitigation:


- Add CI check to verify templates in distribution
- Document template locations in README
- Version bump: minor (0.2.0) as it's a feature enhancement

## Future Enhancements (Not in Scope)

- Support for additional template files (LICENSE, CONTRIBUTING.md, etc.)
- User-customizable templates via config
- Jinja2 upgrade for conditional logic
- Template validation
