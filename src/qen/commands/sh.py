"""Shell command execution in project context.

Executes shell commands in the project directory as defined in stored QEN configuration.
"""

import subprocess
from pathlib import Path
from typing import Any

import click

from ..config import QenConfig, QenConfigError


class ShellError(Exception):
    """Base exception for shell command errors."""

    pass


def execute_shell_command(
    command: str,
    project_name: str | None = None,
    chdir: str | None = None,
    yes: bool = False,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> None:
    """Execute a shell command in the project directory.

    Args:
        command: Shell command to execute
        project_name: Project name (None = use current project from config)
        chdir: Subdirectory to change to (relative to project root)
        yes: Skip confirmation prompt
        verbose: Show additional context information
        config_overrides: Configuration overrides from CLI

    Raises:
        click.ClickException: For user-facing errors
        ShellError: For shell execution errors
    """
    # Load configuration with overrides
    overrides = config_overrides or {}
    config = QenConfig(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
    )

    if not config.main_config_exists():
        raise click.ClickException("qen is not initialized. Run 'qen init' first to configure qen.")

    try:
        main_config = config.read_main_config()
    except QenConfigError as e:
        raise click.ClickException(f"Error reading configuration: {e}") from e

    # Determine which project to use
    if project_name:
        target_project: str = project_name
    else:
        target_project_raw = main_config.get("current_project")
        if not target_project_raw:
            raise click.ClickException(
                "No active project. Create a project with 'qen init <project-name>' first."
            )
        target_project = str(target_project_raw)

    # Get project directory from config
    try:
        project_config = config.read_project_config(target_project)
        meta_path = Path(main_config["meta_path"])
        project_dir = meta_path / project_config["folder"]
    except QenConfigError as e:
        raise click.ClickException(
            f"Project '{target_project}' not found in qen configuration: {e}"
        ) from e

    # Verify project directory exists
    if not project_dir.exists():
        raise click.ClickException(f"Project folder does not exist: {project_dir}")

    # Determine target directory
    if chdir:
        target_dir = project_dir / chdir
        if not target_dir.exists():
            raise click.ClickException(
                f"Specified subdirectory does not exist: {chdir}\nFull path: {target_dir}"
            )
        if not target_dir.is_dir():
            raise click.ClickException(
                f"Specified path is not a directory: {chdir}\nFull path: {target_dir}"
            )
    else:
        target_dir = project_dir

    # Show context information
    if verbose:
        click.echo(f"Project: {target_project}")
        click.echo(f"Project path (from config): {project_dir}")
        click.echo(f"Target directory: {target_dir}")
        click.echo(f"Command: {command}")
        click.echo("")

    # Confirmation prompt (unless --yes)
    if not yes:
        click.echo(f"Project: {target_project}")
        click.echo(f"Target directory: {target_dir}")
        if not click.confirm("Run command in this directory?", default=True):
            raise click.Abort()
        click.echo("")

    # Execute the command
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=target_dir,
            check=False,  # Don't raise on non-zero exit
            capture_output=True,  # Capture output for proper display
            text=True,
        )

        # Display output through Click for proper capture in tests
        if result.stdout:
            click.echo(result.stdout, nl=False)
        if result.stderr:
            click.echo(result.stderr, nl=False, err=True)

        # Exit with the same code as the command
        if result.returncode != 0:
            raise click.ClickException(f"Command failed with exit code {result.returncode}")

    except subprocess.SubprocessError as e:
        raise ShellError(f"Failed to execute command: {e}") from e


@click.command("sh")
@click.argument("command")
@click.option(
    "-c",
    "--chdir",
    help="Change to subdirectory before running command (relative to project root)",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation and working directory display",
)
@click.option(
    "--verbose",
    is_flag=True,
    help="Show additional context information",
)
@click.option(
    "--project",
    help="Project name (default: current project)",
)
@click.pass_context
def sh_command(
    ctx: click.Context,
    command: str,
    chdir: str | None,
    yes: bool,
    verbose: bool,
    project: str | None,
) -> None:
    """Run shell commands in project context.

    Executes COMMAND in the project directory as defined in stored QEN configuration.
    The command is executed in the project folder, NOT your current working directory.

    Examples:

    \b
        # Run command in project root
        $ qen sh "ls -la"

    \b
        # Run command in specific subdirectory
        $ qen sh -c repos/api "npm install"

    \b
        # Skip confirmation prompt
        $ qen sh -y "mkdir build"

    \b
        # Show verbose output
        $ qen sh --verbose "echo $PWD"

    \b
        # Run in specific project
        $ qen sh --project my-project "git status"
    """
    overrides = ctx.obj.get("config_overrides", {})
    try:
        execute_shell_command(
            command=command,
            project_name=project,
            chdir=chdir,
            yes=yes,
            verbose=verbose,
            config_overrides=overrides,
        )
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Unexpected error: {e}") from e
