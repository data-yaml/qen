"""Utilities for working with GitHub Pull Requests.

This module provides shared functionality for parsing and analyzing PR data
from the GitHub API (via gh CLI).
"""


def parse_check_status(checks: list[dict]) -> str:
    """Parse GitHub check status from statusCheckRollup.

    GitHub API returns checks with 'status' and 'conclusion' fields:
    - status: IN_PROGRESS, COMPLETED, QUEUED, WAITING
    - conclusion: SUCCESS, FAILURE, NEUTRAL, CANCELLED, SKIPPED, TIMED_OUT, ACTION_REQUIRED

    Args:
        checks: List of check objects from GitHub API statusCheckRollup

    Returns:
        Overall check status: "passing", "failing", "pending", "skipped", or "unknown"

    Examples:
        >>> checks = [{"__typename": "CheckRun", "status": "COMPLETED", "conclusion": "SUCCESS"}]
        >>> parse_check_status(checks)
        'passing'

        >>> checks = [{"__typename": "CheckRun", "status": "IN_PROGRESS", "conclusion": None}]
        >>> parse_check_status(checks)
        'pending'
    """
    if not checks:
        return "unknown"

    # For completed checks, use conclusion. For in-progress checks, use status
    check_states = []
    for c in checks:
        if c.get("__typename") != "CheckRun":
            continue  # Skip non-CheckRun types

        status = c.get("status", "").upper()
        conclusion = c.get("conclusion", "").upper()

        # If completed, use conclusion. Otherwise use status
        if status == "COMPLETED" and conclusion:
            check_states.append(conclusion)
        else:
            check_states.append(status)

    if not check_states:
        return "unknown"

    # Determine overall status
    has_failure = any(
        s in ("FAILURE", "ERROR", "TIMED_OUT", "ACTION_REQUIRED") for s in check_states
    )
    has_pending = any(s in ("PENDING", "IN_PROGRESS", "QUEUED", "WAITING") for s in check_states)

    # Filter out skipped/neutral/cancelled - they don't affect status
    active_states = [
        s for s in check_states if s not in ("SKIPPED", "NEUTRAL", "CANCELLED", "STALE")
    ]

    if has_failure:
        return "failing"
    elif has_pending:
        return "pending"
    elif active_states and all(s == "SUCCESS" for s in active_states):
        return "passing"
    elif not active_states and check_states:
        # All checks are skipped/neutral/cancelled
        return "skipped"
    else:
        return "unknown"
