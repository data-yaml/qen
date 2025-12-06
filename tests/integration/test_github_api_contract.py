"""GitHub API Contract Tests for QEN Project.

This module contains integration tests to validate the GitHub API schema
and ensure our code's assumptions match the real GitHub API responses.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Literal

import pytest
from typing_extensions import TypedDict


def has_test_repo_access() -> bool:
    """Check if the test repository is accessible via GitHub CLI."""
    result = subprocess.run(
        ["gh", "repo", "view", "quiltdata/qen-test-repo"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class CheckRun(TypedDict, total=False):
    """Represents the schema for a GitHub Check Run."""

    __typename: Literal["CheckRun"]
    status: Literal["COMPLETED", "IN_PROGRESS", "QUEUED", "WAITING", "PENDING"]
    conclusion: Literal[
        "SUCCESS", "FAILURE", "NEUTRAL", "CANCELLED", "SKIPPED", "TIMED_OUT", "ACTION_REQUIRED", ""
    ]
    name: str
    detailsUrl: str
    startedAt: str
    completedAt: str
    workflowName: str


def validate_check_run(check: dict[str, Any]) -> None:
    """Validate a single GitHub Check Run against the expected schema."""
    # Validate required fields
    required_fields = {"status", "__typename"}
    assert all(field in check for field in required_fields), (
        f"CheckRun missing required fields. Got: {check.keys()}"
    )

    # Validate status values
    valid_statuses: list[str] = ["COMPLETED", "IN_PROGRESS", "QUEUED", "WAITING", "PENDING"]
    assert check["status"] in valid_statuses, f"Invalid check status: {check['status']}"

    # Validate status-dependent fields
    if check["status"] == "COMPLETED":
        assert "conclusion" in check, "Completed check must have a conclusion"
        valid_conclusions: list[str] = [
            "SUCCESS",
            "FAILURE",
            "NEUTRAL",
            "CANCELLED",
            "SKIPPED",
            "TIMED_OUT",
            "ACTION_REQUIRED",
            "",
        ]
        assert check["conclusion"] in valid_conclusions, (
            f"Invalid check conclusion: {check.get('conclusion')}"
        )


@pytest.mark.integration
@pytest.mark.skipif(not has_test_repo_access(), reason="No access to quiltdata/qen-test-repo")
def test_pr_status_check_rollup_schema() -> None:
    """Verify statusCheckRollup matches expected schema.

    This test ensures that our parser's assumptions about GitHub API
    responses match the actual data structure from a real repository.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            "1",
            "--repo",
            "quiltdata/qen-test-repo",
            "--json",
            "statusCheckRollup",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON: {result.stdout}")

    checks = data.get("statusCheckRollup", [])

    # If checks exist, validate their schema
    for check in checks:
        validate_check_run(check)


@pytest.mark.integration
@pytest.mark.skipif(not has_test_repo_access(), reason="No access to quiltdata/qen-test-repo")
def test_github_api_schema_unchanged() -> None:
    """Alert if GitHub API schema for PRs changes.

    This test verifies that the GitHub API maintains its expected structure,
    helping prevent breaking changes in our PR status parser.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            "1",
            "--repo",
            "quiltdata/qen-test-repo",
            "--json",
            "statusCheckRollup,number,state,mergeable",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Failed to parse JSON: {result.stdout}")

    # Verify expected fields exist
    expected_fields = {"number", "state", "mergeable", "statusCheckRollup"}
    assert set(data.keys()) == expected_fields, (
        f"GitHub API schema changed! New fields: {set(data.keys()) - expected_fields}"
    )

    # Verify check rollup schema if present
    if data["statusCheckRollup"]:
        check = data["statusCheckRollup"][0]
        validate_check_run(check)
