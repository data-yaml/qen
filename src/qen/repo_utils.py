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
            raise RepoUrlParseError(f"Invalid org/repo format: {repo}. Expected exactly one slash.")
        org_part, repo_part = parts
        if not org_part or not repo_part:
            raise RepoUrlParseError(
                f"Invalid org/repo format: {repo}. Both parts must be non-empty."
            )

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


def infer_repo_path(
    repo_name: str, branch: str | None = None, project_dir: Path | None = None
) -> str:
    """Infer the local path for a repository.

    When branch is provided, organizes repos by branch: repos/{branch}/{repo_name}.
    This allows multiple branches of the same repository to coexist without collision.

    Args:
        repo_name: Name of the repository
        branch: Branch name (required for proper organization)
        project_dir: Optional project directory (unused, kept for API compatibility)

    Returns:
        Relative path in the format "repos/{branch}/{repo_name}"

    Examples:
        >>> infer_repo_path("myrepo", branch="main")
        'repos/main/myrepo'

        >>> infer_repo_path("myrepo", branch="feature/add-support")
        'repos/feature/add-support/myrepo'

        >>> infer_repo_path("myrepo", branch="2025-12-05-project-name")
        'repos/2025-12-05-project-name/myrepo'
    """
    if not branch:
        raise ValueError("branch parameter is required for infer_repo_path")

    return f"repos/{branch}/{repo_name}"


def check_remote_branch_exists(repo_path: Path, branch: str) -> bool:
    """Check if a branch exists on the remote repository.

    Args:
        repo_path: Path to local git repository
        branch: Branch name to check

    Returns:
        True if remote branch exists, False otherwise
    """
    try:
        result = run_git_command(
            ["ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
            cwd=repo_path,
        )
        # If output is non-empty, remote branch exists
        return bool(result.strip())
    except GitError:
        return False


def clone_repository(
    url: str,
    dest_path: Path,
    branch: str | None = None,
    verbose: bool = False,
    yes: bool = False,
) -> None:
    """Clone a git repository to a destination path.

    Args:
        url: Git clone URL
        dest_path: Destination path for the clone
        branch: Optional branch to checkout after cloning
        verbose: Enable verbose output
        yes: Auto-confirm prompts (create local branch without asking)

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
        # Check if remote branch exists
        remote_branch_exists = check_remote_branch_exists(dest_path, branch)

        if remote_branch_exists:
            # Remote branch exists - checkout with tracking
            try:
                # First try to checkout the branch if it already exists locally
                run_git_command(["checkout", branch], cwd=dest_path)
            except GitError:
                # If it doesn't exist locally, create it from remote
                try:
                    run_git_command(["checkout", "-b", branch, f"origin/{branch}"], cwd=dest_path)
                except GitError as e:
                    raise GitError(f"Failed to checkout remote branch '{branch}': {e}") from e
        else:
            # Remote branch does NOT exist - prompt user
            if not yes:
                import click

                if not click.confirm(
                    f"Branch '{branch}' does not exist on remote '{url}'.\n"
                    f"Create and push new branch to remote?",
                    default=False,
                ):
                    raise GitError(f"Branch '{branch}' does not exist on remote")

            # Create local branch and push to remote (user confirmed or --yes)
            # Check if local branch already exists
            try:
                run_git_command(["checkout", branch], cwd=dest_path)
                # Branch exists locally, just push it
                if verbose:
                    import click

                    click.echo(f"Local branch '{branch}' exists, pushing to remote...")
            except GitError:
                # Branch doesn't exist locally, create it
                try:
                    run_git_command(["checkout", "-b", branch], cwd=dest_path)
                except GitError as e:
                    raise GitError(f"Failed to create branch '{branch}': {e}") from e

            # Push to remote and set upstream tracking
            try:
                run_git_command(["push", "-u", "origin", branch], cwd=dest_path)
                if verbose:
                    import click

                    click.echo(f"Pushed branch '{branch}' to remote")
            except GitError as e:
                raise GitError(f"Failed to push branch '{branch}' to remote: {e}") from e
