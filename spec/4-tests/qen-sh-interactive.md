# qen sh - Add Interactive Shell Mode

## Overview

Enhance `qen sh` to support **interactive shell mode** when no command argument is provided. This maintains minimalism by reusing the existing command.

**Current behavior:**

- `qen sh "command"` - Runs one command in project dir, then exits

**New behavior:**

- `qen sh` - Opens an **interactive subshell** in project dir

## Why Scripts Cannot `cd` Their Parent Shell

Scripts run in a subprocess (child process) and cannot modify parent process state. When the subprocess exits, the parent shell remains in its original directory.

**Solutions:**

1. ❌ Source the script (`. script.sh`) - risky, executes in parent shell
2. ✅ **Open a new subshell** - safe, predictable, isolates state
3. Shell function in `~/.bashrc` - requires user setup
4. `eval $(command)` - dangerous, requires careful quoting

**This spec implements option 2**: Open a new subshell in the target directory using `os.execve()`.

## Command Design

### Make Command Argument Optional

**Current signature:**

```python
@click.command("sh")
@click.argument("command")  # REQUIRED
def sh_command(ctx, command: str, ...):
```

**New signature:**

```python
@click.command("sh")
@click.argument("command", required=False)  # OPTIONAL
def sh_command(ctx, command: str | None, ...):
    if command:
        # Execute single command (current behavior)
        execute_shell_command(command, ...)
    else:
        # Open interactive shell (NEW behavior)
        open_interactive_shell(...)
```

### Usage Examples

```bash
# Interactive mode (NEW)
qen sh
qen sh -c repos/api
qen sh --yes

# Single command mode (existing)
qen sh "git status"
qen sh -c repos/api "npm test"
qen sh --yes "mkdir build"
```

## Implementation Tasks

### Task 1: Make Command Argument Optional

**File:** [src/qen/commands/sh.py](../../src/qen/commands/sh.py:136-208)

**Changes:**

```python
@click.command("sh")
@click.argument("command", required=False)  # Add required=False
@click.option("-c", "--chdir", ...)
@click.option("-y", "--yes", ...)
@click.option("--verbose", ...)
@click.option("--project", ...)
@click.pass_context
def sh_command(
    ctx: click.Context,
    command: str | None,  # Change to optional
    chdir: str | None,
    yes: bool,
    verbose: bool,
    project: str | None,
) -> None:
    """Run shell commands or open interactive shell in project context.

    If COMMAND is provided, executes it in the project directory and exits.
    If COMMAND is omitted, opens an interactive shell in the project directory.

    Examples:

    \b
        # Open interactive shell in project root
        $ qen sh

    \b
        # Open interactive shell in subdirectory
        $ qen sh -c repos/api

    \b
        # Run single command (existing behavior)
        $ qen sh "ls -la"

    \b
        # Run command in subdirectory
        $ qen sh -c repos/api "npm install"
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
```

### Task 2: Extract Shared Validation Logic

**File:** [src/qen/commands/sh.py](../../src/qen/commands/sh.py)

**Create shared context preparation function:**

```python
@dataclass
class ShellContext:
    """Shell execution context."""

    project_name: str
    project_dir: Path
    target_dir: Path
    config: QenConfigManager


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

    Steps:
    1. Load configuration with overrides
    2. Determine target project
    3. Get project directory from config
    4. Verify directory exists
    5. Resolve target directory (with optional chdir)
    6. Show confirmation prompt (unless --yes)

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
```

### Task 3: Refactor execute_shell_command

**File:** [src/qen/commands/sh.py](../../src/qen/commands/sh.py:22-134)

**Simplify to use prepare_shell_context():**

