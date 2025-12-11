"""Project initialization and management for qen.

This module provides functionality for creating and managing qen projects
within a meta repository. It handles:
- Project directory structure creation
- Branch creation
- Stub file generation (README.md, meta.toml)
- .gitignore management
- Project context discovery
"""

import importlib.resources
import re
from datetime import UTC, datetime
from pathlib import Path
from string import Template

from .git_utils import create_branch, run_git_command


class ProjectError(Exception):
    """Base exception for project-related errors."""

    pass


class ProjectNotFoundError(ProjectError):
    """Raised when project cannot be found in current context."""

    pass


def parse_project_name(name: str) -> tuple[str, str | None]:
    """Parse project name to extract config name and explicit branch.

    This function determines whether the provided name is:
    1. A short name (e.g., "myproj") - requires date prefix generation
    2. A fully-qualified name (e.g., "251210-myproj") - uses name as branch directly

    The YYMMDD pattern must be exactly 6 digits. Names like "12345-proj" or
    "abc-proj" are treated as short names, not date-prefixed branches.

    Args:
        name: Project name provided by user (short or fully-qualified)

    Returns:
        Tuple of (config_name, explicit_branch):
        - config_name: Name to use for config file storage
        - explicit_branch: Branch name if YYMMDD- pattern detected, None otherwise

    Examples:
        >>> parse_project_name("myproj")
        ("myproj", None)

        >>> parse_project_name("251210-myproj")
        ("251210-myproj", "251210-myproj")

        >>> parse_project_name("12345-proj")  # Not 6 digits
        ("12345-proj", None)

        >>> parse_project_name("abc-proj")  # Not digits
        ("abc-proj", None)
    """
    # Check if name matches YYMMDD-* pattern (exactly 6 digits followed by hyphen)
    if re.match(r"^\d{6}-", name):
        # Fully-qualified name: use it as both config name and branch
        return (name, name)
    else:
        # Short name: config name only, branch will be generated
        return (name, None)


def generate_branch_name(project_name: str, date: datetime | None = None) -> str:
    """Generate a branch name with date prefix.

    Format: YYMMDD-<project-name>

    Uses local time for user-facing branch names (not UTC).
    This ensures the date matches what the user sees on their calendar.

    Args:
        project_name: Name of the project
        date: Date to use (default: current local date)

    Returns:
        Branch name with date prefix
    """
    if date is None:
        date = datetime.now()  # Local time for user-facing branch names

    date_prefix = date.strftime("%y%m%d")
    return f"{date_prefix}-{project_name}"


def generate_folder_path(project_name: str, date: datetime | None = None) -> str:
    """Generate a folder path with date prefix.

    Format: proj/YYMMDD-<project-name>

    Uses local time for user-facing paths (not UTC).
    This ensures the date matches what the user sees on their calendar.

    Args:
        project_name: Name of the project
        date: Date to use (default: current local date)

    Returns:
        Folder path relative to meta repo root
    """
    if date is None:
        date = datetime.now()  # Local time for user-facing paths

    date_prefix = date.strftime("%y%m%d")
    return f"proj/{date_prefix}-{project_name}"


def find_project_root(start_path: Path | None = None) -> Path:
    """Find project root directory by searching for pyproject.toml with [tool.qen].

    Searches current directory and parent directories for a pyproject.toml file
    that contains a [tool.qen] section.

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to project root directory

    Raises:
        ProjectNotFoundError: If no project root can be found
    """
    if start_path is None:
        start_path = Path.cwd()

    # Ensure start_path is absolute
    start_path = start_path.resolve()

    # Search upward for pyproject.toml with [tool.qen]
    current = start_path
    for directory in [current] + list(current.parents):
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.exists():
            try:
                # Check if it has [tool.qen] section
                from qenvy.formats import TOMLHandler

                handler = TOMLHandler()
                config = handler.read(pyproject_path)
                if "tool" in config and "qen" in config["tool"]:
                    return directory
            except Exception:
                # Skip if we can't read the file
                continue

    raise ProjectNotFoundError(
        "Not in a qen project directory. Run 'qen init <project>' to create a project."
    )


def get_template_path(template_name: str) -> Path:
    """Get the path to a template file.

    Templates are stored in ./proj directory at repository root.
    Tries to locate the template in the installed package first,
    then falls back to the development source tree.

    Args:
        template_name: Name of the template file (e.g., 'README.md')

    Returns:
        Path to the template file

    Raises:
        ProjectError: If template file cannot be found
    """
    # Try installed package location first (Python 3.9+)
    try:
        # importlib.resources.files() returns a Traversable
        package_files = importlib.resources.files("qen")
        # Templates are in proj/ directory at repo root, which is ../../proj from qen package
        template_path = package_files / ".." / ".." / "proj" / template_name
        # Check if the template exists by trying to read it
        if hasattr(template_path, "is_file") and template_path.is_file():
            return Path(str(template_path))
    except (TypeError, AttributeError, FileNotFoundError):
        pass

    # Fall back to development location
    # Find repo root by going up from src/qen/project.py
    repo_root = Path(__file__).parent.parent.parent
    template_path = repo_root / "proj" / template_name

    if template_path.exists():
        return template_path

    raise ProjectError(
        f"Template file not found: {template_name}. "
        f"Expected at: {template_path}. "
        "This indicates a packaging error - templates must be included in distribution."
    )


