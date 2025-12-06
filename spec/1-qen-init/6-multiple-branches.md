# Spec: Multiple Branches for Same Repository

## Overview

Allow adding the same repository multiple times with different branches to support parallel work across feature branches.

## Motivation

**Use case:** Working on multiple feature branches of the same repository simultaneously:

```bash
# Add deployment repo with two different feature branches
qen add deployment -b 2220-benchling-clean-up-security-groups
qen add deployment -b 2221-benchling-fine-grained-iam-role
```

This is a **core design requirement** for qen - supporting parallel work on multiple branches is essential for productivity.

## Current Behavior (Broken)

```bash
$ qen add deployment -b 2220-benchling-clean-up-security-groups
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2220-benchling-clean-up-security-groups
  Path: /path/to/repos/deployment

$ qen add deployment -b 2221-benchling-fine-grained-iam-role
Error: Repository already exists in project: https://github.com/quiltdata/deployment
Aborted!
```

**Problem:** The uniqueness check only looks at `url`, not `url + branch` combination.

## Expected Behavior (Fixed)

```bash
$ qen add deployment -b 2220-benchling-clean-up-security-groups
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2220-benchling-clean-up-security-groups
  Path: /path/to/repos/deployment-2220-benchling-clean-up-security-groups

$ qen add deployment -b 2221-benchling-fine-grained-iam-role
✓ Added repository: https://github.com/quiltdata/deployment
  Branch: 2221-benchling-fine-grained-iam-role
  Path: /path/to/repos/deployment-2221-benchling-fine-grained-iam-role
```

**Result in pyproject.toml:**

```toml
[[tool.qen.repos]]
url = "https://github.com/quiltdata/deployment"
branch = "2220-benchling-clean-up-security-groups"
path = "repos/deployment-2220-benchling-clean-up-security-groups"

[[tool.qen.repos]]
url = "https://github.com/quiltdata/deployment"
branch = "2221-benchling-fine-grained-iam-role"
path = "repos/deployment-2221-benchling-fine-grained-iam-role"
```

## Design Decisions

### 1. Uniqueness Key: `(url, branch)` tuple

**Rule:** A repository entry is unique by the combination of `url` + `branch`.

**Reasoning:**
- Same URL with different branches = different working directories
- Same URL with same branch = duplicate (should error)
- Different paths don't matter for uniqueness (user can override path)

### 2. Automatic Path Suffixing

**Rule:** When adding same repo with different branches, auto-suffix path with branch name.

**Logic:**
```python
# First instance (main branch) - no suffix
repos/deployment

# Second instance (different branch) - add suffix
repos/deployment-2220-benchling-clean-up-security-groups

# Third instance (another branch) - add suffix
repos/deployment-2221-benchling-fine-grained-iam-role
```

**Reasoning:**
- Prevents path collisions on filesystem
- Makes it obvious which directory corresponds to which branch
- User can still override with explicit `--path` if desired

### 3. Explicit Path Override

**Rule:** Allow `--path` to override auto-generated path, but still enforce `(url, branch)` uniqueness.

**Example:**
```bash
# User specifies custom path
qen add deployment -b feature-x --path repos/custom/deployment-x

# Still errors if (url, branch) combo already exists
qen add deployment -b feature-x --path repos/other/path
Error: Repository already exists with branch 'feature-x'
```

## Implementation Changes

### 1. Update `repo_exists_in_pyproject()` function

**File:** `src/qen/pyproject_utils.py`

**Change:** Check `(url, branch)` tuple instead of just `url`.

**Before:**
```python
def repo_exists_in_pyproject(project_dir: Path, url: str) -> bool:
    """Check if a repository URL already exists in pyproject.toml."""
    # ... checks only url ...
    for repo in repos:
        if isinstance(repo, dict) and repo.get("url") == url:
            return True
    return False
```

**After:**
```python
def repo_exists_in_pyproject(project_dir: Path, url: str, branch: str) -> bool:
    """Check if a repository with given URL and branch already exists.

    Args:
        project_dir: Path to project directory
        url: Repository URL to check
        branch: Branch name to check

    Returns:
        True if (url, branch) combination exists in [[tool.qen.repos]]
    """
    # ... same navigation logic ...

    # Check if (url, branch) tuple exists
    for repo in repos:
        if isinstance(repo, dict):
            if repo.get("url") == url and repo.get("branch") == branch:
                return True
    return False
```

### 2. Update `infer_repo_path()` function

**File:** `src/qen/repo_utils.py`

**Change:** Add optional `branch` parameter to include branch in path when needed.

