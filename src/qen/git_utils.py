"""Git utilities for meta repository discovery and organization extraction.

This module provides functions for:
- Discovering meta repositories by searching upward from the current directory
- Parsing git remote URLs to extract organization names
- Validating git repository structure
- Getting repository status (branch, changes, sync status)
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class GitError(Exception):
    """Base exception for git-related errors."""

    pass


class MetaRepoNotFoundError(GitError):
    """Raised when meta repository cannot be found."""

    pass


class NotAGitRepoError(GitError):
    """Raised when the current directory is not in a git repository."""

    pass


class AmbiguousOrgError(GitError):
    """Raised when multiple organizations are detected in git remotes."""

    pass


@dataclass
class SyncStatus:
    """Sync status with remote repository."""

    has_upstream: bool
    ahead: int = 0
    behind: int = 0

    def is_up_to_date(self) -> bool:
        """Check if local and remote are in sync."""
        return self.has_upstream and self.ahead == 0 and self.behind == 0

    def is_diverged(self) -> bool:
        """Check if local and remote have diverged."""
        return self.has_upstream and self.ahead > 0 and self.behind > 0

    def description(self) -> str:
        """Get human-readable description of sync status."""
        if not self.has_upstream:
            return "no remote"
        if self.is_up_to_date():
            return "up-to-date"
        if self.is_diverged():
            commit_word_ahead = "commit" if self.ahead == 1 else "commits"
            commit_word_behind = "commit" if self.behind == 1 else "commits"
            return f"diverged (ahead {self.ahead} {commit_word_ahead}, behind {self.behind} {commit_word_behind})"
        if self.ahead > 0:
            commit_word = "commit" if self.ahead == 1 else "commits"
            return f"ahead {self.ahead} {commit_word}"
        if self.behind > 0:
            commit_word = "commit" if self.behind == 1 else "commits"
            return f"behind {self.behind} {commit_word}"
        return "up-to-date"


@dataclass
class RepoStatus:
    """Status information for a git repository."""

    exists: bool
    branch: str | None = None
    modified: list[str] | None = None
    staged: list[str] | None = None
    untracked: list[str] | None = None
    sync: SyncStatus | None = None

    def __post_init__(self) -> None:
        """Initialize default values for lists."""
        if self.modified is None:
            self.modified = []
        if self.staged is None:
            self.staged = []
        if self.untracked is None:
            self.untracked = []

    def is_clean(self) -> bool:
        """Check if repository has no uncommitted changes."""
        return (
            self.exists
            and len(self.modified or []) == 0
            and len(self.staged or []) == 0
            and len(self.untracked or []) == 0
        )

    def status_description(self) -> str:
        """Get human-readable description of status."""
        if not self.exists:
            return "not cloned"

        if self.is_clean():
            return "clean"

        parts = []
        if self.modified:
            parts.append(f"{len(self.modified)} modified")
        if self.staged:
            parts.append(f"{len(self.staged)} staged")
        if self.untracked:
            parts.append(f"{len(self.untracked)} untracked")

        if len(parts) == 1:
            return parts[0]
        return f"mixed ({', '.join(parts)})"


def run_git_command(args: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return its output.

    Args:
        args: Git command arguments (without 'git')
        cwd: Working directory for the command

    Returns:
        Command output as string (stripped)

    Raises:
        GitError: If git command fails
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {e.stderr.strip()}") from e
    except FileNotFoundError as e:
        raise GitError("Git is not installed or not in PATH") from e


def is_git_repo(path: Path) -> bool:
    """Check if a directory is a git repository.

    Args:
        path: Directory path to check

    Returns:
        True if directory is a git repository
    """
    try:
        run_git_command(["rev-parse", "--git-dir"], cwd=path)
        return True
    except GitError:
        return False


def get_repo_name(path: Path) -> str | None:
    """Get the name of the git repository at the given path.

    Args:
        path: Path to git repository

    Returns:
        Repository name (directory name) or None if not a git repo
    """
    if not is_git_repo(path):
        return None
    return path.name


def find_meta_repo(start_path: Path | None = None) -> Path:
    """Search for meta repository by traversing upward from start path.

    Searches current directory and all parent directories for a directory
    named 'meta' that is also a git repository. If not found in the upward
    path, searches peer directories (siblings of current directory and its parents).

    Args:
        start_path: Starting directory (default: current working directory)

    Returns:
        Path to meta repository

    Raises:
        MetaRepoNotFoundError: If meta repository cannot be found
        NotAGitRepoError: If not currently in a git repository
    """
    if start_path is None:
        start_path = Path.cwd()

    # Ensure start_path is absolute
    start_path = start_path.resolve()

    # Check if we're in a git repo at all
    if not is_git_repo(start_path):
        raise NotAGitRepoError("Not in a git repository. qen requires a meta git repository.")

    # Search upward for meta repo
    current = start_path
    for parent in [current] + list(current.parents):
        if parent.name == "meta" and is_git_repo(parent):
            return parent

    # Search peer directories (siblings)
    for parent in [current] + list(current.parents):
        parent_dir = parent.parent
        if parent_dir.exists():
            meta_peer = parent_dir / "meta"
            if meta_peer.exists() and meta_peer.is_dir() and is_git_repo(meta_peer):
                return meta_peer

    raise MetaRepoNotFoundError(
        "Cannot find meta repository. Run from within meta or a subdirectory."
    )


def parse_git_url(url: str) -> dict[str, str]:
    """Parse a git remote URL to extract components.

    Supports both HTTPS and SSH URLs:
    - https://github.com/org/repo.git
    - git@github.com:org/repo.git

    Args:
        url: Git remote URL

    Returns:
        Dictionary with 'host', 'org', and 'repo' keys

    Raises:
        GitError: If URL cannot be parsed
    """
    url = url.strip()

    # Handle SSH URLs (git@host:org/repo.git)
    if url.startswith("git@"):
        try:
            # Split on first colon
            host_part, path_part = url.split(":", 1)
            host = host_part.replace("git@", "")

            # Remove .git suffix if present
            if path_part.endswith(".git"):
                path_part = path_part[:-4]

            # Split path into org/repo
            parts = path_part.split("/")
            if len(parts) >= 2:
                org = parts[0]
                repo = parts[1]
                return {"host": host, "org": org, "repo": repo}
        except (ValueError, IndexError):
            pass

    # Handle HTTPS URLs
    elif url.startswith(("http://", "https://")):
        try:
            parsed = urlparse(url)
            host = parsed.netloc

            # Remove .git suffix from path
            path = parsed.path
            if path.endswith(".git"):
                path = path[:-4]

            # Remove leading slash and split
            parts = path.lstrip("/").split("/")
            if len(parts) >= 2:
                org = parts[0]
                repo = parts[1]
                return {"host": host, "org": org, "repo": repo}
        except Exception:
            pass

    raise GitError(f"Cannot parse git URL: {url}")


def get_git_remotes(path: Path) -> dict[str, str]:
    """Get all git remotes for a repository.

    Args:
        path: Path to git repository

    Returns:
        Dictionary mapping remote names to URLs

    Raises:
        GitError: If not a git repository or command fails
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    output = run_git_command(["remote", "-v"], cwd=path)

    remotes: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue

        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            url = parts[1]
            # Only keep fetch URLs (skip push URLs)
            if len(parts) < 3 or parts[2] == "(fetch)":
                remotes[name] = url

    return remotes


