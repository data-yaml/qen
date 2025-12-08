"""Integration tests for qen add command using REAL operations.

NO MOCKS ALLOWED. These tests use REAL git operations and REAL GitHub repositories.

These tests validate:
1. Real git clone operations against GitHub repositories
2. pyproject.toml TOML format and updates
3. Repository tracking with correct indices
4. Various URL format parsing (HTTPS, SSH, short format)
5. Custom branch and path handling
6. Error handling for invalid inputs

Test repository: https://github.com/data-yaml/qen-test
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

from tests.conftest import run_qen


@pytest.mark.integration
def test_add_with_full_https_url(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with full HTTPS URL - REAL CLONE.

    Tests adding a repository with full HTTPS URL format:
    https://github.com/data-yaml/qen-test

    Verifies:
    - Real git clone succeeds
    - Repository is cloned to repos/ directory
    - pyproject.toml is updated with correct [[tool.qen.repos]] entry
    - Entry has url, branch, and path fields
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Note: After `qen init <project>`, we're on the project branch (251208-test-project)
    # When --branch is not specified, qen add defaults to the current meta branch
    # So we need to explicitly specify --branch main to test with main branch

    # Add repository with full HTTPS URL and explicit --branch main (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    # With --branch main, path is repos/main/qen-test
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"
    assert (repo_path / "README.md").exists(), "README.md not found in cloned repo"

    # Verify pyproject.toml was updated with correct TOML format
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml not found"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    # Verify [[tool.qen.repos]] structure
    assert "tool" in pyproject
    assert "qen" in pyproject["tool"]
    assert "repos" in pyproject["tool"]["qen"]
    repos = pyproject["tool"]["qen"]["repos"]
    assert isinstance(repos, list)
    assert len(repos) == 1

    # Verify repo entry fields
    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"  # Explicitly specified with --branch
    assert repo_entry["path"] == "repos/main/qen-test"  # Path includes branch


@pytest.mark.integration
def test_add_with_ssh_url(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with SSH URL format - REAL CLONE.

    Tests adding a repository with SSH URL format:
    git@github.com:data-yaml/qen-test.git

    Verifies that SSH URLs are parsed correctly and cloning works.
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository with SSH URL and explicit --branch main (REAL CLONE)
    # Note: SSH URL is normalized to HTTPS URL internally
    result = run_qen(
        [
            "add",
            "git@github.com:data-yaml/qen-test.git",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    # SSH URL is normalized to HTTPS
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_short_format(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with short format (org/repo) - REAL CLONE.

    Tests adding a repository with short format:
    data-yaml/qen-test

    Verifies that short format is expanded to full URL using configured org.
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository with short format and explicit --branch main (REAL CLONE)
    result = run_qen(
        ["add", "data-yaml/qen-test", "--branch", "main", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify repository was cloned (REAL git operation)
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_custom_branch(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom branch name - REAL CLONE.

    Tests adding a repository with a custom branch using --branch flag.

    Verifies:
    - Repository is cloned and checked out to custom branch
    - pyproject.toml records the correct branch name
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add repository with custom branch (REAL CLONE)
    # When --branch is specified explicitly, that becomes the tracked branch
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify repository was cloned with explicit branch (REAL git operation)
    # With explicit --branch, path is repos/<branch>/<repo-name>
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify we're on the correct branch
    branch_result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    current_branch = branch_result.stdout.strip()
    assert current_branch == "main", f"Expected branch 'main', got '{current_branch}'"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"
    assert repo_entry["path"] == "repos/main/qen-test"


@pytest.mark.integration
def test_add_with_custom_path(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom local path - REAL CLONE.

    Tests adding a repository with a custom local path using --path flag.

    Verifies:
    - Repository is cloned to custom path
    - pyproject.toml records the custom path
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Checkout main branch before adding (to get consistent branch default)
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add repository with custom path and explicit --branch main (REAL CLONE)
    custom_path = "repos/my-custom-test-repo"
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--path",
            custom_path,
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify repository was cloned to custom path (REAL git operation)
    repo_path = proj_dir / custom_path
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), "Not a git repository"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 1

    repo_entry = repos[0]
    assert repo_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo_entry["branch"] == "main"  # Defaults to current meta branch (main)
    assert repo_entry["path"] == custom_path


@pytest.mark.integration
def test_add_multiple_repos_with_indices(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test adding multiple repositories and verify tracking order - REAL CLONES.

    Tests adding multiple repositories in sequence and verifies:
    - All repositories are tracked in pyproject.toml
    - Repositories maintain correct order (indices)
    - Each repo entry is independent and complete
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Add first repository with explicit --branch main (REAL CLONE)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Add second repository with explicit --branch main (REAL CLONE)
    # This will clone the same repo but we'll use --path to differentiate
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "main",
            "--path",
            "repos/qen-test-second",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Verify both repositories were cloned (REAL git operations)
    repo1_path = proj_dir / "repos" / "main" / "qen-test"
    repo2_path = proj_dir / "repos" / "qen-test-second"

    assert repo1_path.exists(), f"First repo not cloned to {repo1_path}"
    assert (repo1_path / ".git").exists(), "First repo not a git repository"

    assert repo2_path.exists(), f"Second repo not cloned to {repo2_path}"
    assert (repo2_path / ".git").exists(), "Second repo not a git repository"

    # Verify pyproject.toml has both entries in correct order
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"]["repos"]
    assert len(repos) == 2, f"Expected 2 repos, got {len(repos)}"

    # Verify first entry (index 1 in user-facing output)
    repo1_entry = repos[0]
    assert repo1_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo1_entry["branch"] == "main"
    assert repo1_entry["path"] == "repos/main/qen-test"

    # Verify second entry (index 2 in user-facing output)
    repo2_entry = repos[1]
    assert repo2_entry["url"] == "https://github.com/data-yaml/qen-test"
    assert repo2_entry["branch"] == "main"
    assert repo2_entry["path"] == "repos/qen-test-second"


@pytest.mark.integration
def test_add_invalid_url_error_handling(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test error handling for invalid repository URL - NO CLONE.

    Tests that qen add properly handles invalid URLs and provides
    clear error messages without attempting to clone.
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Attempt to add repository with invalid URL format
    result = run_qen(
        ["add", "not-a-valid-url", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=meta_repo,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0
    assert "Error" in result.stderr or "Error" in result.stdout


@pytest.mark.integration
def test_add_nonexistent_repo_error_handling(
    tmp_path: Path,
    temp_config_dir: Path,
) -> None:
    """Test error handling for non-existent GitHub repository - REAL CLONE ATTEMPT.

    Tests that qen add properly handles clone failures when the repository
    doesn't exist on GitHub.
    """
    # Create temporary meta repo
    meta_repo = tmp_path / "meta"
    meta_repo.mkdir()

    # Initialize meta repo with git
    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    meta_toml = meta_repo / "meta.toml"
    meta_toml.write_text('[meta]\nname = "test-org"\n')
    subprocess.run(["git", "add", "meta.toml"], cwd=meta_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Add remote to simulate real meta repo (required for org extraction)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/data-yaml/meta.git"],
        cwd=meta_repo,
        check=True,
        capture_output=True,
    )

    # Initialize qen global config (REAL command - must run from meta repo)
    result = run_qen(
        ["init"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Create a project (REAL command)
    result = run_qen(
        ["init", "test-project", "--yes"],
        temp_config_dir,
        cwd=meta_repo,
        check=True,
    )
    assert result.returncode == 0

    # Find the project directory
    proj_dir = None
    for item in (meta_repo / "proj").iterdir():
        if item.is_dir() and "test-project" in item.name:
            proj_dir = item
            break
    assert proj_dir is not None, "Project directory not created"

    # Attempt to add non-existent repository (REAL CLONE - will fail)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/this-repo-does-not-exist-qen-test-12345",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=meta_repo,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0
    assert "Error" in result.stderr or "Error" in result.stdout

    # Verify no partial state was created
    repo_path = proj_dir / "repos" / "this-repo-does-not-exist-qen-test-12345"
    assert not repo_path.exists(), "Failed clone should not leave directory"

    # Verify pyproject.toml was not updated
    pyproject_path = proj_dir / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    repos = pyproject["tool"]["qen"].get("repos", [])
    assert len(repos) == 0, "Failed add should not create pyproject.toml entry"
