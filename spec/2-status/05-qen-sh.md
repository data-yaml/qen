# qen sh - Run Shell Commands in Project Context

## Overview

`qen sh` provides a convenient way to execute shell commands within the context of a QEN project, specifically in the project or a specified project subdirectory. It ensures commands are run in the correct project environment and helps manage multi-repository projects.

## Command Behavior

### Basic Usage

```bash
qen sh "ls -la"                    # Run command in project root
qen sh -c repos/api "npm install"  # Run command in specific project subdirectory
qen sh -y "mkdir build"             # Skip confirmation, run immediately
```

**Note:** Command runs only within an initialized QEN project directory.

### What It Does

1. **Verify Project Context** - Confirms current directory is part of a QEN project
2. **Validate Subdirectory** - Checks specified subdirectory exists (if provided)
3. **Show Confirmation** - Displays current working directory and command (unless `--yes`)
4. **Execute Command** - Run the shell command in the specified context
5. **Capture Output** - Returns command output or error information

## Repository State Requirements

### Project Structure

- Must be run within a QEN project directory
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

- **Not in QEN project**: "Not in a QEN project directory. Run 'qen init' first."
- **Invalid subdirectory**: "Specified subdirectory does not exist: <subdir>"
- **Command execution failure**: Passes through shell command error
- **Permission issues**: Inherits shell command permission errors

## Examples

### Example 1: Run Command in Project Root

```bash
$ qen sh "git status"
Current working directory: /path/to/qen/project
Run command in this directory? [Y/n] y

# git status output here
```

### Example 2: Run Command in Specific Subdirectory

```bash
$ qen sh -c repos/api "npm install"
Current working directory: /path/to/qen/project/repos/api
Run command in this directory? [Y/n] y

# npm install output for API repo
```

### Example 3: Skip Confirmation

```bash
$ qen sh -y "mkdir build"
# Immediately runs mkdir build in project root
```

### Example 4: Verbose Output

```bash
$ qen sh --verbose "echo $PWD"
Project: my-project
Root Directory: /path/to/projects/my-project
Current Working Directory: /path/to/projects/my-project
Command: echo $PWD

# Command output
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

1. **Context Verification** - Ensure command runs within a QEN project
2. **Subdirectory Support** - Allow running commands in project subdirectories
3. **Safe Execution** - Provide confirmation mechanism
4. **Error Handling** - Clear error messages for project context issues

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

1. **Project-Centric** - Always tie command to project context
2. **Safety First** - Confirmation by default
3. **Minimal Overhead** - Keep command execution lightweight
4. **Flexible Subdirectory Handling** - Easy navigation within project

## Integration Points

### With Other Commands

- `qen init` - Sets up project context for shell commands
- `qen status` - Helps understand project and repository state
- `qen pull` - Ensures up-to-date state before running commands

### External Tools

- **bash/shell** - Uses system shell for command execution
- **git** - Inherits project git context
