# qen status - Add Repository and PR URLs

## Overview

Enhance the `qen status` command to display clickable URLs for repository branches and pull requests, making it easier for users to navigate directly to GitHub from the terminal output.

## Current Behavior

The `qen status` command displays repository information but requires users to manually construct GitHub URLs:

```bash
$ qen status --pr

Sub-repositories:

  [1] repos/main/repo (https://github.com/org/repo)
    Status: clean
    Branch: feature-branch
    Sync:   up-to-date
    PR:     #123 (open, checks passing)
```

Users must manually:

1. Copy the repository URL and branch name to view the branch on GitHub
2. Navigate to the PR by guessing or constructing the PR URL

## Desired Behavior

Display direct URLs that users can click (in terminal emulators that support hyperlinks) or copy:

```bash
$ qen status --pr

Sub-repositories:

  [1] repos/main/repo (https://github.com/org/repo)
    Status: clean
    Branch: feature-branch → https://github.com/org/repo/tree/feature-branch
    Sync:   up-to-date
    PR:     #123 (open, checks passing) → https://github.com/org/repo/pull/123
```

**Key improvements:**

- Branch line includes direct link to view branch on GitHub
- PR line includes direct link to view PR on GitHub
- URLs use arrow symbol `→` for clear visual separation
- Works in all terminals (clickable in supported terminals, copy-pasteable in all terminals)

## Implementation Design

### Step 1: Add URL Builder Utility

**File:** [src/qen/commands/status.py](../../src/qen/commands/status.py)

**Location:** Add after imports, before main functions (around line 50)

```python
def build_branch_url(repo_url: str, branch: str) -> str | None:
    """Build a GitHub branch URL from repository URL and branch name.

    Args:
        repo_url: Repository URL (e.g., "https://github.com/org/repo")
        branch: Branch name (e.g., "feature-branch")

    Returns:
        Branch URL in format: https://github.com/org/repo/tree/branch
        Returns None if not a GitHub URL

    Examples:
        >>> build_branch_url("https://github.com/org/repo", "main")
        "https://github.com/org/repo/tree/main"

        >>> build_branch_url("https://github.com/org/repo/", "feature")
        "https://github.com/org/repo/tree/feature"

        >>> build_branch_url("https://github.com/org/repo.git", "dev")
        "https://github.com/org/repo/tree/dev"

        >>> build_branch_url("https://gitlab.com/org/repo", "main")
        None

        >>> build_branch_url("/local/path/repo", "main")
        None
    """
    # Only handle GitHub URLs
    if not repo_url.startswith("https://github.com/"):
        return None

    # Normalize URL: remove trailing slash and .git suffix
    clean_url = repo_url.rstrip("/").removesuffix(".git")

    # Build branch URL using GitHub's /tree/ path
    return f"{clean_url}/tree/{branch}"
```

**Design rationale:**

- Returns `None` for non-GitHub URLs (GitLab, Bitbucket, local paths, etc.)
- Handles common URL variations (trailing slash, `.git` suffix)
- Simple string manipulation (no regex needed)
- Type-safe with explicit return type

### Step 2: Update Output Formatting - Branch URLs

**File:** [src/qen/commands/status.py](../../src/qen/commands/status.py)

**Function:** `format_status_output()` (lines 128-231)

**Location:** Around line 189 where branch is displayed

**Current code:**

```python
lines.append(f"    Branch: {repo_status.branch}")
```

**Updated code:**

```python
# Build branch line with optional URL
branch_line = f"    Branch: {repo_status.branch}"
branch_url = build_branch_url(repo_config.url, repo_status.branch)
if branch_url:
    branch_line += f" → {branch_url}"
lines.append(branch_line)
```

**Design rationale:**

- Only append URL if `build_branch_url()` returns non-None
- Uses arrow `→` for clear visual separation
- Preserves existing format when URL not available
- No breaking changes to output structure

### Step 3: Update Output Formatting - PR URLs

**File:** [src/qen/commands/status.py](../../src/qen/commands/status.py)

**Function:** `format_status_output()` (lines 128-231)

**Location:** Around line 197-198 where PR info is displayed

**Current code:**

```python
pr_line = f"    PR:     #{pr_info.pr_number}"

# Add status and checks
if pr_info.pr_status:
    pr_line += f" ({pr_info.pr_status}"
    if pr_info.pr_checks:
        pr_line += f", checks {pr_info.pr_checks}"
    pr_line += ")"

lines.append(pr_line)
```

**Updated code:**

