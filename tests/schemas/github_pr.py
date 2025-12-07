"""GitHub API response schemas for pull request and check run data.

This module defines TypedDict schemas that match GitHub's API response format,
ensuring type safety and contract validation for GitHub PR and check run data.
"""

from typing import Literal, NotRequired, TypedDict


class CheckRun(TypedDict):
    """GitHub CheckRun schema from statusCheckRollup.

    Represents a single GitHub check run within a pull request's status checks.
    Note: conclusion is only present when status is COMPLETED.
    """

    __typename: str
    status: Literal["COMPLETED", "IN_PROGRESS", "QUEUED", "WAITING", "PENDING"]
    conclusion: NotRequired[
        Literal[
            "SUCCESS",
            "FAILURE",
            "NEUTRAL",
            "CANCELLED",
            "SKIPPED",
            "TIMED_OUT",
            "ACTION_REQUIRED",
            "",
        ]
    ]
    name: str
    detailsUrl: str
    startedAt: str
    completedAt: str
    workflowName: str


class Author(TypedDict):
    """GitHub PR author information."""

    login: str
    avatarUrl: NotRequired[str | None]
    url: NotRequired[str | None]


class PrData(TypedDict):
    """GitHub PR schema from gh pr view --json.

    Represents the comprehensive data for a GitHub pull request, matching
    the exact schema returned by the GitHub CLI when using the --json flag.
    """

    number: int
    title: str
    state: Literal["OPEN", "CLOSED", "MERGED"]
    baseRefName: str
    url: str
    statusCheckRollup: list[CheckRun]
    mergeable: Literal["MERGEABLE", "CONFLICTING", "UNKNOWN"]
    author: Author
    createdAt: str
    updatedAt: str
