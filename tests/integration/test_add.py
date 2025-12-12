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
from pathlib import Path

import pytest

from qen.pyproject_utils import load_repos_from_pyproject
from tests.conftest import run_qen


@pytest.mark.integration
@pytest.mark.parametrize(
    "url_format,url_input,expected_norm_url",
    [
        ("https", "https://github.com/data-yaml/qen-test", "https://github.com/data-yaml/qen-test"),
        ("ssh", "git@github.com:data-yaml/qen-test.git", "https://github.com/data-yaml/qen-test"),
        ("short", "data-yaml/qen-test", "https://github.com/data-yaml/qen-test"),
    ],
)
def test_add_with_various_url_formats(
    url_format: str,
    url_input: str,
    expected_norm_url: str,
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with various URL formats - REAL CLONE.

    Tests adding a repository with different URL format variations:
    - Full HTTPS URL: https://github.com/data-yaml/qen-test
    - SSH URL: git@github.com:data-yaml/qen-test.git
    - Short format: data-yaml/qen-test

    Verifies:
    - Real git clone succeeds
    - Repository is cloned to repos/ directory
    - pyproject.toml is updated with correct [[tool.qen.repos]] entry
    - URL is normalized to HTTPS format
    - Entry has url, branch, and path fields

    Args:
        url_format: Format type being tested (https, ssh, short)
        url_input: The actual URL string to pass to qen add
        expected_norm_url: Expected normalized HTTPS URL in pyproject.toml
        qen_project: Test project fixture
        temp_config_dir: Isolated config directory
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Add repository with specified URL format and explicit --branch main (REAL CLONE)
    result = run_qen(
        [
            "add",
            url_input,
            "--branch",
            "main",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen add failed for {url_format} format: {result.stderr}"

    # Verify repository was cloned (REAL git operation)
    # With --branch main, path is repos/main/qen-test
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path} for {url_format} format"
    assert (repo_path / ".git").exists(), (
        f"Not a git repository for {url_format} format: {repo_path}"
    )

    # Only verify README for https format (first test), to avoid redundant checks
    if url_format == "https":
        assert (repo_path / "README.md").exists(), (
            f"README.md not found in cloned repo: {repo_path}"
        )

    # Verify pyproject.toml was updated with correct TOML format
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    # Use pyproject_utils to load repos (consistent with production code)
    repos = load_repos_from_pyproject(proj_dir)
    assert len(repos) == 1, f"Expected 1 repo for {url_format} format, got {len(repos)}"

    # Verify repo entry fields
    repo = repos[0]
    assert repo.url == expected_norm_url, (
        f"Expected URL '{expected_norm_url}' for {url_format} format, got '{repo.url}'"
    )
    assert repo.branch == "main", (
        f"Expected branch 'main' for {url_format} format, got '{repo.branch}'"
    )
    assert repo.path == "repos/main/qen-test", (
        f"Expected path 'repos/main/qen-test' for {url_format} format, got '{repo.path}'"
    )


@pytest.mark.integration
def test_add_with_custom_branch(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom branch name - REAL CLONE.

    Tests adding a repository with a custom branch using --branch flag.

    Verifies:
    - Repository is cloned and checked out to custom branch
    - pyproject.toml records the correct branch name
    """
    meta_prime, per_project_meta, proj_dir = qen_project

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
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen add with custom branch failed: {result.stderr}"

    # Verify repository was cloned with explicit branch (REAL git operation)
    # With explicit --branch, path is repos/<branch>/<repo-name>
    repo_path = proj_dir / "repos" / "main" / "qen-test"
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), f"Not a git repository: {repo_path}"

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
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    # Use pyproject_utils to load repos (consistent with production code)
    repos = load_repos_from_pyproject(proj_dir)
    assert len(repos) == 1, f"Expected 1 repo, got {len(repos)}"

    repo = repos[0]
    assert repo.url == "https://github.com/data-yaml/qen-test", (
        f"Expected url 'https://github.com/data-yaml/qen-test', got '{repo.url}'"
    )
    assert repo.branch == "main", f"Expected branch 'main', got '{repo.branch}'"
    assert repo.path == "repos/main/qen-test", (
        f"Expected path 'repos/main/qen-test', got '{repo.path}'"
    )


@pytest.mark.integration
def test_add_with_custom_path(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test qen add with custom local path - REAL CLONE.

    Tests adding a repository with a custom local path using --path flag.

    Verifies:
    - Repository is cloned to custom path
    - pyproject.toml records the custom path
    """
    meta_prime, per_project_meta, proj_dir = qen_project

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
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen add with custom path failed: {result.stderr}"

    # Verify repository was cloned to custom path (REAL git operation)
    repo_path = proj_dir / custom_path
    assert repo_path.exists(), f"Repository not cloned to {repo_path}"
    assert (repo_path / ".git").exists(), f"Not a git repository: {repo_path}"

    # Verify pyproject.toml entry
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    # Use pyproject_utils to load repos (consistent with production code)
    repos = load_repos_from_pyproject(proj_dir)
    assert len(repos) == 1, f"Expected 1 repo, got {len(repos)}"

    repo = repos[0]
    assert repo.url == "https://github.com/data-yaml/qen-test", (
        f"Expected url 'https://github.com/data-yaml/qen-test', got '{repo.url}'"
    )
    assert repo.branch == "main", f"Expected branch 'main', got '{repo.branch}'"
    assert repo.path == custom_path, f"Expected custom path '{custom_path}', got '{repo.path}'"


@pytest.mark.integration
def test_add_multiple_repos_with_indices(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test adding multiple repositories and verify tracking order - REAL CLONES.

    Tests adding multiple repositories in sequence and verifies:
    - All repositories are tracked in pyproject.toml
    - Repositories maintain correct order (indices)
    - Each repo entry is independent and complete
    """
    meta_prime, per_project_meta, proj_dir = qen_project

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
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen add first repo failed: {result.stderr}"

    # Add second repository with different branch (REAL CLONE)
    # Using different branch to test multi-repo tracking with indices
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/qen-test",
            "--branch",
            "ref-passing-checks",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
    )
    assert result.returncode == 0, f"qen add second repo failed: {result.stderr}"

    # Verify both repositories were cloned (REAL git operations)
    repo1_path = proj_dir / "repos" / "main" / "qen-test"
    repo2_path = proj_dir / "repos" / "ref-passing-checks" / "qen-test"

    assert repo1_path.exists(), f"First repo not cloned to {repo1_path}"
    assert (repo1_path / ".git").exists(), f"First repo not a git repository: {repo1_path}"

    assert repo2_path.exists(), f"Second repo not cloned to {repo2_path}"
    assert (repo2_path / ".git").exists(), f"Second repo not a git repository: {repo2_path}"

    # Verify pyproject.toml has both entries in correct order
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    # Use pyproject_utils to load repos (consistent with production code)
    repos = load_repos_from_pyproject(proj_dir)
    assert len(repos) == 2, f"Expected 2 repos, got {len(repos)}"

    # Verify first entry (index 1 in user-facing output)
    repo1 = repos[0]
    assert repo1.url == "https://github.com/data-yaml/qen-test", (
        f"Expected first repo url 'https://github.com/data-yaml/qen-test', got '{repo1.url}'"
    )
    assert repo1.branch == "main", f"Expected first repo branch 'main', got '{repo1.branch}'"
    assert repo1.path == "repos/main/qen-test", (
        f"Expected first repo path 'repos/main/qen-test', got '{repo1.path}'"
    )

    # Verify second entry (index 2 in user-facing output)
    repo2 = repos[1]
    assert repo2.url == "https://github.com/data-yaml/qen-test", (
        f"Expected second repo url 'https://github.com/data-yaml/qen-test', got '{repo2.url}'"
    )
    assert repo2.branch == "ref-passing-checks", (
        f"Expected second repo branch 'ref-passing-checks', got '{repo2.branch}'"
    )
    assert repo2.path == "repos/ref-passing-checks/qen-test", (
        f"Expected second repo path 'repos/ref-passing-checks/qen-test', got '{repo2.path}'"
    )


@pytest.mark.integration
def test_add_invalid_url_error_handling(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling for invalid repository URL - NO CLONE.

    Tests that qen add properly handles invalid URLs and provides
    clear error messages without attempting to clone.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Attempt to add repository with invalid URL format
    result = run_qen(
        ["add", "not-a-valid-url", "--yes", "--no-workspace"],
        temp_config_dir,
        cwd=per_project_meta,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0, (
        f"Expected error for invalid URL, but command succeeded. Output: {result.stdout}"
    )
    assert "Error" in result.stderr or "Error" in result.stdout, (
        f"Expected 'Error' in output for invalid URL. Stderr: {result.stderr}, Stdout: {result.stdout}"
    )


@pytest.mark.integration
def test_add_nonexistent_repo_error_handling(
    qen_project: tuple[Path, Path, Path],
    temp_config_dir: Path,
) -> None:
    """Test error handling for non-existent GitHub repository - REAL CLONE ATTEMPT.

    Tests that qen add properly handles clone failures when the repository
    doesn't exist on GitHub.
    """
    meta_prime, per_project_meta, proj_dir = qen_project

    # Attempt to add non-existent repository (REAL CLONE - will fail)
    result = run_qen(
        [
            "add",
            "https://github.com/data-yaml/this-repo-does-not-exist-qen-test-12345",
            "--yes",
            "--no-workspace",
        ],
        temp_config_dir,
        cwd=per_project_meta,
        check=False,  # Expect failure
    )

    # Verify command failed with error
    assert result.returncode != 0, (
        f"Expected error for non-existent repo, but command succeeded. Output: {result.stdout}"
    )
    assert "Error" in result.stderr or "Error" in result.stdout, (
        f"Expected 'Error' in output for non-existent repo. Stderr: {result.stderr}, Stdout: {result.stdout}"
    )

    # Verify no partial state was created
    repo_path = proj_dir / "repos" / "this-repo-does-not-exist-qen-test-12345"
    assert not repo_path.exists(), f"Failed clone should not leave directory at {repo_path}"

    # Verify pyproject.toml was not updated
    pyproject_path = proj_dir / "pyproject.toml"
    assert pyproject_path.exists(), f"pyproject.toml not found at {pyproject_path}"

    # Use pyproject_utils to load repos (consistent with production code)
    repos = load_repos_from_pyproject(proj_dir)
    assert len(repos) == 0, (
        f"Failed add should not create pyproject.toml entry, but found {len(repos)} repos"
    )
