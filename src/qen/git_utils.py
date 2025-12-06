"""Git utilities for meta repository discovery and organization extraction.

This module provides functions for:
- Discovering meta repositories by searching upward from the current directory
- Parsing git remote URLs to extract organization names
- Validating git repository structure
"""

import subprocess
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


def create_branch(path: Path, branch_name: str, switch: bool = True) -> None:
    """Create a new git branch.

    Args:
        path: Path to git repository
        branch_name: Name of branch to create
        switch: If True, switch to the new branch (default: True)

    Raises:
        GitError: If branch creation fails
    """
    if not is_git_repo(path):
        raise NotAGitRepoError(f"Not a git repository: {path}")

    if switch:
        run_git_command(["checkout", "-b", branch_name], cwd=path)
    else:
        run_git_command(["branch", branch_name], cwd=path)


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