def extract_org_from_remotes(path: Path) -> str:
    """Extract organization name from git remotes.

    Examines all git remotes and extracts organization names.
    If multiple different organizations are found, raises an error.

    Args:
        path: Path to git repository

    Returns:
        Organization name

    Raises:
        NotAGitRepoError: If not a git repository
        AmbiguousOrgError: If multiple organizations detected
        GitError: If no remotes found or cannot parse URLs
    """
    remotes = get_git_remotes(path)

    if not remotes:
        raise GitError("No git remotes found")

    orgs: set[str] = set()
    for _remote_name, url in remotes.items():
        try:
            parsed = parse_git_url(url)
            orgs.add(parsed["org"])
        except GitError:
            # Skip remotes we can't parse
            continue

    if not orgs:
        raise GitError("Cannot extract organization from any git remote")

    if len(orgs) > 1:
        raise AmbiguousOrgError(
            "Multiple organizations detected in git remotes. Please specify explicitly."
        )

    return orgs.pop()


def get_current_branch(path: Path) -> str:
    """Get the current branch name.

    Args:
        path: Path to git repository

    Returns:
        Current branch name

    Raises:
        GitError: If not a git repository or command fails
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path)


def get_default_branch(path: Path) -> str:
    """Get the default branch name for a repository.

    Checks refs/remotes/origin/HEAD to determine the default branch.
    Falls back to current branch, then 'main' if unable to determine.

    Args:
        path: Path to git repository

    Returns:
        Name of the default branch (e.g., 'main', 'master')
    """
    if not is_git_repo(path):
        return "main"

    try:
        result = run_git_command(["symbolic-ref", "refs/remotes/origin/HEAD"], cwd=path)
        # Extract branch name from refs/remotes/origin/HEAD
        # Format: refs/remotes/origin/main -> main
        return result.split("/")[-1]
    except GitError:
        # If we can't find the remote HEAD, try to use the current branch
        # This handles cases where remote tracking isn't set up yet
        try:
            return get_current_branch(path)
        except GitError:
            # If even that fails, fall back to 'main'
            return "main"


def create_branch(
    path: Path, branch_name: str, switch: bool = True, base_branch: str | None = None
) -> None:
    """Create a new git branch.

    Args:
        path: Path to git repository
        branch_name: Name of branch to create
        switch: If True, switch to the new branch (default: True)
        base_branch: Branch or ref to create from (default: repository's default branch)

    Raises:
        GitError: If branch creation fails
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    # Determine base branch/ref
    if base_branch is None:
        default_branch = get_default_branch(path)
        # Check if we have a remote tracking branch for the default
        try:
            run_git_command(
                ["rev-parse", "--verify", f"refs/remotes/origin/{default_branch}"], cwd=path
            )
            # Remote tracking branch exists, use it
            base_branch = f"origin/{default_branch}"
        except GitError:
            # No remote tracking branch, use local branch name
            base_branch = default_branch

    if switch:
        run_git_command(["checkout", "-b", branch_name, base_branch], cwd=path)
    else:
        run_git_command(["branch", branch_name, base_branch], cwd=path)


def branch_exists(path: Path, branch_name: str) -> bool:
    """Check if a branch exists.

    Args:
        path: Path to git repository
        branch_name: Name of branch to check

    Returns:
        True if branch exists
    """
    if not is_git_repo(path):
        return False

    try:
        run_git_command(["rev-parse", "--verify", branch_name], cwd=path)
        return True
    except GitError:
        return False


def get_sync_status(path: Path, fetch: bool = False) -> SyncStatus:
    """Get sync status with remote repository.

    Args:
        path: Path to git repository
        fetch: If True, run git fetch before checking status

    Returns:
        SyncStatus object with ahead/behind counts

    Raises:
        NotAGitRepoError: If not a git repository
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    # Optionally fetch before checking status
    if fetch:
        try:
            run_git_command(["fetch"], cwd=path)
        except GitError:
            # Ignore fetch errors (e.g., no network)
            pass

    try:
        # Get upstream branch
        run_git_command(["rev-parse", "--abbrev-ref", "@{upstream}"], cwd=path)

        # Count commits ahead/behind
        counts = run_git_command(
            ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], cwd=path
        )
        ahead_str, behind_str = counts.split()
        return SyncStatus(has_upstream=True, ahead=int(ahead_str), behind=int(behind_str))
    except GitError:
        # No upstream configured
        return SyncStatus(has_upstream=False)


def get_repo_status(path: Path, fetch: bool = False) -> RepoStatus:
    """Get comprehensive status for a repository.

    Args:
        path: Path to git repository
        fetch: If True, run git fetch before checking sync status

    Returns:
        RepoStatus object with all status information

    Raises:
        GitError: If git commands fail
    """
    # Check if directory exists
    if not path.exists():
        return RepoStatus(exists=False)

    # Check if it's a git repository
    if not is_git_repo(path):
        return RepoStatus(exists=False)

    # Get current branch
    branch = get_current_branch(path)

    # Check for changes using porcelain format
    porcelain = run_git_command(["status", "--porcelain=v1"], cwd=path)

    modified: list[str] = []
    staged: list[str] = []
    untracked: list[str] = []

    for line in porcelain.splitlines():
        if len(line) < 4:
            continue

        status_code = line[:2]
        file_path = line[3:]

        # Staged changes (index)
        if status_code[0] not in (" ", "?"):
            staged.append(file_path)

        # Unstaged changes (working tree)
        if status_code[1] not in (" ", "?"):
            modified.append(file_path)

        # Untracked files
        if status_code == "??":
            untracked.append(file_path)

    # Get sync status with remote
    sync_status = get_sync_status(path, fetch=fetch)

    return RepoStatus(
        exists=True,
        branch=branch,
        modified=modified,
        staged=staged,
        untracked=untracked,
        sync=sync_status,
    )


def git_fetch(path: Path) -> None:
    """Run git fetch on a repository.

    Args:
        path: Path to git repository

    Raises:
        NotAGitRepoError: If not a git repository
        GitError: If fetch fails
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    run_git_command(["fetch"], cwd=path)
