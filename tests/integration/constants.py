"""Standard reference PR constants for integration tests.

These permanent PRs exist in data-yaml/qen-test and should NEVER be closed.
They enable fast integration tests without creating new PRs every run.

To recreate these PRs if needed, run:
    python scripts/ensure_test_repo.py

Note: PR numbers are discovered dynamically from branch names, not hardcoded.
"""

# Standard reference PRs in data-yaml/qen-test
# These PRs are permanent and should remain open for integration testing
# PR numbers are discovered dynamically - use get_standard_pr_numbers() to get actual numbers
STANDARD_PRS: dict[str, int | list[int]] = {
    "passing": 215,  # Branch: ref-passing-checks, Base: main, Status: Open with passing checks
    "failing": 216,  # Branch: ref-failing-checks, Base: main, Status: Open with failing checks
    "issue": 217,  # Branch: ref-issue-456-test, Base: main, Status: Open with issue pattern
    "stack": [218, 219, 220],  # Stack: ref-stack-a → ref-stack-b → ref-stack-c
}

# Branch names for standard PRs
STANDARD_BRANCHES: dict[str, str] = {
    "passing": "ref-passing-checks",
    "failing": "ref-failing-checks",
    "issue": "ref-issue-456-test",
    "stack_a": "ref-stack-a",
    "stack_b": "ref-stack-b",
    "stack_c": "ref-stack-c",
}

# Expected check results for standard PRs
EXPECTED_CHECKS: dict[str, list[str]] = {
    "passing": ["passing", "pending"],  # Should have passing or pending checks
    "failing": ["failing", "pending", "unknown"],  # Should have failing checks (or pending/unknown)
    "issue": ["passing", "pending", "unknown"],  # Checks status doesn't matter for issue test
}