```python
def execute_shell_command(
    command: str,
    project_name: str | None = None,
    chdir: str | None = None,
    yes: bool = False,
    verbose: bool = False,
    config_overrides: dict[str, Any] | None = None,
) -> None:
    """Execute a shell command in the project directory."""

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
            check=False,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            click.echo(result.stdout, nl=False)
        if result.stderr:
            click.echo(result.stderr, nl=False, err=True)

        if result.returncode != 0:
            raise click.ClickException(f"Command failed with exit code {result.returncode}")

    except subprocess.SubprocessError as e:
        raise ShellError(f"Failed to execute command: {e}") from e
```

### Task 4: Implement open_interactive_shell

**File:** [src/qen/commands/sh.py](../../src/qen/commands/sh.py)

**Add new function for interactive shell:**

```python
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
    import os

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
    import os

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
    import os

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
```

### Task 5: Update Tests

**File:** [tests/unit/qen/commands/test_sh.py](../../tests/unit/qen/commands/test_sh.py)

**Add tests for new functionality:**

```python
def test_sh_no_command_opens_interactive_shell(mocker):
    """qen sh with no command opens interactive shell."""
    mock_open_interactive = mocker.patch(
        "qen.commands.sh.open_interactive_shell"
    )

    result = runner.invoke(cli, ["sh"])

    assert result.exit_code == 0
    mock_open_interactive.assert_called_once()


def test_sh_with_command_executes_command(mocker):
    """qen sh with command executes single command."""
    mock_execute = mocker.patch("qen.commands.sh.execute_shell_command")

    result = runner.invoke(cli, ["sh", "ls"])

    assert result.exit_code == 0
    mock_execute.assert_called_once()
    # Verify command argument was passed
    assert mock_execute.call_args[1]["command"] == "ls"


def test_detect_shell_from_env(monkeypatch):
    """Detect shell from $SHELL environment variable."""
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert detect_shell() == "/bin/zsh"


def test_detect_shell_fallback_bash(monkeypatch, mocker):
    """Fall back to /bin/bash if $SHELL not set."""
    monkeypatch.delenv("SHELL", raising=False)
    mocker.patch("pathlib.Path.is_file", return_value=True)
    assert detect_shell() == "/bin/bash"


def test_create_shell_env_basic(shell_context):
    """Create environment with project prompt."""
    env = create_shell_env(shell_context, chdir=None)
    assert "QEN_PROJECT" in env
    assert "(my-project)" in env["PS1"]


def test_create_shell_env_with_subdir(shell_context):
    """Include subdirectory in prompt."""
    env = create_shell_env(shell_context, chdir="repos/api")
    assert "(my-project:repos/api)" in env["PS1"]


def test_prepare_shell_context_no_project(mocker):
    """Error if no active project."""
    mocker.patch(
        "qen.commands.sh.ensure_initialized",
        return_value=MockConfig(current_project=None),
    )

    with pytest.raises(click.ClickException, match="No active project"):
        prepare_shell_context(
            project_name=None,
            chdir=None,
            yes=True,
            verbose=False,
            config_overrides=None,
        )


def test_open_interactive_shell_calls_execve(mocker, shell_context):
    """Spawn shell using os.execve."""
    mock_prepare = mocker.patch(
        "qen.commands.sh.prepare_shell_context",
        return_value=shell_context,
    )
    mock_detect = mocker.patch(
        "qen.commands.sh.detect_shell",
        return_value="/bin/bash",
    )
    mock_chdir = mocker.patch("os.chdir")
    mock_execve = mocker.patch("os.execve")

    open_interactive_shell(yes=True)

    mock_chdir.assert_called_once()
    mock_execve.assert_called_once()
```

## User Experience Examples

### Example 1: Basic Interactive Shell

```bash
$ pwd
/Users/you/some/directory

$ qen sh
Project: my-project
Target directory: /path/to/proj/251208-my-project
Run command in this directory? [Y/n] y

Opening shell in: /path/to/proj/251208-my-project
Type 'exit' to return to /Users/you/some/directory

(my-project) $ pwd
/path/to/proj/251208-my-project

(my-project) $ git status
On branch 251208-my-project
nothing to commit, working tree clean

(my-project) $ exit

$ pwd
/Users/you/some/directory
```