```python
pr_line = f"    PR:     #{pr_info.pr_number}"

# Add status and checks
if pr_info.pr_status:
    pr_line += f" ({pr_info.pr_status}"
    if pr_info.pr_checks:
        pr_line += f", checks {pr_info.pr_checks}"
    pr_line += ")"

# Add PR URL if available
if pr_info.pr_url:
    pr_line += f" → {pr_info.pr_url}"

lines.append(pr_line)
```

**Design rationale:**

- PR URL already available in `pr_info.pr_url` (from GitHub API via `gh pr view`)
- Simply append URL with arrow separator
- Only show URL if it exists (defensive programming)
- No need to build URL - GitHub API provides canonical URL

## Data Availability

All necessary data is already collected by existing code:

### Repository URL

- **Source:** `RepoConfig.url` (loaded from `pyproject.toml`)
- **Format:** Full GitHub URL (e.g., "<https://github.com/org/repo>")
- **Already used:** Displayed in first line of each repo section

### Branch Name

- **Source:** `RepoStatus.branch` (from git operations)
- **Format:** Branch name string (e.g., "feature-branch")
- **Already used:** Displayed in "Branch:" line

### PR URL

- **Source:** `PrInfo.pr_url` (from `gh pr view` command)
- **Format:** Full PR URL (e.g., "<https://github.com/org/repo/pull/123>")
- **Already used:** Available in PrInfo dataclass but not displayed
- **How it's fetched:** See [src/qen/commands/pr.py:166-234](../../src/qen/commands/pr.py#L166-L234) - `get_pr_info_for_branch()` function

**No new data fetching required** - this is purely a display enhancement.

## Edge Cases

### Non-GitHub Repository URLs

**Scenario:** Repository URL is not a GitHub URL

**Examples:**

- `https://gitlab.com/org/repo`
- `https://bitbucket.org/org/repo`
- `git@gitlab.com:org/repo.git`
- `/local/path/to/repo`
- `file:///Users/user/repos/project`

**Behavior:**

```python
build_branch_url("https://gitlab.com/org/repo", "main")  # Returns None
```

**Output:**

```text
  [1] repos/main/repo (https://gitlab.com/org/repo)
    Status: clean
    Branch: main
    Sync:   up-to-date
```

**Rationale:** No URL shown (no broken/invalid URLs in output)

### URL Variations

**Scenario:** GitHub URLs with trailing slashes or `.git` suffixes

**Examples:**

- `https://github.com/org/repo/` (trailing slash)
- `https://github.com/org/repo.git` (git suffix)
- `https://github.com/org/repo/.git` (both)

**Behavior:**

```python
build_branch_url("https://github.com/org/repo/", "main")
# Returns: "https://github.com/org/repo/tree/main"

build_branch_url("https://github.com/org/repo.git", "main")
# Returns: "https://github.com/org/repo/tree/main"
```

**Rationale:** Normalize URLs before building branch URL

### Branch Names with Special Characters

**Scenario:** Branch names contain `/`, `-`, `_`, or other characters

**Examples:**

- `feature/new-thing` (slash in name)
- `user/email@domain` (at symbol)
- `fix-bug-#123` (hash symbol)

**Behavior:**

```python
build_branch_url("https://github.com/org/repo", "feature/new-thing")
# Returns: "https://github.com/org/repo/tree/feature/new-thing"
```

**GitHub URL handling:** GitHub automatically URL-encodes branch names when accessed, so we can pass them as-is. The browser will handle encoding.

**Rationale:** No manual encoding needed - GitHub and browsers handle this

### No PR Exists

**Scenario:** Repository has no associated PR

**Current behavior:**

```text
  [1] repos/main/repo (https://github.com/org/repo)
    Status: clean
    Branch: main → https://github.com/org/repo/tree/main
    Sync:   up-to-date
```

**PR line not shown** (existing behavior, unchanged)

**Rationale:** Only show PR info when PR exists

### PR URL Not Available

**Scenario:** PR exists but `pr_info.pr_url` is None (edge case)

**Behavior:**

```python
if pr_info.pr_url:
    pr_line += f" → {pr_info.pr_url}"
```

**Output:**

```text
    PR:     #123 (open, checks passing)
```

**No URL shown** if `pr_url` is None

**Rationale:** Defensive programming - don't assume data availability

## Testing Strategy

### Unit Tests

**File:** [tests/unit/qen/commands/test_status.py](../../tests/unit/qen/commands/test_status.py)

**Test: URL Builder Function**

