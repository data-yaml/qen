#!/usr/bin/env python3
"""Set up a minimal test repository for integration tests.

Creates a local git repository with test PRs in various states that can be
used for integration testing without requiring access to a real GitHub repository.
"""

import json
import subprocess
import tempfile
from pathlib import Path


def run_cmd(
    cmd: list[str], cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=check,
    )


def create_test_repo(repo_path: Path) -> None:
    """Create a test git repository with branches and mock PR data.

    Args:
        repo_path: Path where the test repository should be created
    """
    print(f"Creating test repository at: {repo_path}")

    # Initialize git repo
    repo_path.mkdir(parents=True, exist_ok=True)
    run_cmd(["git", "init"], cwd=repo_path)
    run_cmd(["git", "config", "user.name", "Test User"], cwd=repo_path)
    run_cmd(["git", "config", "user.email", "test@example.com"], cwd=repo_path)

    # Create main branch with initial commit
    readme = repo_path / "README.md"
    readme.write_text("# QEN Integration Test Repository\n\nThis is a test repository.\n")
    run_cmd(["git", "add", "README.md"], cwd=repo_path)
    run_cmd(["git", "commit", "-m", "Initial commit"], cwd=repo_path)

    # Create test branches with different scenarios
    test_branches = [
        ("test/passing-checks", "Feature with passing checks"),
        ("test/failing-checks", "Feature with failing checks"),
        ("test/in-progress-checks", "Feature with in-progress checks"),
        ("test/mixed-checks", "Feature with mixed check states"),
        ("test/no-checks", "Feature with no checks"),
        ("test/merge-conflicts", "Feature with merge conflicts"),
    ]

    for branch_name, description in test_branches:
        # Create branch
        run_cmd(["git", "checkout", "-b", branch_name], cwd=repo_path)

        # Add a commit to the branch
        test_file = repo_path / f"{branch_name.replace('/', '_')}.txt"
        test_file.write_text(f"# {description}\n\nThis is a test branch.\n")
        run_cmd(["git", "add", test_file.name], cwd=repo_path)
        run_cmd(["git", "commit", "-m", f"Add {description}"], cwd=repo_path)

    # Return to main
    run_cmd(["git", "checkout", "main"], cwd=repo_path)

    # Create .gh-mock directory for mock PR data
    mock_dir = repo_path / ".gh-mock"
    mock_dir.mkdir(exist_ok=True)

    # Create mock PR data for each branch
    pr_data = {
        "test/passing-checks": {
            "number": 1,
            "title": "Test PR - All Checks Passing",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/1",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "name": "test-check",
                    "detailsUrl": "https://github.com/quiltdata/qen-test-repo/actions/runs/1",
                    "startedAt": "2025-01-01T00:00:00Z",
                    "completedAt": "2025-01-01T00:05:00Z",
                    "workflowName": "Test Workflow",
                }
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "abc123"}],
            "files": [{"path": "test_passing_checks.txt"}],
        },
        "test/failing-checks": {
            "number": 2,
            "title": "Test PR - Failing Checks",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/2",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "status": "COMPLETED",
                    "conclusion": "FAILURE",
                    "name": "failing-test",
                    "detailsUrl": "https://github.com/quiltdata/qen-test-repo/actions/runs/2",
                    "startedAt": "2025-01-01T00:00:00Z",
                    "completedAt": "2025-01-01T00:05:00Z",
                    "workflowName": "Test Workflow",
                }
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "def456"}],
            "files": [{"path": "test_failing_checks.txt"}],
        },
        "test/in-progress-checks": {
            "number": 3,
            "title": "Test PR - In Progress Checks",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/3",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "status": "IN_PROGRESS",
                    "conclusion": None,
                    "name": "slow-check",
                    "detailsUrl": "https://github.com/quiltdata/qen-test-repo/actions/runs/3",
                    "startedAt": "2025-01-01T00:00:00Z",
                    "completedAt": None,
                    "workflowName": "Test Workflow",
                }
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "ghi789"}],
            "files": [{"path": "test_in_progress_checks.txt"}],
        },
        "test/mixed-checks": {
            "number": 4,
            "title": "Test PR - Mixed Check States",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/4",
            "statusCheckRollup": [
                {
                    "__typename": "CheckRun",
                    "status": "COMPLETED",
                    "conclusion": "SUCCESS",
                    "name": "passing-check",
                    "detailsUrl": "https://github.com/quiltdata/qen-test-repo/actions/runs/4",
                    "startedAt": "2025-01-01T00:00:00Z",
                    "completedAt": "2025-01-01T00:05:00Z",
                    "workflowName": "Test Workflow",
                },
                {
                    "__typename": "CheckRun",
                    "status": "COMPLETED",
                    "conclusion": "SKIPPED",
                    "name": "skipped-check",
                    "detailsUrl": "https://github.com/quiltdata/qen-test-repo/actions/runs/5",
                    "startedAt": "2025-01-01T00:00:00Z",
                    "completedAt": "2025-01-01T00:05:00Z",
                    "workflowName": "Test Workflow",
                },
            ],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "jkl012"}],
            "files": [{"path": "test_mixed_checks.txt"}],
        },
        "test/no-checks": {
            "number": 5,
            "title": "Test PR - No Checks",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/5",
            "statusCheckRollup": [],
            "mergeable": "MERGEABLE",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "mno345"}],
            "files": [{"path": "test_no_checks.txt"}],
        },
        "test/merge-conflicts": {
            "number": 6,
            "title": "Test PR - Merge Conflicts",
            "state": "OPEN",
            "baseRefName": "main",
            "url": "https://github.com/quiltdata/qen-test-repo/pull/6",
            "statusCheckRollup": [],
            "mergeable": "CONFLICTING",
            "author": {"login": "testuser"},
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-01-01T00:00:00Z",
            "commits": [{"oid": "pqr678"}],
            "files": [{"path": "test_merge_conflicts.txt"}],
        },
    }

    # Write mock PR data to files
    for branch, data in pr_data.items():
        pr_file = mock_dir / f"{branch.replace('/', '_')}.json"
        pr_file.write_text(json.dumps(data, indent=2))

    print("✓ Test repository created successfully")
    print(f"  Location: {repo_path}")
    print(f"  Branches: {len(test_branches)}")
    print(f"  Mock PRs: {len(pr_data)}")


def main() -> None:
    """Main entry point."""
    # Create test repo in temp directory
    test_repo_path = Path(tempfile.gettempdir()) / "qen-test-repo"

    # Remove existing test repo if it exists
    if test_repo_path.exists():
        import shutil

        print(f"Removing existing test repository: {test_repo_path}")
        shutil.rmtree(test_repo_path)

    create_test_repo(test_repo_path)


if __name__ == "__main__":
    main()
