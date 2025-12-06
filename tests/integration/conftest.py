"""
Integration testing infrastructure for QEN project.

Provides shared fixtures and helpers for GitHub repository and PR testing.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import (
    NotRequired,
    Protocol,
    runtime_checkable,
)

import pytest
import requests
from typing_extensions import TypedDict


@runtime_checkable
class GitHubTokenProvider(Protocol):
    """Protocol for GitHub token providers."""

    def get_github_token(self) -> str | None:
        """Retrieve a GitHub token for API access."""
        ...


class PullRequestInfo(TypedDict):
    """Structured representation of a GitHub Pull Request."""

    number: int
    title: str
    body: str
    state: str
    base_branch: str
    head_branch: str
    html_url: str


class IntegrationTestConfig(TypedDict):
    """Configuration for integration testing."""

    test_repo_url: str
    test_org: NotRequired[str]
    test_repo: NotRequired[str]


def get_integration_test_config() -> IntegrationTestConfig:
    """
    Load integration test configuration from environment or default values.

    Returns:
        A configuration dictionary with test repository details.
    """
    # Prefer environment variables, fallback to default values
    return {
        "test_repo_url": os.environ.get(
            "QEN_TEST_REPO_URL", "https://github.com/qen-test-org/integration-test-repo.git"
        ),
        "test_org": os.environ.get("QEN_TEST_ORG", "qen-test-org"),
        "test_repo": os.environ.get("QEN_TEST_REPO", "integration-test-repo"),
    }


@pytest.fixture(scope="session")
def has_test_repo_access() -> bool:
    """
    Check if the test repository can be accessed.

    Returns:
        bool: True if repository is accessible, False otherwise.
    """
    config = get_integration_test_config()
    try:
        result = subprocess.run(
            ["git", "ls-remote", config["test_repo_url"]],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def test_repo_url() -> str:
    """
    Provide the URL of the dedicated test repository.

    Returns:
        str: GitHub repository URL for integration testing.
    """
    return get_integration_test_config()["test_repo_url"]


@pytest.fixture
def clone_test_repo(test_repo_url: str) -> str:
    """
    Clone the test repository to a temporary location.

    Args:
        test_repo_url: URL of the test repository.

    Returns:
        str: Path to the cloned repository.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        subprocess.run(
            ["git", "clone", test_repo_url, temp_dir], check=True, capture_output=True, text=True
        )
        yield temp_dir


@pytest.fixture(scope="session")
def gh_token(token_provider: GitHubTokenProvider | None = None) -> str | None:
    """
    Retrieve GitHub token for API access, prioritizing different sources.

    Args:
        token_provider: Optional provider with a get_github_token method.

    Returns:
        Optional GitHub token string.
    """
    # Prioritize sources in this order:
    # 1. Token provider
    # 2. Environment variable
    # 3. GitHub CLI token
    if token_provider and (provider_token := token_provider.get_github_token()):
        return provider_token

    if env_token := os.environ.get("GITHUB_TOKEN"):
        return env_token

    try:
        gh_token_result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return gh_token_result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("No GitHub token available")


def ensure_test_pr_exists(
    gh_token: str,
    repo_full_name: str,
    base_branch: str = "main",
    title: str = "Integration Test PR",
    body: str = "Automated integration test pull request",
) -> PullRequestInfo:
    """
    Ensure a test pull request exists in the specified repository.

    Args:
        gh_token: GitHub authentication token
        repo_full_name: Repository in 'owner/repo' format
        base_branch: Base branch for the PR
        title: Pull request title
        body: Pull request description

    Returns:
        Structured pull request information.
    """
    headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
    # Check for existing open PRs
    open_prs_url = f"https://api.github.com/repos/{repo_full_name}/pulls"
    open_prs_response = requests.get(
        open_prs_url, headers=headers, params={"state": "open", "base": base_branch}
    )
    open_prs_response.raise_for_status()
    open_prs = open_prs_response.json()

    if open_prs:
        return PullRequestInfo(
            number=open_prs[0]["number"],
            title=open_prs[0]["title"],
            body=open_prs[0]["body"],
            state=open_prs[0]["state"],
            base_branch=open_prs[0]["base"]["ref"],
            head_branch=open_prs[0]["head"]["ref"],
            html_url=open_prs[0]["html_url"],
        )

    # Create a new PR if no existing open PR
    head_branch = f"integration-test-{os.urandom(8).hex()}"

    # Use GitHub CLI to create PR to handle branch and commit
    subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "-R",
            repo_full_name,
            "-B",
            base_branch,
            "-H",
            head_branch,
            "-t",
            title,
            "-b",
            body,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    # Fetch the newly created PR details
    open_prs_response = requests.get(
        open_prs_url,
        headers=headers,
        params={"state": "open", "base": base_branch, "head": head_branch},
    )
    open_prs_response.raise_for_status()
    new_prs = open_prs_response.json()

    if not new_prs:
        raise RuntimeError("Failed to create test pull request")

    return PullRequestInfo(
        number=new_prs[0]["number"],
        title=new_prs[0]["title"],
        body=new_prs[0]["body"],
        state=new_prs[0]["state"],
        base_branch=new_prs[0]["base"]["ref"],
        head_branch=new_prs[0]["head"]["ref"],
        html_url=new_prs[0]["html_url"],
    )


