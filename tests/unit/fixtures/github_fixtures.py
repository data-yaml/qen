"""Pytest fixtures for GitHub API response objects.

These fixtures provide properly-typed CheckRun and PR data objects that match
the actual GitHub API schema, preventing test mocks from diverging from reality.
"""

import pytest

from tests.unit.schemas.github_pr import CheckRun


@pytest.fixture
def check_run_passing() -> CheckRun:
    """Create a passing CheckRun matching GitHub API schema."""
    return {
        "__typename": "CheckRun",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
        "name": "test-check",
        "detailsUrl": "https://github.com/test/repo/runs/123",
        "startedAt": "2025-01-01T10:00:00Z",
        "completedAt": "2025-01-01T10:05:00Z",
        "workflowName": "CI",
    }


@pytest.fixture
def check_run_failing() -> CheckRun:
    """Create a failing CheckRun matching GitHub API schema."""
    return {
        "__typename": "CheckRun",
        "status": "COMPLETED",
        "conclusion": "FAILURE",
        "name": "test-check",
        "detailsUrl": "https://github.com/test/repo/runs/124",
        "startedAt": "2025-01-01T10:00:00Z",
        "completedAt": "2025-01-01T10:05:00Z",
        "workflowName": "CI",
    }


@pytest.fixture
def check_run_pending() -> CheckRun:
    """Create a pending CheckRun matching GitHub API schema."""
    return {
        "__typename": "CheckRun",
        "status": "IN_PROGRESS",
        "name": "test-check",
        "detailsUrl": "https://github.com/test/repo/runs/125",
        "startedAt": "2025-01-01T10:00:00Z",
        "completedAt": "",
        "workflowName": "CI",
    }


@pytest.fixture
def check_run_skipped() -> CheckRun:
    """Create a skipped CheckRun matching GitHub API schema."""
    return {
        "__typename": "CheckRun",
        "status": "COMPLETED",
        "conclusion": "SKIPPED",
        "name": "test-check",
        "detailsUrl": "https://github.com/test/repo/runs/126",
        "startedAt": "2025-01-01T10:00:00Z",
        "completedAt": "2025-01-01T10:05:00Z",
        "workflowName": "CI",
    }
