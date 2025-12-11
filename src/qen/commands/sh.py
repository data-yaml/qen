"""Shell command execution in project context.

Executes shell commands in the project directory as defined in stored QEN configuration.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

from ..config import QenConfig, QenConfigError
from ..init_utils import ensure_correct_branch, ensure_initialized


class ShellError(Exception):
    """Base exception for shell command errors."""

    pass


@dataclass
class ShellContext:
    """Shell execution context."""

    project_name: str
    project_dir: Path
    target_dir: Path
    config: QenConfig


def prepare_shell_context(
    project_name: str | None,
    chdir: str | None,
    yes: bool,
    verbose: bool,
    config_overrides: dict[str, Any] | None,
) -> ShellContext:
    """Prepare context for shell execution.

    Validates configuration, resolves project directory, shows confirmation.
    Reused by both execute_shell_command() and open_interactive_shell().

    Args:
        project_name: Project name (None = use current project)
        chdir: Subdirectory to change to (relative to project root)
        yes: Skip confirmation prompt
        verbose: Show additional context information
        config_overrides: Configuration overrides from CLI

    Returns:
        ShellContext with validated paths and config

    Raises:
        click.ClickException: For validation errors or user abort
    """
    # Load configuration with overrides
    overrides = config_overrides or {}
    config = ensure_initialized(
        config_dir=overrides.get("config_dir"),
        meta_path_override=overrides.get("meta_path"),
        current_project_override=overrides.get("current_project"),
        verbose=verbose,
    )

    # Config is now guaranteed to exist
    ensure_correct_branch(config, verbose=verbose)
    main_config = config.read_main_config()

    # Determine which project to use
    if project_name:
        target_project = project_name
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
    except QenConfigError as e:
        raise click.ClickException(
            f"Project '{target_project}' not found in qen configuration: {e}"
        ) from e

    # Check for per-project meta (new format)
    if "repo" not in project_config:
        click.echo(
            f"Error: Project '{target_project}' uses old configuration format.\n"
            f"This version requires per-project meta clones.\n"
            f"To migrate: qen init --force {target_project}",
            err=True,
        )
        raise click.Abort()

    per_project_meta = Path(project_config["repo"])
    project_dir = per_project_meta / project_config["folder"]

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
        click.echo("")

    # Confirmation prompt (unless --yes)
    if not yes:
        click.echo(f"Project: {target_project}")
        click.echo(f"Target directory: {target_dir}")
        if not click.confirm("Run command in this directory?", default=True):
            raise click.Abort()
        click.echo("")

    return ShellContext(
        project_name=target_project,
        project_dir=project_dir,
        target_dir=target_dir,
        config=config,
    )


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
    # Prepare context (validation, config, confirmation)
    context = prepare_shell_context(
        project_name=project_name,
        chdir=chdir,
        yes=yes,
        verbose=verbose,
        config_overrides=config_overrides,
    )

    # Show command if verbose
    if verbose:
        click.echo(f"Command: {command}")
        click.echo("")

    # Execute the command
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=context.target_dir,
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


def detect_shell() -> str:
    """Detect user's preferred shell.

    Detection order:
    1. $SHELL environment variable
    2. /bin/bash (fallback)

    Returns:
        Absolute path to shell executable

    Raises:
        click.ClickException: If shell not found
    """
    shell_path = os.environ.get("SHELL")
    if shell_path and Path(shell_path).is_file():
        return shell_path

    bash_path = "/bin/bash"
    if Path(bash_path).is_file():
        return bash_path

    raise click.ClickException("Could not detect shell. Set $SHELL environment variable.")


def create_shell_env(context: ShellContext, chdir: str | None) -> dict[str, str]:
    """Create environment variables for subshell.

    Sets PS1 to show project context in prompt.

    Args:
        context: Shell context with project info
        chdir: Subdirectory path (for prompt display)

    Returns:
        Environment dict with custom prompt
    """
    env = os.environ.copy()

    # Build prompt prefix
    if chdir:
        prompt_prefix = f"({context.project_name}:{chdir})"
    else:
        prompt_prefix = f"({context.project_name})"

    # Customize PS1 (bash/sh-compatible)
    original_ps1 = env.get("PS1", "\\$ ")
    env["PS1"] = f"{prompt_prefix} {original_ps1}"

    # Store project context for scripts
    env["QEN_PROJECT"] = context.project_name
    env["QEN_PROJECT_DIR"] = str(context.project_dir)
    env["QEN_TARGET_DIR"] = str(context.target_dir)

    return env


def open_interactive_shell(
    project_name: str | None = None,
    chdir: str | None = None,
    yes: bool = False,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> None:
    """Open an interactive shell in the project directory.

    Uses os.execve() to replace the Python process with a shell.
    This function NEVER RETURNS - the process is replaced.

    Args:
        project_name: Project name (None = use current project)
        chdir: Subdirectory to open shell in
        yes: Skip confirmation prompt
        verbose: Show additional context
        config_overrides: Config overrides from CLI

    Raises:
        click.ClickException: For validation errors or shell spawn failure
    """
    # Prepare context (validation, config, confirmation)
    context = prepare_shell_context(
        project_name=project_name,
        chdir=chdir,
        yes=yes,
        verbose=verbose,
        config_overrides=config_overrides,
    )

    # Detect shell
    shell_path = detect_shell()

    if verbose:
        click.echo(f"Shell: {shell_path}")
        click.echo("")

    # Create environment with custom prompt
    env = create_shell_env(context, chdir=chdir)

    # Show entry message
    click.echo(f"Opening shell in: {context.target_dir}")
    click.echo(f"Type 'exit' to return to {Path.cwd()}")
    click.echo("")

    # Change to target directory
    os.chdir(context.target_dir)

    # Replace current process with shell (NEVER RETURNS)
    try:
        os.execve(shell_path, [shell_path], env)
    except OSError as e:
        raise click.ClickException(f"Failed to spawn shell: {e}") from e


@click.command("sh")
@click.argument("command", required=False)
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
    command: str | None,
    chdir: str | None,
    yes: bool,
    verbose: bool,
    project: str | None,
) -> None:
    """Run shell commands or open interactive shell in project context.

    If COMMAND is provided, executes it in the project directory and exits.
    If COMMAND is omitted, opens an interactive shell in the project directory.

    The command/shell runs in the project folder as defined in QEN configuration,
    NOT your current working directory.

    Examples:

    \b
        # Open interactive shell in project root
        $ qen sh

    \b
        # Open interactive shell in subdirectory
        $ qen sh -c repos/api

    \b
        # Run single command in project root
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
        if command:
            # Execute single command (existing behavior)
            execute_shell_command(
                command=command,
                project_name=project,
                chdir=chdir,
                yes=yes,
                verbose=verbose,
                config_overrides=overrides,
            )
        else:
            # Open interactive shell (NEW behavior)
            open_interactive_shell(
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
