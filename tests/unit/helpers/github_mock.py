"""GitHub API Mock Data Generation for Testing."""

from datetime import datetime, timedelta
from typing import Any, Literal, Unpack

from tests.unit.schemas.github_pr import CheckRun, PrData


def create_check_run_mock(
    name: str = "test-check",
    status: Literal["COMPLETED", "IN_PROGRESS", "QUEUED", "WAITING", "PENDING"] = "COMPLETED",
    conclusion: Literal[
        "SUCCESS", "FAILURE", "NEUTRAL", "CANCELLED", "SKIPPED", "TIMED_OUT", "ACTION_REQUIRED", ""
    ] = "SUCCESS",
    **overrides: Any,
) -> CheckRun:
    """Create an individual check run mock with default or overridden values."""
    now = datetime.now().isoformat() + "Z"
    default_check: CheckRun = {
        "__typename": "CheckRun",
        "status": status,
        "conclusion": conclusion,
        "name": name,
        "detailsUrl": f"https://github.com/test-org/test-repo/actions/runs/{hash(name)}",
        "startedAt": now,
        "completedAt": now,
        "workflowName": f"{name}-workflow",
    }

    return {**default_check, **overrides}


def create_passing_checks_mock(num_checks: int = 1) -> list[CheckRun]:
    """Generate a list of passing check runs."""
    return [
        create_check_run_mock(name=f"passing-check-{i}", status="COMPLETED", conclusion="SUCCESS")
        for i in range(num_checks)
    ]


def create_failing_checks_mock(num_checks: int = 1) -> list[CheckRun]:
    """Generate a list of failing check runs."""
    return [
        create_check_run_mock(name=f"failing-check-{i}", status="COMPLETED", conclusion="FAILURE")
        for i in range(num_checks)
    ]


def create_mixed_checks_mock() -> list[CheckRun]:
    """Generate a mix of check states."""
    return [
        create_check_run_mock(name="passing-check", status="COMPLETED", conclusion="SUCCESS"),
        create_check_run_mock(name="in-progress-check", status="IN_PROGRESS"),
        create_check_run_mock(name="failed-check", status="COMPLETED", conclusion="FAILURE"),
        create_check_run_mock(name="skipped-check", status="COMPLETED", conclusion="SKIPPED"),
    ]


def create_pr_mock_data(**overrides: Unpack[dict[str, Any]]) -> PrData:
    """Create mock PR data that matches GitHub schema.

    Ensures unit tests use realistic and validatable mock data.

    Args:
        **overrides: Optional overrides to default PR data values.

    Returns:
        A PrData dictionary matching the GitHub API schema.
    """
    now = datetime.now()

    default_data: PrData = {
        "number": 123,
        "title": "Test PR",
        "state": "OPEN",
        "baseRefName": "main",
        "url": "https://github.com/org/repo/pull/123",
        "statusCheckRollup": create_passing_checks_mock(),
        "mergeable": "MERGEABLE",
        "author": {"login": "testuser"},
        "createdAt": now.isoformat() + "Z",
        "updatedAt": (now + timedelta(minutes=5)).isoformat() + "Z",
    }

    # Validate against schema by simple dictionary merge
    return {**default_data, **overrides}  # type: ignore