```python
def test_build_branch_url_basic():
    """Test building branch URL from GitHub repository URL."""
    url = build_branch_url("https://github.com/org/repo", "main")
    assert url == "https://github.com/org/repo/tree/main"


def test_build_branch_url_feature_branch():
    """Test building URL for feature branch with slash."""
    url = build_branch_url("https://github.com/org/repo", "feature/new-thing")
    assert url == "https://github.com/org/repo/tree/feature/new-thing"


def test_build_branch_url_trailing_slash():
    """Test handling repository URL with trailing slash."""
    url = build_branch_url("https://github.com/org/repo/", "main")
    assert url == "https://github.com/org/repo/tree/main"


def test_build_branch_url_git_suffix():
    """Test handling repository URL with .git suffix."""
    url = build_branch_url("https://github.com/org/repo.git", "main")
    assert url == "https://github.com/org/repo/tree/main"


def test_build_branch_url_trailing_slash_and_git():
    """Test handling both trailing slash and .git suffix."""
    url = build_branch_url("https://github.com/org/repo/.git", "main")
    assert url == "https://github.com/org/repo/tree/main"


def test_build_branch_url_non_github():
    """Test non-GitHub URLs return None."""
    assert build_branch_url("https://gitlab.com/org/repo", "main") is None
    assert build_branch_url("https://bitbucket.org/org/repo", "main") is None


def test_build_branch_url_local_path():
    """Test local filesystem paths return None."""
    assert build_branch_url("/local/path/repo", "main") is None
    assert build_branch_url("file:///Users/user/repo", "main") is None


def test_build_branch_url_ssh_format():
    """Test SSH format URLs return None (not supported)."""
    assert build_branch_url("git@github.com:org/repo.git", "main") is None
```

**Test: Output Formatting with URLs**

```python
def test_format_status_output_includes_branch_url(tmp_path, mocker):
    """Test that branch URLs are included in status output."""
    # Setup mock repo status with GitHub URL
    repo_config = RepoConfig(
        url="https://github.com/org/repo",
        branch="feature-branch",
        path="repos/repo"
    )
    repo_status = RepoStatus(
        path=tmp_path,
        branch="feature-branch",
        status=GitStatus.CLEAN,
        sync=SyncStatus(ahead=0, behind=0, state=SyncState.UP_TO_DATE)
    )

    output = format_status_output(
        repo_statuses=[(repo_config, repo_status)],
        pr_info_map={},
        verbose=False,
        current_dir=tmp_path
    )

    # Verify branch URL appears in output
    assert "Branch: feature-branch → https://github.com/org/repo/tree/feature-branch" in output


def test_format_status_output_includes_pr_url(tmp_path, mocker):
    """Test that PR URLs are included when PR exists."""
    # Setup repo with PR info
    repo_config = RepoConfig(
        url="https://github.com/org/repo",
        branch="pr-branch",
        path="repos/repo"
    )
    repo_status = RepoStatus(
        path=tmp_path,
        branch="pr-branch",
        status=GitStatus.CLEAN,
        sync=SyncStatus(ahead=0, behind=0, state=SyncState.UP_TO_DATE)
    )
    pr_info = PrInfo(
        repo_path=str(tmp_path),
        repo_url="https://github.com/org/repo",
        branch="pr-branch",
        has_pr=True,
        pr_number=123,
        pr_url="https://github.com/org/repo/pull/123",
        pr_status="open",
        pr_checks="passing"
    )

    output = format_status_output(
        repo_statuses=[(repo_config, repo_status)],
        pr_info_map={str(tmp_path): pr_info},
        verbose=False,
        current_dir=tmp_path
    )

    # Verify PR URL appears in output
    assert "PR:     #123 (open, checks passing) → https://github.com/org/repo/pull/123" in output


def test_format_status_output_no_url_for_non_github(tmp_path, mocker):
    """Test that non-GitHub repos don't show branch URLs."""
    repo_config = RepoConfig(
        url="https://gitlab.com/org/repo",
        branch="main",
        path="repos/repo"
    )
    repo_status = RepoStatus(
        path=tmp_path,
        branch="main",
        status=GitStatus.CLEAN,
        sync=SyncStatus(ahead=0, behind=0, state=SyncState.UP_TO_DATE)
    )

    output = format_status_output(
        repo_statuses=[(repo_config, repo_status)],
        pr_info_map={},
        verbose=False,
        current_dir=tmp_path
    )

    # Verify no arrow or URL in branch line
    assert "Branch: main\n" in output or "Branch: main    " in output
    assert "→" not in output.split("Branch:")[1].split("\n")[0]


def test_format_status_output_handles_missing_pr_url(tmp_path, mocker):
    """Test graceful handling when PR exists but pr_url is None."""
    repo_config = RepoConfig(
        url="https://github.com/org/repo",
        branch="pr-branch",
        path="repos/repo"
    )
    repo_status = RepoStatus(
        path=tmp_path,
        branch="pr-branch",
        status=GitStatus.CLEAN,
        sync=SyncStatus(ahead=0, behind=0, state=SyncState.UP_TO_DATE)
    )
    pr_info = PrInfo(
        repo_path=str(tmp_path),
        repo_url="https://github.com/org/repo",
        branch="pr-branch",
        has_pr=True,
        pr_number=123,
        pr_url=None,  # Simulate missing PR URL
        pr_status="open",
        pr_checks="passing"
    )

    output = format_status_output(
        repo_statuses=[(repo_config, repo_status)],
        pr_info_map={str(tmp_path): pr_info},
        verbose=False,
        current_dir=tmp_path
    )

    # Verify PR info shown but no URL
    assert "PR:     #123" in output
    # Should not have arrow after PR line
    pr_line = [line for line in output.split("\n") if "PR:" in line][0]
    assert "→" not in pr_line
```

