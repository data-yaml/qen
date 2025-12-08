# qen sh - Run Shell Commands in Project Context

## Overview

`qen sh` executes shell commands in the PROJECT FOLDER as defined in the stored QEN configuration. This command changes to the project directory (not your current directory) and runs commands there.

**Key Point:** This command operates on the stored config state, NOT your current working directory. It will cd to the project folder defined in `$XDG_CONFIG_HOME/qen/projects/<project>.toml` before executing the command.

## Command Behavior

### Basic Usage

```bash
qen sh "ls -la"                    # cd to project folder, run command there
qen sh -c repos/api "npm install"  # cd to project/repos/api, run command there
qen sh -y "mkdir build"             # Skip confirmation, cd and run immediately
```

### What It Does

1. **Load Project Config** - Reads project configuration from XDG config directory
2. **Identify Project Folder** - Gets project path from stored config (NOT current directory)
3. **Validate Subdirectory** - Checks specified subdirectory exists (if -c provided)
4. **Show Confirmation** - Displays target directory and command (unless `--yes`)
5. **Change Directory** - cd to the project folder (or subdirectory)
6. **Execute Command** - Run the shell command in that location
7. **Return Output** - Display command output or error information

## Repository State Requirements

### Project Structure

- Requires an active QEN project configuration (stored in XDG config)
- Operates on the project folder defined in config, regardless of current directory
- Optional specification of subdirectories within the project
- Respects project-level configuration and repository structure

## Flags and Options

| Flag | Description | Default |
|------|-------------|---------|
| `-c, --chdir <subdir>` | Change to specified subdirectory before running command | Project root |
| `-y, --yes` | Skip confirmation and working directory display | false |
| `--verbose` | Show additional context information | false |

### Flag Usage Notes

**`-c, --chdir`**: Change to Subdirectory

- Relative to project root
- Must be a valid subdirectory
- Useful for running commands in specific repositories or project areas

**`-y, --yes`**: Skip Confirmation

- Bypasses working directory confirmation
- Useful in scripts or when you're certain about the context
- Reduces interactive overhead

**`--verbose`**: Detailed Context

- Shows additional information about project and execution context
- Helpful for debugging or understanding command execution environment

## Error Conditions

- **No active project**: "No active QEN project. Run 'qen init PROJECT_NAME' first."
- **Project folder not found**: "Project folder does not exist: {path}"
- **Invalid subdirectory**: "Specified subdirectory does not exist: {subdir}"
- **Command execution failure**: Passes through shell command error
- **Permission issues**: Inherits shell command permission errors

## Examples

### Example 1: Run Command in Project Root

```bash
$ pwd
/Users/you/some/other/directory

$ qen sh "git status"
Project: my-project
Target directory: /path/to/meta/proj/2025-12-06-my-project
Run command in this directory? [Y/n] y

# Changes to project folder and runs git status there
# (output from /path/to/meta/proj/2025-12-06-my-project)
```

### Example 2: Run Command in Specific Subdirectory

```bash
$ qen sh -c repos/api "npm install"
Project: my-project
Target directory: /path/to/meta/proj/2025-12-06-my-project/repos/api
Run command in this directory? [Y/n] y

# Changes to repos/api and runs npm install
```

### Example 3: Skip Confirmation

```bash
$ qen sh -y "mkdir build"
# Immediately changes to project folder and runs mkdir build there
```

### Example 4: Verbose Output

```bash
$ qen sh --verbose "echo $PWD"
Project: my-project
Project path (from config): /path/to/meta/proj/2025-12-06-my-project
Target directory: /path/to/meta/proj/2025-12-06-my-project
Command: echo $PWD

/path/to/meta/proj/2025-12-06-my-project
```

## Configuration

### Project-Level Settings (Optional)

```toml
[tool.qen.shell]
default_subdirectory = "repos/main"  # Default subdirectory for sh command
require_confirmation = true          # Always show confirmation prompt
```

## Success Criteria

### Must Accomplish

1. **Config-Based Execution** - Load project path from stored config, NOT current directory
2. **Directory Change** - Actually cd to project folder before running command
3. **Subdirectory Support** - Allow running commands in project subdirectories
4. **Safe Execution** - Provide confirmation showing target directory
5. **Error Handling** - Clear error messages when project config or folder not found

### Should Accomplish

1. **Flexible Subdirectory Selection**
2. **Confirmation Bypass**
3. **Verbose Mode for Debugging**

### Nice to Have

1. **Shell Expansion Support** - Handle environment variables and shell globbing
2. **Multi-Repository Context** - Potential future support for cross-repo commands

## Non-Goals

- **Full Shell Replacement** - Not a comprehensive shell environment
- **Complex Project Routing** - Focus on simple, predictable command execution
- **Persistent Shell Sessions** - Each invocation is a new shell context

## Design Decisions

1. **Config-Driven, Not CWD-Driven** - Always use stored config state, never infer from current directory
2. **Explicit Directory Change** - cd to project folder before execution (not context-aware from CWD)
3. **Safety First** - Confirmation by default showing target directory
4. **Minimal Overhead** - Keep command execution lightweight
5. **Flexible Subdirectory Handling** - Easy navigation within project

## Integration Points

### With Other Commands

- `qen init` - Sets up project context for shell commands
- `qen status` - Helps understand project and repository state
- `qen pull` - Ensures up-to-date state before running commands

### External Tools

- **bash/shell** - Uses system shell for command execution
- **git** - Inherits project git context