def render_template(template_path: Path, **variables: str | None) -> str:
    """Render a template file with the given variables.

    Uses string.Template for safe variable substitution.

    Args:
        template_path: Path to template file
        **variables: Variables to substitute in the template

    Returns:
        Rendered template content

    Raises:
        ProjectError: If template rendering fails
    """
    try:
        template_content = template_path.read_text()
        template = Template(template_content)
        return template.safe_substitute(**variables)
    except FileNotFoundError:
        raise ProjectError(f"Template file not found: {template_path}") from None
    except Exception as e:
        raise ProjectError(f"Failed to render template {template_path.name}: {e}") from e


def create_project_structure(
    meta_path: Path,
    project_name: str,
    branch_name: str,
    folder_path: str,
    github_org: str | None = None,
) -> None:
    """Create project directory structure in meta repository.

    Creates:
    - proj/YYYY-MM-DD-<project-name>/
    - proj/YYYY-MM-DD-<project-name>/README.md (from template)
    - proj/YYYY-MM-DD-<project-name>/pyproject.toml (from template)
    - proj/YYYY-MM-DD-<project-name>/.gitignore (from template)
    - proj/YYYY-MM-DD-<project-name>/repos/ (directory)

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        branch_name: Git branch name
        folder_path: Project folder path (relative to meta repo)
        github_org: GitHub organization (default: 'your-org')

    Raises:
        ProjectError: If directory creation fails
    """
    # Create the project directory
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
        "project_name": project_name,
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        "branch_name": branch_name,
        "folder_path": folder_path,
        "github_org": github_org or "your-org",
        "meta_path": str(meta_path),
    }

    # Render and write README.md
    readme_template = get_template_path("README.md")
    readme_content = render_template(readme_template, **template_vars)
    readme_path = project_dir / "README.md"
    try:
        readme_path.write_text(readme_content)
    except Exception as e:
        raise ProjectError(f"Failed to create README.md: {e}") from e

    # Render and write pyproject.toml
    pyproject_template = get_template_path("pyproject.toml")
    pyproject_content = render_template(pyproject_template, **template_vars)
    pyproject_path = project_dir / "pyproject.toml"
    try:
        pyproject_path.write_text(pyproject_content)
    except Exception as e:
        raise ProjectError(f"Failed to create pyproject.toml: {e}") from e

    # Render and write .gitignore
    gitignore_template = get_template_path(".gitignore")
    gitignore_content = render_template(gitignore_template, **template_vars)
    gitignore_path = project_dir / ".gitignore"
    try:
        gitignore_path.write_text(gitignore_content)
    except Exception as e:
        raise ProjectError(f"Failed to create .gitignore: {e}") from e

    # Render and write qen executable wrapper
    qen_template = get_template_path("qen")
    qen_content = render_template(qen_template, **template_vars)
    qen_path = project_dir / "qen"
    try:
        qen_path.write_text(qen_content)
        # Make executable (chmod +x)
        qen_path.chmod(0o755)
    except Exception as e:
        raise ProjectError(f"Failed to create qen executable: {e}") from e

    # Create repos/ directory
    repos_dir = project_dir / "repos"
    try:
        repos_dir.mkdir(exist_ok=False)
    except Exception as e:
        raise ProjectError(f"Failed to create repos/ directory: {e}") from e


def stage_project_files(meta_path: Path, folder_path: str) -> None:
    """Stage project files for commit.

    Args:
        meta_path: Path to meta repository
        folder_path: Project folder path (relative to meta repo)

    Raises:
        ProjectError: If staging fails
    """
    try:
        # Stage the entire project directory
        run_git_command(["add", folder_path], cwd=meta_path)
    except Exception as e:
        raise ProjectError(f"Failed to stage project files: {e}") from e


def commit_project(meta_path: Path, project_name: str, folder_path: str) -> None:
    """Commit project files with a standardized message.

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        folder_path: Project folder path (relative to meta repo)

    Raises:
        ProjectError: If commit fails
    """
    commit_message = f"Initialize project: {project_name}"
    try:
        run_git_command(["commit", "-m", commit_message], cwd=meta_path)
    except Exception as e:
        raise ProjectError(f"Failed to commit project files: {e}") from e


def create_project(
    meta_path: Path,
    project_name: str,
    date: datetime | None = None,
    github_org: str | None = None,
) -> tuple[str, str]:
    """Create a new project in the meta repository.

    This function:
    1. Creates a new branch with date prefix
    2. Creates project directory structure
    3. Creates stub files from templates (README.md, pyproject.toml, .gitignore)
    4. Creates repos/ directory
    5. Stages files for commit
    6. Commits the changes

    Args:
        meta_path: Path to meta repository
        project_name: Name of the project
        date: Date to use for prefixes (default: current date)
        github_org: GitHub organization for templates (default: 'your-org')

    Returns:
        Tuple of (branch_name, folder_path)

    Raises:
        ProjectError: If project creation fails
    """
    # Generate branch and folder names
    # Pass date to generation functions (or None to use local time)
    branch_name = generate_branch_name(project_name, date)
    folder_path = generate_folder_path(project_name, date)

    # Create branch
    try:
        create_branch(meta_path, branch_name, switch=True)
    except Exception as e:
        raise ProjectError(f"Failed to create branch: {e}") from e

    # Create project structure
    try:
        create_project_structure(meta_path, project_name, branch_name, folder_path, github_org)
    except Exception as e:
        # Try to cleanup: switch back to previous branch
        # (but don't fail if this cleanup fails)
        raise e

    # Stage files
    try:
        stage_project_files(meta_path, folder_path)
    except Exception as e:
        raise e

    # Commit changes
    try:
        commit_project(meta_path, project_name, folder_path)
    except Exception as e:
        raise e

    return branch_name, folder_path