### Integration Tests

**File:** [tests/integration/test_status_real.py](../../tests/integration/test_status_real.py) (new file)

**IMPORTANT:** Integration tests MUST use real repositories and real GitHub data.

```python
@pytest.mark.integration
def test_status_shows_branch_urls(test_project_with_real_repo):
    """Test that status command displays branch URLs for GitHub repos."""
    project_dir = test_project_with_real_repo

    # Run qen status
    result = subprocess.run(
        ["qen", "status"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True
    )

    # Verify branch URL appears in output
    assert "→ https://github.com/" in result.stdout
    assert "/tree/" in result.stdout


@pytest.mark.integration
def test_status_shows_pr_urls(test_project_with_pr_branch):
    """Test that status command displays PR URLs when PRs exist."""
    project_dir = test_project_with_pr_branch

    # Run qen status --pr
    result = subprocess.run(
        ["qen", "status", "--pr"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True
    )

    # Verify PR URL appears in output
    assert "PR:" in result.stdout
    assert "→ https://github.com/" in result.stdout
    assert "/pull/" in result.stdout


@pytest.mark.integration
def test_status_multiple_repos_with_urls(test_project_with_multiple_repos):
    """Test status with multiple repos shows URL for each."""
    project_dir = test_project_with_multiple_repos

    # Run qen status --pr
    result = subprocess.run(
        ["qen", "status", "--pr"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=True
    )

    # Count occurrences of branch URLs
    branch_url_count = result.stdout.count("/tree/")
    # Should match number of repos
    assert branch_url_count >= 2
```

**Note:** Integration tests verify the feature works with real data, but don't need exhaustive coverage of edge cases (that's what unit tests are for).

## Manual Testing

After implementation, test manually with real projects:

```bash
# Test with project that has GitHub repos
cd proj/YYMMDD-some-project

# Test basic status with branch URLs
qen status

# Test with PR URLs
qen status --pr

# Test with multiple repos
qen status --pr --verbose
```

**Expected output:**

```text
Sub-repositories:

  [1] repos/main/repo (https://github.com/data-yaml/qen)
    Status: clean
    Branch: main → https://github.com/data-yaml/qen/tree/main
    Sync:   up-to-date
    PR:     #42 (open, checks passing) → https://github.com/data-yaml/qen/pull/42

  [2] repos/test/qen-test (https://github.com/data-yaml/qen-test)
    Status: clean
    Branch: feature/new-thing → https://github.com/data-yaml/qen-test/tree/feature/new-thing
    Sync:   up-to-date
```

**Verify:**

- ✅ URLs are properly formatted
- ✅ URLs are clickable in terminal (if supported)
- ✅ URLs can be copy-pasted and work in browser
- ✅ Non-GitHub repos don't show broken URLs

## Files Modified

### Source Code

- [src/qen/commands/status.py](../../src/qen/commands/status.py)
  - Add `build_branch_url()` function (around line 50)
  - Update `format_status_output()` function (lines ~189 and ~197)

### Tests

- [tests/unit/qen/commands/test_status.py](../../tests/unit/qen/commands/test_status.py)
  - Add tests for `build_branch_url()` function
  - Update tests for `format_status_output()` to expect URLs
  - Add edge case tests for non-GitHub repos

- [tests/integration/test_status_real.py](../../tests/integration/test_status_real.py) (new file)
  - Test branch URLs appear in real output
  - Test PR URLs appear when PRs exist
  - Test multiple repos show URLs correctly