def trigger_slow_workflow(
    gh_token: str, repo_full_name: str, workflow_name: str = "integration-test-workflow"
) -> str:
    """
    Manually trigger a GitHub workflow.

    Args:
        gh_token: GitHub authentication token
        repo_full_name: Repository in 'owner/repo' format
        workflow_name: Name of the workflow to trigger

    Returns:
        Workflow run URL.
    """
    # Use GitHub CLI for workflow dispatch
    result = subprocess.run(
        ["gh", "workflow", "run", workflow_name, "-R", repo_full_name],
        capture_output=True,
        text=True,
        check=True,
    )
    # Extract and return workflow run URL from output
    return result.stdout.strip()


def setup_pr_stack(
    gh_token: str, repo_full_name: str, base_branch: str = "main", num_prs: int = 3
) -> list[PullRequestInfo]:
    """
    Create a stack of interconnected pull requests.

    Args:
        gh_token: GitHub authentication token
        repo_full_name: Repository in 'owner/repo' format
        base_branch: Base branch for the PR stack
        num_prs: Number of PRs to create in the stack

    Returns:
        List of pull request information for each PR in the stack.
    """
    pr_stack: list[PullRequestInfo] = []
    previous_branch = base_branch

    for i in range(num_prs):
        pr = ensure_test_pr_exists(
            gh_token,
            repo_full_name,
            base_branch=previous_branch,
            title=f"Integration Test PR Stack {i + 1}",
            body=f"Part {i + 1} of integration test PR stack",
        )
        pr_stack.append(pr)
        previous_branch = pr["head_branch"]

    return pr_stack


def create_test_pr(
    gh_token: str,
    repo_full_name: str,
    base_branch: str = "main",
    head_branch: str | None = None,
    title: str | None = None,
    body: str | None = None,
) -> PullRequestInfo:
    """
    Create a test pull request with optional custom parameters.

    Args:
        gh_token: GitHub authentication token
        repo_full_name: Repository in 'owner/repo' format
        base_branch: Base branch for the PR
        head_branch: Optional custom head branch name
        title: Optional custom PR title
        body: Optional custom PR body

    Returns:
        Structured pull request information.
    """
    default_title = f"Integration Test PR {os.urandom(8).hex()}"
    default_body = "Automated integration test pull request"

    head_branch = head_branch or f"test-pr-{os.urandom(8).hex()}"
    title = title or default_title
    body = body or default_body

    return ensure_test_pr_exists(
        gh_token, repo_full_name, base_branch=base_branch, title=title, body=body
    )


def add_commit_to_pr(
    pr_info: PullRequestInfo, gh_token: str, commit_message: str = "Integration test commit"
) -> None:
    """
    Add a commit to an existing pull request's branch.

    Args:
        pr_info: Pull request information
        gh_token: GitHub authentication token
        commit_message: Commit message to use
    """
    subprocess.run(
        ["gh", "pr", "checkout", str(pr_info["number"])], check=True, capture_output=True, text=True
    )

    # Create a new file with random content
    random_filename = f"test_commit_{os.urandom(8).hex()}.txt"
    with open(random_filename, "w") as f:
        f.write(f"Random test content: {os.urandom(16).hex()}")

    subprocess.run(["git", "add", random_filename], check=True, capture_output=True, text=True)

    subprocess.run(
        ["git", "commit", "-m", commit_message], check=True, capture_output=True, text=True
    )

    subprocess.run(
        ["git", "push", "origin", pr_info["head_branch"]],
        check=True,
        capture_output=True,
        text=True,
    )


def get_pr_info(gh_token: str, repo_full_name: str, pr_number: int) -> PullRequestInfo:
    """
    Retrieve detailed information about a specific pull request.

    Args:
        gh_token: GitHub authentication token
        repo_full_name: Repository in 'owner/repo' format
        pr_number: Pull request number

    Returns:
        Structured pull request information.
    """
    headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
    pr_url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"

    response = requests.get(pr_url, headers=headers)
    response.raise_for_status()

    pr_data = response.json()
    return PullRequestInfo(
        number=pr_data["number"],
        title=pr_data["title"],
        body=pr_data["body"],
        state=pr_data["state"],
        base_branch=pr_data["base"]["ref"],
        head_branch=pr_data["head"]["ref"],
        html_url=pr_data["html_url"],
    )
