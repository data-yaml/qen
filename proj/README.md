# ${project_name}

## Project Metadata

- **Created:** ${date}
- **Branch:** ${branch_name}

## Context

*One-line description.*

### Job Story

- When...
- I want...
- So that...

### TestCase(s)

TBD

### Hypotheses

1. TBD

## Repositories

This project includes repositories defined in the `pyproject.toml` file. Current repositories:

- See `pyproject.toml` for the most up-to-date list

## Getting Started

### Using the Project Wrapper

This project includes a `./qen` executable that automatically runs qen commands in this project's context:

```bash
# From within the project directory, use the wrapper:
./qen status      # Check project status
./qen add <repo>  # Add a repository
./qen pull        # Update repos
./qen pr status   # Check PR status
./qen --help      # More commands

# The wrapper ensures you're always working with this project,
# even if you have multiple qen projects configured.
```

### Using Global qen

Alternatively, you can use the global `qen` command with the `--proj` flag:

```bash
uvx qen --proj ${project_name} status
uvx qen --proj ${project_name} add <repo>
```

## Next Steps

- [ ] Update project overview
- [ ] Add more detailed documentation
- [ ] Configure repositories in `pyproject.toml`
