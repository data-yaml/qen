# Spec: pyproject.toml for Proj Configuration

## Overview

Replace `meta.toml` with `pyproject.toml` using the `[tool.qen]` namespace for proj repository configuration.

## Rationale

### Why pyproject.toml?

**Benefits:**

1. **Standard Python format** - Every Python developer knows pyproject.toml
2. **IDE support** - Automatic syntax highlighting, validation, schema support
3. **Single source of truth** - One config file per proj instead of two
4. **Ecosystem integration** - Works with existing Python tooling
5. **Extensibility** - Natural place to add more qen-specific config

**Trade-offs:**

- Slightly more verbose than minimal meta.toml
- Could be confusing if proj isn't a Python project (but most will be)

### Addressing the Four Questions

**1. Terminology:** Using "proj" for things managed by qen (in `proj/YYMMDD-<name>/`)

**2. How meta.toml imagined repo tracking:**

```toml
[[repos]]
url = "https://github.com/org/repo"
branch = "main"
path = "repos/repo"
```

Simple array of tables with url, branch, and local path.

**3. Minimum useful info:**

- `url` (required) - Git clone URL
- `branch` (optional, default: "main") - Branch to track
- `path` (optional, default: inferred from URL) - Local clone path in `repos/`

**4. Is this brilliant or terrible reuse of pyproject.toml?**

**Brilliant ✅** - Here's why:

- `[tool.*]` namespace is designed for exactly this - tool-specific config
- Precedent: pytest, ruff, mypy, black, coverage all use `[tool.X]`
- Makes each proj a valid Python project (can add dependencies, scripts, etc. later)
- Natural evolution: start with repo tracking, grow into full project config
- Zero learning curve for Python developers
- Free validation from TOML parsers and IDE schemas

**Potential concerns:**

- "What if proj isn't Python?" → Still fine, pyproject.toml is just TOML with conventions
- "Won't this confuse tools?" → No, tools only read their own `[tool.X]` namespace
- "Isn't this bloated?" → No, minimum pyproject.toml is tiny (see below)

## File Structure

### Minimal pyproject.toml (repo tracking only)

```toml
[tool.qen]
created = "2025-12-05T10:30:00Z"

[[tool.qen.repos]]
url = "https://github.com/org/repo"
branch = "main"  # optional, defaults to "main"
path = "repos/repo"  # optional, inferred from URL
```

### Full pyproject.toml (with Python project metadata)

```toml
[project]
name = "my-proj"
version = "0.1.0"
description = "Optional project description"

[tool.qen]
created = "2025-12-05T10:30:00Z"

[[tool.qen.repos]]
url = "https://github.com/orgname/backend"
branch = "develop"
path = "repos/backend"

[[tool.qen.repos]]
url = "https://github.com/orgname/frontend"
# branch defaults to "main"
# path inferred as "repos/frontend"
```

## Schema Definition

### [tool.qen] Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `created` | ISO8601 datetime | Yes | - | Proj creation timestamp |
| `description` | string | No | - | Optional proj description |

### [[tool.qen.repos]] Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `url` | string | Yes | - | Git clone URL (https or ssh) |
| `branch` | string | No | `"main"` | Branch to track |
| `path` | string | No | inferred | Local path in `repos/` (relative to proj dir) |

## Implementation Changes

### 1. Update Project Initialization

**File:** `src/qen/project.py`

**Changes:**

- `create_project_structure()`: Create `pyproject.toml` instead of `meta.toml`
- Update stub template to use `[tool.qen]` format
- Add `created` timestamp to `[tool.qen]`

**Before:**

```python
meta_toml_content = """# Repository configuration for this project
# Add repositories using: qen add <repo-url>

[[repos]]
# Example:
# url = "https://github.com/org/repo"
# branch = "main"
# path = "repos/repo"
"""
meta_toml_path.write_text(meta_toml_content)
```

**After:**