### Documentation

- [spec/4-tests/status-urls.md](../../spec/4-tests/status-urls.md) (this file)

## Success Criteria

### Implementation Checklist

- [ ] Add `build_branch_url()` function to status.py
- [ ] Update branch line formatting to include URL
- [ ] Update PR line formatting to include URL
- [ ] Handle non-GitHub repos gracefully (no URL shown)
- [ ] Handle missing PR URLs gracefully (no crash)

### Testing Checklist

- [ ] Unit tests for `build_branch_url()` with various inputs
- [ ] Unit tests for GitHub URL normalization (trailing slash, .git suffix)
- [ ] Unit tests for non-GitHub URLs returning None
- [ ] Unit tests for output format with branch URLs
- [ ] Unit tests for output format with PR URLs
- [ ] Unit tests for non-GitHub repos (no URL in output)
- [ ] Unit tests for missing PR URLs (graceful handling)
- [ ] Integration tests with real repositories
- [ ] Integration tests with real PRs
- [ ] All tests pass: `./poe test-all`

### User Experience Checklist

- [ ] Branch URLs are clearly separated from branch names
- [ ] PR URLs are clearly separated from PR info
- [ ] URLs are properly formatted (no broken/invalid URLs)
- [ ] URLs work when clicked in supported terminals
- [ ] URLs work when copy-pasted to browser
- [ ] Non-GitHub repos don't show confusing/broken URLs
- [ ] Output remains readable and well-formatted
- [ ] No breaking changes to existing output structure

## Design Rationale

### Why Arrow Symbol `→`?

- **Clear visual separation:** Distinguishes URL from label text
- **Universal understanding:** Arrow indicates "points to" or "link to"
- **Single character:** Doesn't add excessive visual clutter
- **Terminal-safe:** Works in all terminals (no special font required)
- **Precedent:** Commonly used in CLI tools for showing relationships

### Why Only GitHub URLs?

- **Scope control:** GitHub is the primary use case for qen
- **Avoid broken URLs:** Different git hosts have different URL patterns
- **Simple implementation:** No need for complex URL pattern detection
- **Future extensible:** Can add support for other hosts later if needed

**Future enhancement:** Could add support for GitLab, Bitbucket, etc. by:

1. Detecting host from URL
2. Using host-specific URL patterns
3. Adding tests for each host

### Why No URL Encoding?

- **GitHub handles it:** GitHub's servers handle URL encoding automatically
- **Browser handles it:** Modern browsers encode URLs when clicked
- **Simplicity:** No need for `urllib.parse.quote()` or similar
- **Works in practice:** Branch names with special chars (`/`, `-`, `_`) work as-is

**Edge case:** If a branch name contains truly unusual characters (spaces, unicode), the URL might not work perfectly, but this is extremely rare in practice and GitHub would reject such branch names anyway.

### Why Reuse `pr_info.pr_url`?

- **Already available:** GitHub API provides canonical PR URL
- **Authoritative:** URL comes from GitHub, not constructed by us
- **Handles edge cases:** GitHub handles redirects, renamed repos, etc.
- **No duplication:** Don't need to parse owner/repo and build URL

## Related Code

### Existing URL Parsing

[src/qen/commands/pr.py:814-844](../../src/qen/commands/pr.py#L814-L844) - `parse_repo_owner_and_name()`

This function parses URLs to extract owner and repo name. We could use it to build URLs, but simpler to just use string manipulation since we already have the full repo URL.

### PR Info Fetching

[src/qen/commands/pr.py:166-234](../../src/qen/commands/pr.py#L166-L234) - `get_pr_info_for_branch()`

This function already fetches PR URLs from GitHub API via `gh pr view`. No changes needed.

### Repository Configuration

[src/qen/pyproject_utils.py:24-33](../../src/qen/pyproject_utils.py#L24-L33) - `RepoConfig` dataclass

Already contains `url` field with full repository URL. No changes needed.

## References

### Related Specifications

- [spec/2-status/01-qen-pull.md](../2-status/01-qen-pull.md) - PR status metadata
- [spec/2-status/02-pr-status-display.md](../2-status/02-pr-status-display.md) - PR display formatting

### Related Commands

- `qen status` - Current command being enhanced
- `qen pr status` - Could benefit from similar URL enhancements (future work)

---

*This specification follows the testing philosophy from [AGENTS.md](../../AGENTS.md):*
*Unit tests use mocks for speed, integration tests NEVER use mocks.*