### Example 2: Interactive Shell in Subdirectory

```bash
$ qen sh -c repos/api
Project: my-project
Target directory: /path/to/proj/251208-my-project/repos/api
Run command in this directory? [Y/n] y

Opening shell in: /path/to/proj/251208-my-project/repos/api
Type 'exit' to return to /Users/you/current/dir

(my-project:repos/api) $ npm test
... test output ...

(my-project:repos/api) $ exit
```

### Example 3: Skip Confirmation

```bash
$ qen sh --yes
Opening shell in: /path/to/proj/251208-my-project
Type 'exit' to return to /Users/you/current/dir

(my-project) $ # Immediately in shell
```

### Example 4: Single Command Still Works

```bash
$ qen sh "git status"
Project: my-project
Target directory: /path/to/proj/251208-my-project
Run command in this directory? [Y/n] y

On branch 251208-my-project
nothing to commit, working tree clean
```

## Design Decisions

### Decision 1: Reuse `qen sh` Instead of New Command

**Rationale:** Minimalism. One command, two modes.

**Alternative rejected:** Create separate `qen shell` command (bloat).

### Decision 2: Use `os.execve()` for Process Replacement

**Rationale:**

- Native shell behavior (no nested process)
- Clean exit handling (Ctrl+C, Ctrl+D work naturally)
- No cleanup needed (shell replaces Python entirely)

**Tradeoff:** Python process never returns (function never returns).

### Decision 3: Customize Prompt with PS1

**Rationale:**

- Visual feedback (user knows they're in qen shell)
- Simple (one environment variable)
- Preserves user config (appends to existing prompt)

**Limitation:** PS1 is bash/sh-specific (zsh/fish may differ).

### Decision 4: Export QEN_* Environment Variables

**Rationale:**

- Scripts can detect qen environment
- Useful for automation
- Follows convention (like `GIT_DIR`, `VIRTUAL_ENV`)

### Decision 5: Extract Shared Logic into prepare_shell_context

**Rationale:**

- DRY principle
- Consistent validation and error messages
- Easier to maintain and test

## Success Criteria

### Must Accomplish

- [ ] Make `command` argument optional in `sh_command()`
- [ ] Extract shared validation into `prepare_shell_context()`
- [ ] Refactor `execute_shell_command()` to use `prepare_shell_context()`
- [ ] Implement `detect_shell()` to find user's shell
- [ ] Implement `create_shell_env()` to customize prompt
- [ ] Implement `open_interactive_shell()` using `os.execve()`
- [ ] Add unit tests for new functions
- [ ] Update existing tests to handle optional command
- [ ] All tests pass: `./poe test`

### Should Accomplish

- [ ] Support `--verbose` mode for interactive shell
- [ ] Show clear entry/exit messages
- [ ] Handle shell detection failure gracefully
- [ ] Export `QEN_PROJECT`, `QEN_PROJECT_DIR`, `QEN_TARGET_DIR`
- [ ] Work with bash, zsh, and other shells

### Nice to Have

- [ ] Shell-specific prompt customization (zsh PROMPT)
- [ ] Integration tests with subprocess validation
- [ ] Document manual testing procedure

## Non-Goals

- Cross-platform Windows support (Unix-only)
- Shell-specific features (keep it generic)
- Persistent shell sessions (each invocation is fresh)
- Shell wrapper behavior (don't intercept commands)

## References

### Related Code

- [src/qen/commands/sh.py](../../src/qen/commands/sh.py) - Current implementation
- [spec/2-status/05-qen-sh.md](../2-status/05-qen-sh.md) - Original spec

### External References

- `os.execve()`: <https://docs.python.org/3/library/os.html#os.execve>
- Bash prompts: <https://www.gnu.org/software/bash/manual/html_node/Controlling-the-Prompt.html>

---

*Minimalist philosophy: Enhance existing commands rather than adding new ones.*
