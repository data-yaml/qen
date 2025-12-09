"""Integration tests that verify our schema matches GitHub's actual API responses.

CRITICAL: These tests use REAL GitHub API calls to validate our TypedDict schemas
match reality. If these fail, it means GitHub changed their API and we need to
update our schemas.

These tests validate the CONTRACT between our code and GitHub's API - they should
NEVER be mocked.
"""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
def test_github_checkrun_schema_matches_reality(real_test_repo: Path) -> None:
    """Verify our CheckRun schema matches actual GitHub API response.

    Uses standard PR from data-yaml/qen-test to validate schema.
    If this test fails, GitHub changed their API format.
    """
    # Use standard passing PR (always exists)
    pr_url = "https://github.com/data-yaml/qen-test/pull/1"

    result = subprocess.run(
        ["gh", "pr", "view", pr_url, "--json", "statusCheckRollup"],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    data = json.loads(result.stdout)
    checks = data.get("statusCheckRollup", [])

    assert len(checks) > 0, "Test PR should have checks"

    # Verify EVERY field in our CheckRun schema exists in real response
    real_check = checks[0]

    # Required fields from our schema
    assert "__typename" in real_check, "Missing __typename field"
    assert real_check["__typename"] == "CheckRun", (
        f"Expected CheckRun, got {real_check['__typename']}"
    )

    assert "status" in real_check, "Missing status field"
    assert real_check["status"] in [
        "COMPLETED",
        "IN_PROGRESS",
        "QUEUED",
        "WAITING",
        "PENDING",
    ], f"Unknown status: {real_check['status']}"

    # conclusion only present when COMPLETED
    if real_check["status"] == "COMPLETED":
        assert "conclusion" in real_check, "Missing conclusion field for COMPLETED check"
        assert real_check["conclusion"] in [
            "SUCCESS",
            "FAILURE",
            "NEUTRAL",
            "CANCELLED",
            "SKIPPED",
            "TIMED_OUT",
            "ACTION_REQUIRED",
        ], f"Unknown conclusion: {real_check['conclusion']}"

    # Other fields our schema expects
    assert "name" in real_check, "Missing name field"
    assert "detailsUrl" in real_check, "Missing detailsUrl field"
    assert "startedAt" in real_check, "Missing startedAt field"
    assert "completedAt" in real_check, "Missing completedAt field"
    assert "workflowName" in real_check, "Missing workflowName field"

    print("✓ CheckRun schema validated against real GitHub API")
    print(f"  Fields present: {', '.join(real_check.keys())}")


@pytest.mark.integration
def test_github_pr_schema_matches_reality(real_test_repo: Path) -> None:
    """Verify our PrData schema matches actual GitHub API response.

    Validates all fields we depend on are present in real GitHub responses.
    """
    pr_url = "https://github.com/data-yaml/qen-test/pull/1"

    result = subprocess.run(
        [
            "gh",
            "pr",
            "view",
            pr_url,
            "--json",
            "number,title,state,baseRefName,url,statusCheckRollup,mergeable,author,createdAt,updatedAt",
        ],
        cwd=real_test_repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )

    data = json.loads(result.stdout)

    # Verify all PrData fields exist
    assert "number" in data
    assert "title" in data
    assert "state" in data
    assert data["state"] in ["OPEN", "CLOSED", "MERGED"]
    assert "baseRefName" in data
    assert "url" in data
    assert "statusCheckRollup" in data
    assert isinstance(data["statusCheckRollup"], list)
    assert "mergeable" in data
    assert data["mergeable"] in ["MERGEABLE", "CONFLICTING", "UNKNOWN"]
    assert "author" in data
    assert "login" in data["author"]
    assert "createdAt" in data
    assert "updatedAt" in data

    print("✓ PrData schema validated against real GitHub API")
    print(f"  Fields present: {', '.join(data.keys())}")