**New signature:**
```python
def infer_repo_path(
    repo_name: str,
    branch: str | None = None,
    project_dir: Path | None = None
) -> str:
    """Infer repository path from name and optionally branch.

    If branch is provided and there's a potential collision with existing
    repos, append the branch name to make the path unique.

    Args:
        repo_name: Repository name (e.g., "deployment")
        branch: Optional branch name for disambiguation
        project_dir: Optional project directory to check for collisions

    Returns:
        Path string like "repos/deployment" or "repos/deployment-branch-name"
    """
```

**Logic:**
```python
# Base path
base_path = f"repos/{repo_name}"

# If branch provided and project_dir exists, check for collision
if branch and project_dir:
    pyproject_path = project_dir / "pyproject.toml"
    if pyproject_path.exists():
        # Check if base_path already used by different branch
        config = read_pyproject(project_dir)
        existing_repos = config.get("tool", {}).get("qen", {}).get("repos", [])

        for repo in existing_repos:
            if repo.get("path") == base_path and repo.get("branch") != branch:
                # Collision: same path, different branch
                # Append branch to make unique
                return f"repos/{repo_name}-{branch}"

return base_path
```

### 3. Update `add_repository()` function

**File:** `src/qen/commands/add.py`

**Change:** Pass `branch` to `repo_exists_in_pyproject()` check.

**Before (line 143):**
```python
if repo_exists_in_pyproject(project_dir, url):
    click.echo(f"Error: Repository already exists in project: {url}", err=True)
    raise click.Abort()
```

**After:**
```python
if repo_exists_in_pyproject(project_dir, url, branch):
    click.echo(
        f"Error: Repository already exists in project: {url} (branch: {branch})",
        err=True
    )
    raise click.Abort()
```

### 4. Update path inference call

**File:** `src/qen/commands/add.py` (line 135)

**Change:** Pass branch and project_dir for smart path inference.

**Before:**
```python
if path is None:
    path = infer_repo_path(repo_name)
```

**After:**
```python
if path is None:
    path = infer_repo_path(repo_name, branch, project_dir)
```

## Test Cases

### Test: Allow same repo with different branches

```python
def test_add_same_repo_different_branches():
    """Test adding same repository with different branches."""
    # Add first branch
    add_repository("https://github.com/org/repo", branch="feature-1")

    # Add second branch - should succeed
    add_repository("https://github.com/org/repo", branch="feature-2")

    # Check pyproject.toml has both entries
    config = read_pyproject(project_dir)
    repos = config["tool"]["qen"]["repos"]
    assert len(repos) == 2
    assert repos[0]["branch"] == "feature-1"
    assert repos[1]["branch"] == "feature-2"
    assert repos[0]["path"] != repos[1]["path"]  # Different paths
```

### Test: Prevent duplicate (url, branch) combination

```python
def test_prevent_duplicate_url_branch():
    """Test that duplicate (url, branch) is rejected."""
    # Add first time
    add_repository("https://github.com/org/repo", branch="main")

    # Try to add again with same branch - should error
    with pytest.raises(click.Abort):
        add_repository("https://github.com/org/repo", branch="main")
```

### Test: Auto-suffix paths for multiple branches

```python
def test_auto_suffix_paths():
    """Test automatic path suffixing for multiple branches."""
    # First branch gets clean path
    add_repository("deployment", branch="main")
    config = read_pyproject(project_dir)
    assert config["tool"]["qen"]["repos"][0]["path"] == "repos/deployment"

    # Second branch gets suffixed path
    add_repository("deployment", branch="feature-x")
    config = read_pyproject(project_dir)
    assert config["tool"]["qen"]["repos"][1]["path"] == "repos/deployment-feature-x"
```

## Migration

**No migration needed** - this is a bug fix for newly implemented functionality.

## Files to Modify

1. `src/qen/pyproject_utils.py` - Update `repo_exists_in_pyproject()` signature and logic
2. `src/qen/repo_utils.py` - Update `infer_repo_path()` to handle branch suffixing
3. `src/qen/commands/add.py` - Update function calls to pass branch parameter
4. `tests/qen/test_add.py` - Add test cases for multiple branches
5. `spec/1-qen-init/3-pyproject.md` - Add clarification about multiple branches

## Documentation Updates

Update spec [3-pyproject.md](3-pyproject.md) to add explicit example:

```toml
# Example: Same repository, multiple branches
[[tool.qen.repos]]
url = "https://github.com/org/deployment"
branch = "2220-benchling-clean-up-security-groups"
path = "repos/deployment-2220-benchling-clean-up-security-groups"

[[tool.qen.repos]]
url = "https://github.com/org/deployment"
branch = "2221-benchling-fine-grained-iam-role"
path = "repos/deployment-2221-benchling-fine-grained-iam-role"
```

## Decision

This is a **critical bug fix**, not a design change. The existing architecture already supports this - it just needs the uniqueness check corrected from `url` to `(url, branch)`.