```python
pyproject_content = f"""# qen proj configuration
# Add repositories using: qen add <repo-url>

[tool.qen]
created = "{datetime.now(UTC).isoformat()}"

# Example repository:
# [[tool.qen.repos]]
# url = "https://github.com/org/repo"
# branch = "main"
# path = "repos/repo"
"""
pyproject_path.write_text(pyproject_content)
```

### 2. Update README.md Stub

**File:** `src/qen/project.py` (README template)

**Changes:**

- Update reference from `meta.toml` to `pyproject.toml`

**Before:**

```markdown
## Repositories

See `meta.toml` for the list of repositories in this project.
```

**After:**

```markdown
## Repositories

See `pyproject.toml` ([tool.qen] section) for the list of repositories in this project.
```

### 3. Update qen add Command (Future Work)

**File:** TBD (command not yet implemented)

**Changes:**

- Read/write `[tool.qen.repos]` instead of `[[repos]]`
- Use existing `formats.py` TOML parsing utilities
- Validate `url` is present, apply defaults for `branch` and `path`

### 4. Update Tests

**File:** `tests/test_init.py`

**Changes:**

- Update test expectations from `meta.toml` to `pyproject.toml`
- Test parsing of `[tool.qen]` namespace
- Test validation of required fields

### 5. Update Documentation

**File:** `README.md`, `spec/1-qen-init.md`

**Changes:**

- Update all references from `meta.toml` to `pyproject.toml`
- Document `[tool.qen]` schema
- Add migration guide (if needed)

## Migration Strategy

### Current Status

- Code exists but appears unused in production (placeholder tests)
- No evidence of existing projs with `meta.toml` files
- Safe to do **clean cutover** without backward compatibility

### If Migration Needed (Future)

1. Create `qen migrate` command
2. Find all `proj/*/meta.toml` files
3. Convert to `pyproject.toml` with `[tool.qen]` namespace
4. Preserve all data exactly
5. Optionally delete old `meta.toml`

## Example: Full Workflow

```bash
# Initialize qen
$ qen init
✓ Found meta repo at /Users/alice/meta
✓ Detected org: mycompany
✓ Created config at ~/.config/qen/config.toml

# Create a new proj
$ qen init backend-redesign
✓ Created branch: 2025-12-05-backend-redesign
✓ Created directory: proj/2025-12-05-backend-redesign/
✓ Created files:
  - README.md
  - pyproject.toml  # ← Changed from meta.toml
  - repos/
  - .gitignore
✓ Set as current proj: backend-redesign

# Add a repository
$ qen add https://github.com/mycompany/api --branch develop
✓ Added to pyproject.toml:  # ← Changed from meta.toml
  url = "https://github.com/mycompany/api"
  branch = "develop"
  path = "repos/api"
```

## Files to Modify

1. `src/qen/project.py` - Update `create_project_structure()`, README template
2. `tests/test_init.py` - Update test expectations
3. `spec/1-qen-init.md` - Update spec documentation
4. `README.md` - Update examples and references

## Compatibility Notes

- **Backward compatible?** No, but appears safe (no production usage)
- **Tool conflicts?** No, `[tool.qen]` is isolated namespace
- **Python version?** Works with all Python 3.11+ (tomllib) and 3.10 (tomli)
- **IDE support?** Yes, all Python IDEs understand pyproject.toml structure

## Decision: Proceed?

> Recommendation: Yes ✅

This is a brilliant reuse of pyproject.toml because:

1. It follows Python ecosystem conventions perfectly
2. The `[tool.*]` namespace is designed for exactly this use case
3. It provides room for growth (can add project metadata later)
4. Zero learning curve for Python developers
5. Better tooling support than custom config files
6. Clean implementation with no legacy baggage

The only scenario where this would be "terrible" is if qen were meant to manage non-Python projects exclusively, but even then, pyproject.toml is just TOML and works fine.
