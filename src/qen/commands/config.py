"""Configuration command implementation for qen.

Manages QEN configuration including viewing and switching between projects.
"""

import json

# Use tomllib for Python 3.11+, tomli for older versions
import tomllib
from dataclasses import dataclass
from pathlib import Path

import click

from ..config import QenConfig, QenConfigError
from ..git_utils import GitError, run_git_command
from ..pyproject_utils import PyProjectNotFoundError, load_repos_from_pyproject


class ConfigCommandError(Exception):
    """Base exception for config command errors."""

    pass


@dataclass
class ProjectSummary:
    """Summary information for a project."""

    name: str
    branch: str
    created: str
    repository_count: int
    path: str
    is_current: bool = False


def get_current_project_name(
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
) -> str | None:
    """Get the current project name from global config.

    Args:
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override

    Returns:
        Current project name or None if not set
    """
    # If current_project override provided, use it directly
    if current_project is not None:
        return current_project

    # Use provided config or create one with overrides
    if config is None:
        config = QenConfig(
            config_dir=config_dir,
            meta_path_override=meta_path,
            current_project_override=current_project,
        )

    try:
        main_config = config.read_main_config()
        return main_config.get("current_project")
    except QenConfigError:
        return None


def count_repositories(project_config: dict[str, str]) -> int:
    """Count repositories in a project.

    Args:
        project_config: Project configuration dictionary

    Returns:
        Number of repositories in project
    """
    # Use per-project meta from project config
    if "repo" not in project_config:
        return 0

    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    try:
        repos = load_repos_from_pyproject(project_dir)
        return len(repos)
    except (PyProjectNotFoundError, Exception):
        return 0


def list_all_projects(
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
) -> list[ProjectSummary]:
    """List all available projects.

    Args:
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override

    Returns:
        List of ProjectSummary objects sorted by creation date (newest first)
    """
    # Use provided config or create one with overrides
    if config is None:
        config = QenConfig(
            config_dir=config_dir,
            meta_path_override=meta_path,
            current_project_override=current_project,
        )

    project_names = config.list_projects()
    current_project_name = get_current_project_name(config, config_dir, meta_path, current_project)

    projects: list[ProjectSummary] = []
    for project_name in project_names:
        try:
            project_config = config.read_project_config(project_name)
            repo_count = count_repositories(project_config)

            # Build full path using per-project meta
            if "repo" in project_config:
                per_project_meta = Path(project_config["repo"])
                project_path = str(per_project_meta / project_config["folder"])
            else:
                # Old format - skip
                continue

            projects.append(
                ProjectSummary(
                    name=project_config["name"],
                    branch=project_config["branch"],
                    created=project_config["created"],
                    repository_count=repo_count,
                    path=project_path,
                    is_current=(project_name == current_project_name),
                )
            )
        except (QenConfigError, KeyError):
            # Skip invalid project configurations
            continue

    # Sort by created timestamp (newest first)
    return sorted(projects, key=lambda p: p.created, reverse=True)


