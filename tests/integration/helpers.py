"""Integration test helper functions for git and project setup.

This module eliminates duplication of git setup and project creation patterns
across integration tests. All helpers use REAL operations (NO MOCKS).
"""

import subprocess
from pathlib import Path


def create_test_git_repo(
    path: Path,
    *,
    branch: str = "main",
    user_name: str = "QEN Integration Test",
    user_email: str = "test@qen.local",
    with_remote: bool = True,
    remote_org: str = "test-org",
    remote_name: str = "test-meta",
    initial_file: str = "README.md",
    initial_content: str = "# Test Meta Repository\n",
) -> Path:
    """Create a test git repository with standard configuration.

    This helper consolidates git initialization patterns from:
    - test_init.py (tmp_meta_repo fixture)
    - test_pull.py (setup_test_project_optimized)
    - conftest.py (meta_prime_repo fixture)

    Args:
        path: Directory to initialize as git repository (must exist)
        branch: Default branch name (default: "main")
        user_name: Git user.name for commits (default: "QEN Integration Test")
        user_email: Git user.email for commits (default: "test@qen.local")
        with_remote: Add git remotes (default: True)
        remote_org: GitHub organization for remote URL (default: "test-org")
        remote_name: Repository name for remote URL (default: "test-meta")
        initial_file: Filename for initial commit (default: "README.md")
        initial_content: Content for initial file (default: "# Test Meta Repository\\n")

    Returns:
        Path to the initialized git repository (same as input path)

    Example:
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        create_test_git_repo(
            meta_dir,
            remote_org="data-yaml",
            remote_name="my-meta",
        )
    """
    # Initialize git repo with specified branch
    subprocess.run(
        ["git", "init", "-b", branch],
        cwd=path,
        check=True,
        capture_output=True,
    )

    # Configure git user (required for commits)
    subprocess.run(
        ["git", "config", "user.name", user_name],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", user_email],
        cwd=path,
        check=True,
        capture_output=True,
    )

    if with_remote:
        # Add origin remote using file:// URL for local testing
        # This allows cloning without needing a real GitHub repository
        subprocess.run(
            ["git", "remote", "add", "origin", f"file://{path}"],
            cwd=path,
            check=True,
            capture_output=True,
        )

        # Add a fake github remote for org extraction
        # (org extraction parses the URL but doesn't clone from it)
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "github",
                f"https://github.com/{remote_org}/{remote_name}.git",
            ],
            cwd=path,
            check=True,
            capture_output=True,
        )

    # Create initial commit (required for branch creation)
    initial = path / initial_file
    initial.write_text(initial_content)

    subprocess.run(
        ["git", "add", initial_file],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=path,
        check=True,
        capture_output=True,
    )

    return path


def create_test_project(
    meta_repo: Path,
    project_name: str,
    config_dir: Path,
) -> tuple[Path, Path]:
    """Create a QEN test project with per-project meta clone.

    This helper consolidates project creation patterns from:
    - test_pull.py (setup_test_project_optimized function)
    - conftest.py (qen_project fixture)

    Runs qen init to set up global config, then qen init <project> to create
    per-project meta clone. Returns paths to per-project meta and project directory.

    Args:
        meta_repo: Path to meta prime repository (must be git repo with remote)
        project_name: Name for the project (used for branch and directory)
        config_dir: Config directory for isolated qen configuration

    Returns:
        Tuple of (per_project_meta_path, project_dir_path)

    Example:
        meta_repo, project_dir = create_test_project(
            meta_prime_repo,
            "test-project",
            temp_config_dir,
        )

        # Run commands from project directory
        result = run_qen(["add", "repo-url"], temp_config_dir, cwd=meta_repo)
    """
    from datetime import datetime

    from tests.conftest import run_qen

    # Initialize qen global config (extracts meta_remote from meta_repo)
    result = run_qen(["--meta", str(meta_repo), "init"], config_dir)
    assert result.returncode == 0, f"qen init failed: {result.stderr}"

    # Create project (creates per-project meta clone)
    result = run_qen(
        ["--meta", str(meta_repo), "init", project_name, "--yes"],
        config_dir,
    )
    assert result.returncode == 0, f"qen init {project_name} failed: {result.stderr}"

    # Calculate paths using per-project meta architecture
    date_prefix = datetime.now().strftime("%y%m%d")
    branch_name = f"{date_prefix}-{project_name}"
    per_project_meta = meta_repo.parent / f"meta-{project_name}"
    project_dir = per_project_meta / "proj" / branch_name

    # Verify paths exist
    assert per_project_meta.exists(), f"Per-project meta not created: {per_project_meta}"
    assert project_dir.exists(), f"Project directory not created: {project_dir}"

    # Verify we're on the correct branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=per_project_meta,
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = result.stdout.strip()
    assert current_branch == branch_name, (
        f"Per-project meta should be on branch '{branch_name}' but is on '{current_branch}'"
    )

    return per_project_meta, project_dir
