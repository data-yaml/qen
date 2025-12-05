"""Repository utilities for URL parsing, path inference, and cloning.

This module provides utilities for working with git repositories:
- Parsing repository URLs in various formats
- Inferring local paths for repositories
- Cloning repositories with branch support
"""

from pathlib import Path

from .git_utils import GitError, parse_git_url, run_git_command


class RepoUrlParseError(Exception):
    """Raised when a repository URL cannot be parsed."""

    pass


def parse_repo_url(repo: str, org: str | None = None) -> dict[str, str]:
    """Parse a repository URL in various formats.

    Supports three formats:
    1. Full URL: https://github.com/org/repo or git@github.com:org/repo
    2. Org/repo format: org/repo (assumes github.com)
    3. Repo-only format: repo (requires org parameter)

    Args:
        repo: Repository identifier in any supported format
        org: Default organization for repo-only format

    Returns:
        Dictionary with 'url', 'host', 'org', and 'repo' keys

    Raises:
        RepoUrlParseError: If URL cannot be parsed or org is missing for repo-only format

    Examples:
        >>> parse_repo_url("https://github.com/myorg/myrepo")
        {'url': 'https://github.com/myorg/myrepo', 'host': 'github.com', 'org': 'myorg', 'repo': 'myrepo'}

        >>> parse_repo_url("myorg/myrepo")
        {'url': 'https://github.com/myorg/myrepo', 'host': 'github.com', 'org': 'myorg', 'repo': 'myrepo'}

        >>> parse_repo_url("myrepo", org="myorg")
        {'url': 'https://github.com/myorg/myrepo', 'host': 'github.com', 'org': 'myorg', 'repo': 'myrepo'}
    """
    repo = repo.strip()

    # Format 0: Local filesystem path (for testing)
    # Check if it's an absolute path or starts with ./ or ../
    if repo.startswith("/") or repo.startswith("./") or repo.startswith("../"):
        from pathlib import Path

        repo_path = Path(repo)
        repo_name = repo_path.name
        return {
            "url": repo,  # Pass through as-is for git clone
            "host": "local",
            "org": "local",
            "repo": repo_name,
        }

    # Format 1: Full URL (https:// or git@)
    if repo.startswith("https://") or repo.startswith("http://") or repo.startswith("git@"):
        try:
            parsed = parse_git_url(repo)
            # Normalize to HTTPS URL
            url = f"https://{parsed['host']}/{parsed['org']}/{parsed['repo']}"
            return {
                "url": url,
                "host": parsed["host"],
                "org": parsed["org"],
                "repo": parsed["repo"],
            }
        except GitError as e:
            raise RepoUrlParseError(f"Cannot parse git URL: {repo}") from e

    # Format 2: org/repo format
    if "/" in repo:
        parts = repo.split("/")
        if len(parts) != 2:
            raise RepoUrlParseError(
                f"Invalid org/repo format: {repo}. Expected exactly one slash."
            )
        org_part, repo_part = parts
        if not org_part or not repo_part:
            raise RepoUrlParseError(f"Invalid org/repo format: {repo}. Both parts must be non-empty.")

        # Assume GitHub for org/repo format
        url = f"https://github.com/{org_part}/{repo_part}"
        return {
            "url": url,
            "host": "github.com",
            "org": org_part,
            "repo": repo_part,
        }

    # Format 3: repo-only (requires org parameter)
    if org:
        url = f"https://github.com/{org}/{repo}"
        return {
            "url": url,
            "host": "github.com",
            "org": org,
            "repo": repo,
        }

    raise RepoUrlParseError(
        f"Cannot parse repository '{repo}'. Provide full URL, org/repo format, "
        "or ensure organization is configured (run 'qen init' first)."
    )


def infer_repo_path(repo_name: str) -> str:
    """Infer the local path for a repository.

    Args:
        repo_name: Name of the repository

    Returns:
        Relative path in the format "repos/{repo_name}"

    Examples:
        >>> infer_repo_path("myrepo")
        'repos/myrepo'
    """
    return f"repos/{repo_name}"


def clone_repository(
    url: str, dest_path: Path, branch: str | None = None, verbose: bool = False
) -> None:
    """Clone a git repository to a destination path.

    Args:
        url: Git clone URL
        dest_path: Destination path for the clone
        branch: Optional branch to checkout after cloning
        verbose: Enable verbose output

    Raises:
        GitError: If clone fails or destination already exists
    """
    # Check if destination already exists
    if dest_path.exists():
        raise GitError(f"Destination already exists: {dest_path}")

    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone the repository
    clone_args = ["clone", url, str(dest_path)]
    if not verbose:
        clone_args.append("--quiet")

    run_git_command(clone_args)

    # Checkout specific branch if requested
    if branch and branch != "main" and branch != "master":
        try:
            # Try to checkout the branch
            run_git_command(["checkout", branch], cwd=dest_path)
        except GitError:
            # If branch doesn't exist locally, try to track remote branch
            try:
                run_git_command(["checkout", "-b", branch, f"origin/{branch}"], cwd=dest_path)
            except GitError as e:
                raise GitError(f"Failed to checkout branch '{branch}': {e}") from e