def display_current_project(
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
    json_output: bool = False,
    verbose: bool = False,
) -> None:
    """Display current project configuration.

    Args:
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override
        json_output: If True, output in JSON format
        verbose: If True, show config file paths and contents

    Raises:
        click.ClickException: If display fails
    """
    # Use provided config or create one with overrides
    if config is None:
        config = QenConfig(
            config_dir=config_dir,
            meta_path_override=meta_path,
            current_project_override=current_project,
        )

    # Get current project name
    project_name = get_current_project_name(config, config_dir, meta_path, current_project)

    if not project_name:
        if json_output:
            click.echo(json.dumps({"current_project": None}, indent=2))
            return

        # Show available projects
        click.echo("No current project set.\n")

        projects = list_all_projects(config, config_dir, meta_path, current_project)
        if projects:
            click.echo("Available projects (use 'qen config --list' to see all):")
            for project in projects[:5]:  # Show first 5
                click.echo(f"  - {project.name}")
            if len(projects) > 5:
                click.echo(f"  ... and {len(projects) - 5} more")
        else:
            click.echo("No projects found. Create one:")
            click.echo("  qen init <project-name>")

        click.echo("\nSwitch to a project:")
        click.echo("  qen config <project-name>")
        return

    # Load project configuration
    try:
        project_config = config.read_project_config(project_name)
    except QenConfigError as e:
        raise click.ClickException(f"Error loading project configuration: {e}") from e

    # Check for per-project meta (new format)
    if "repo" not in project_config:
        click.echo(
            f"Error: Project '{project_name}' uses old configuration format.\n"
            f"This version requires per-project meta clones.\n"
            f"To migrate: qen init --force {project_name}",
            err=True,
        )
        raise click.Abort()

    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

    # Load repositories
    repos = []
    try:
        repo_configs = load_repos_from_pyproject(project_dir)
        for repo_config in repo_configs:
            repo_path = project_dir / repo_config.path
            # Get current branch if repo exists
            branch = repo_config.branch
            if repo_path.exists():
                try:
                    from ..git_utils import get_current_branch

                    branch = get_current_branch(repo_path)
                except GitError:
                    pass  # Use config branch

            repos.append({"path": repo_config.path, "branch": branch, "url": repo_config.url})
    except (PyProjectNotFoundError, Exception):
        pass  # No repos or can't load them

    # JSON output
    if json_output:
        output = {
            "current_project": project_name,
            "project": {
                "name": project_config["name"],
                "branch": project_config["branch"],
                "folder": project_config["folder"],
                "meta_path": str(per_project_meta),
                "created": project_config["created"],
                "repositories": repos,
            },
        }
        click.echo(json.dumps(output, indent=2))
        return

    # Show config file info if verbose
    if verbose:
        global_config_path = config.get_main_config_path()
        project_config_path = config.get_project_config_path(project_name)

        click.echo("Configuration Files:\n")
        click.echo(f"Global config: {global_config_path}")

        # Read and display global config
        try:
            with open(global_config_path, "rb") as f:
                global_config_content = tomllib.load(f)
            click.echo("\nGlobal config contents:")
            click.echo(json.dumps(global_config_content, indent=2))
        except Exception as e:
            click.echo(f"  (Could not read: {e})")

        click.echo(f"\nProject config: {project_config_path}")

        # Read and display project config
        try:
            with open(project_config_path, "rb") as f:
                project_config_content = tomllib.load(f)
            click.echo("\nProject config contents:")
            click.echo(json.dumps(project_config_content, indent=2))
        except Exception as e:
            click.echo(f"  (Could not read: {e})")

        click.echo("\n" + "=" * 60 + "\n")

    # Human-readable output
    click.echo(f"Current project: {project_name}\n")
    click.echo("Project Configuration:")
    click.echo(f"  Name:          {project_config['name']}")
    click.echo(f"  Branch:        {project_config['branch']}")
    click.echo(f"  Created:       {project_config['created']}")
    click.echo(f"  Meta path:     {per_project_meta}")
    click.echo(f"  Project path:  {project_dir}")

    if repos:
        click.echo(f"\nRepositories ({len(repos)}):")
        for repo in repos:
            click.echo(f"  📦 {repo['path']} ({repo['branch']})")

    click.echo("\nQuick Actions:")
    click.echo("  qen status              Show detailed status")
    click.echo("  qen config --list       List all projects")
    click.echo("  qen config <name>       Switch projects")


def display_project_list(
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
    compact: bool = False,
    json_output: bool = False,
) -> None:
    """Display list of all projects.

    Args:
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override
        compact: If True, use compact format
        json_output: If True, output in JSON format

    Raises:
        click.ClickException: If display fails
    """
    projects = list_all_projects(config, config_dir, meta_path, current_project)

    if not projects:
        if json_output:
            click.echo(json.dumps({"current_project": None, "projects": []}, indent=2))
            return

        click.echo("No projects found.")
        click.echo("\nCreate a project:")
        click.echo("  qen init <project-name>")
        return

    # JSON output
    if json_output:
        current_project_name = get_current_project_name(
            config, config_dir, meta_path, current_project
        )
        output = {
            "current_project": current_project_name,
            "projects": [
                {
                    "name": p.name,
                    "branch": p.branch,
                    "created": p.created,
                    "repository_count": p.repository_count,
                    "is_current": p.is_current,
                }
                for p in projects
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    # Human-readable output
    click.echo("Available projects:\n")

    for project in projects:
        marker = "* " if project.is_current else "  "

        if compact:
            # Extract date from ISO timestamp
            date = project.created.split("T")[0]
            repo_word = "repo" if project.repository_count == 1 else "repos"
            click.echo(
                f"{marker}{project.name:<20} {project.repository_count} {repo_word:<6} {date}"
            )
        else:
            current_marker = " (current)" if project.is_current else ""
            click.echo(f"{marker}{project.name}{current_marker}")
            click.echo(f"  Branch:        {project.branch}")
            click.echo(f"  Created:       {project.created}")
            click.echo(f"  Repositories:  {project.repository_count}")
            click.echo(f"  Path:          {project.path}")
            click.echo()

    if not compact:
        click.echo(f"{len(projects)} projects total")
        click.echo("* = current project\n")

        click.echo("Quick Actions:")
        click.echo("  qen config <name>       Switch to a project")
        click.echo("  qen init <name>         Create new project")
    else:
        click.echo("\n* = current project")


def switch_project(
    project_name: str,
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
) -> None:
    """Switch to a different project.

    This now includes switching the git branch in the meta repository.

    Args:
        project_name: Name of project to switch to
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override

    Raises:
        click.ClickException: If switch fails
    """
    # Use provided config or create one with overrides
    if config is None:
        config = QenConfig(
            config_dir=config_dir,
            meta_path_override=meta_path,
            current_project_override=current_project,
        )

    # Verify project exists
    if not config.project_config_exists(project_name):
        # List available projects
        projects = list_all_projects(config, config_dir, meta_path, current_project)
        click.echo(f'Error: Project "{project_name}" not found.\n', err=True)

        if projects:
            click.echo("Available projects:")
            for project in projects:
                click.echo(f"  - {project.name}")
        else:
            click.echo("No projects found.")

        click.echo("\nCreate a new project:")
        click.echo(f"  qen init {project_name}")
        raise click.Abort()

    # Load project config and get branch name
    try:
        project_config = config.read_project_config(project_name)
    except QenConfigError as e:
        raise click.ClickException(f"Error loading configuration: {e}") from e

    # Check for per-project meta (new format)
    if "repo" not in project_config:
        click.echo(
            f"Error: Project '{project_name}' uses old configuration format.\n"
            f"This version requires per-project meta clones.\n"
            f"To migrate: qen init --force {project_name}",
            err=True,
        )
        raise click.Abort()

    per_project_meta = Path(project_config["repo"])
    expected_branch = project_config["branch"]

    # Check current branch
    from ..git_utils import GitError, checkout_branch, get_current_branch, has_uncommitted_changes

    try:
        current_branch = get_current_branch(per_project_meta)
    except GitError as e:
        raise click.ClickException(f"Error getting current branch: {e}") from e

    # If not on correct branch, switch it
    if current_branch != expected_branch:
        # Check for uncommitted changes
        if has_uncommitted_changes(per_project_meta):
            click.echo(f"Error: Cannot switch to project '{project_name}'", err=True)
            click.echo(
                f"Currently on branch '{current_branch}', need '{expected_branch}'", err=True
            )
            click.echo("You have uncommitted changes in the meta repository.", err=True)
            click.echo("Please commit or stash them first.", err=True)
            raise click.Abort()

        # Switch branch
        try:
            click.echo(f"Switching from branch '{current_branch}' to '{expected_branch}'...")
            checkout_branch(per_project_meta, expected_branch)
        except GitError as e:
            raise click.ClickException(f"Error checking out branch: {e}") from e

    # Now update config (AFTER git checkout succeeds)
    try:
        config.update_current_project(project_name)
    except QenConfigError as e:
        raise click.ClickException(f"Error updating current project: {e}") from e

    # Success message
    click.echo(f"Switched to project: {project_name}\n")
    click.echo("Project Configuration:")
    click.echo(f"  Name:          {project_config['name']}")
    click.echo(f"  Branch:        {project_config['branch']}")

    # Count repositories
    try:
        repo_count = count_repositories(project_config)
        click.echo(f"  Repositories:  {repo_count}")
    except Exception:
        pass  # Skip repo count if we can't determine it

    click.echo("\nUse 'qen status' to see detailed status.")


def display_global_config(
    config: QenConfig | None = None,
    config_dir: Path | None = None,
    meta_path: Path | None = None,
    current_project: str | None = None,
    json_output: bool = False,
) -> None:
    """Display global QEN configuration.

    Args:
        config: Optional QenConfig instance (for backward compatibility)
        config_dir: Optional config directory override
        meta_path: Optional meta path override
        current_project: Optional current project override
        json_output: If True, output in JSON format

    Raises:
        click.ClickException: If display fails
    """
    # Use provided config or create one with overrides
    if config is None:
        config = QenConfig(
            config_dir=config_dir,
            meta_path_override=meta_path,
            current_project_override=current_project,
        )

    try:
        main_config = config.read_main_config()
    except QenConfigError as e:
        raise click.ClickException(f"Error reading configuration: {e}") from e

    meta_path = main_config.get("meta_path", "")
    org = main_config.get("org", "")
    current_project = main_config.get("current_project")

    # Check external tools
    gh_found = False
    gh_version = ""
    try:
        result = run_git_command(["--version"])
        git_version = result.strip()
    except GitError:
        git_version = "not found"

    try:
        import subprocess

        gh_result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        gh_found = True
        gh_version = gh_result.stdout.strip().split("\n")[0]
    except (subprocess.CalledProcessError, FileNotFoundError):
        gh_found = False
        gh_version = "not found"

    # Get current project details if set
    current_project_branch = None
    if current_project:
        try:
            project_config = config.read_project_config(str(current_project))
            current_project_branch = project_config.get("branch")
        except QenConfigError:
            pass

    # JSON output
    if json_output:
        output = {
            "meta_path": meta_path,
            "github_org": org,
            "current_project": current_project,
            "current_project_branch": current_project_branch,
            "tools": {
                "git": git_version,
                "gh": {"installed": gh_found, "version": gh_version if gh_found else None},
            },
            "config_files": {
                "global": str(config.get_main_config_path()),
                "projects_dir": str(config.get_config_dir()),
            },
        }
        click.echo(json.dumps(output, indent=2))
        return

    # Human-readable output
    click.echo("Global QEN Configuration:\n")
    click.echo("Meta Repository:")
    click.echo(f"  Path:         {meta_path}")
    click.echo(f"  GitHub org:   {org}")

    if current_project:
        click.echo("\nCurrent Project:")
        click.echo(f"  Name:         {current_project}")
        if current_project_branch:
            click.echo(f"  Branch:       {current_project_branch}")

    click.echo("\nSettings:")
    gh_status = "gh (found)" if gh_found else "gh (not found)"
    click.echo(f"  GitHub CLI:   {gh_status}")
    click.echo(f"  Git:          {git_version}")

    click.echo("\nConfiguration files:")
    click.echo(f"  Global:       {config.get_main_config_path()}")
    click.echo(f"  Projects:     {config.get_config_dir()}/")

    click.echo("\nQuick Actions:")
    click.echo("  qen config              Show current project")
    click.echo("  qen config --list       List all projects")


@click.command("config")
@click.argument("project_name", required=False)
@click.option("--list", "list_projects", is_flag=True, help="List all available projects")
@click.option("--compact", is_flag=True, help="Compact list format (with --list)")
@click.option("--global", "show_global", is_flag=True, help="Show global configuration")
@click.option("--json", "json_output", is_flag=True, help="Output in JSON format")
@click.option("--verbose", is_flag=True, help="Show config file paths and contents")
@click.pass_context
def config_command(
    ctx: click.Context,
    project_name: str | None,
    list_projects: bool,
    compact: bool,
    show_global: bool,
    json_output: bool,
    verbose: bool,
) -> None:
    """Manage QEN configuration and projects.

    Without arguments, shows current project configuration.
    With a project name, switches to that project.

    Examples:

    \b
        # Show current project
        $ qen config

    \b
        # Show current project with config file paths and contents
        $ qen config --verbose

    \b
        # List all projects
        $ qen config --list

    \b
        # Switch to a project
        $ qen config my-project

    \b
        # Show global configuration
        $ qen config --global

    \b
        # JSON output
        $ qen config --json
    """
    # Extract injected config (for testing)
    config = ctx.obj.get("config") if ctx.obj else None

    # If no injected config, create with overrides
    if config is None:
        overrides = ctx.obj.get("config_overrides", {}) if ctx.obj else {}
        config = QenConfig(
            config_dir=overrides.get("config_dir"),
            meta_path_override=overrides.get("meta_path"),
            current_project_override=overrides.get("current_project"),
        )

    # Extract overrides for passing to helper functions
    config_dir = None
    meta_path = None
    current_project_override = None

    if ctx.obj and "config_overrides" in ctx.obj:
        overrides = ctx.obj["config_overrides"]
        config_dir = overrides.get("config_dir")
        meta_path = overrides.get("meta_path")
        current_project_override = overrides.get("current_project")

    if not config.main_config_exists():
        click.echo("Error: qen is not initialized. Run 'qen init' first.", err=True)
        raise click.Abort()

    try:
        # Global config view
        if show_global:
            display_global_config(
                config=config,
                config_dir=config_dir,
                meta_path=meta_path,
                current_project=current_project_override,
                json_output=json_output,
            )
            return

        # List all projects
        if list_projects:
            display_project_list(
                config=config,
                config_dir=config_dir,
                meta_path=meta_path,
                current_project=current_project_override,
                compact=compact,
                json_output=json_output,
            )
            return

        # Switch to project
        if project_name:
            if json_output:
                click.echo("Error: Cannot combine project switch with --json", err=True)
                raise click.Abort()
            switch_project(
                project_name,
                config=config,
                config_dir=config_dir,
                meta_path=meta_path,
                current_project=current_project_override,
            )
            # If verbose, show detailed config after switching
            if verbose:
                click.echo("\n" + "=" * 60 + "\n")
                display_current_project(
                    config=config,
                    config_dir=config_dir,
                    meta_path=meta_path,
                    current_project=project_name,  # Use the just-switched project
                    json_output=False,
                    verbose=True,
                )
            return

        # Show current project (default)
        display_current_project(
            config=config,
            config_dir=config_dir,
            meta_path=meta_path,
            current_project=current_project_override,
            json_output=json_output,
            verbose=verbose,
        )

    except (click.ClickException, click.Abort):
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
