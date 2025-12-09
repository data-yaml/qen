#!/usr/bin/env python3
"""Ensure standard reference PRs exist in data-yaml/qen-test for integration tests.

This script verifies that standard reference PRs (defined in tests/integration/constants.py)
exist and are open. If they don't exist or are closed, it recreates them.

The standard PRs are:
- PR #7: ref-passing-checks → main (always passes)
- PR #8: ref-failing-checks → main (always fails)
- PR #9: ref-issue-456-test → main (has issue pattern)
- PR #10-12: ref-stack-a → ref-stack-b → ref-stack-c (stacked PRs)

This script should be run before integration tests to ensure test environment is ready.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Constants from tests/integration/constants.py
STANDARD_PRS = {
    "passing": 7,
    "failing": 8,
    "issue": 9,
    "stack": [10, 11, 12],
}

STANDARD_BRANCHES = {
    "passing": "ref-passing-checks",
    "failing": "ref-failing-checks",
    "issue": "ref-issue-456-test",
    "stack_a": "ref-stack-a",
    "stack_b": "ref-stack-b",
    "stack_c": "ref-stack-c",
}

REPO = "data-yaml/qen-test"
TEST_REPO_URL = f"https://github.com/{REPO}"


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
    )


def check_gh_cli() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = run_cmd(["gh", "auth", "status"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def pr_exists_and_open(pr_number: int) -> bool:
    """Check if a PR exists and is open."""
    result = run_cmd(
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--repo",
            REPO,
            "--json",
            "number,state",
        ],
        check=False,
    )

    if result.returncode != 0:
        return False

    try:
        pr_data = json.loads(result.stdout)
        return pr_data.get("state") == "OPEN"
    except json.JSONDecodeError:
        return False


def branch_exists_remote(branch: str) -> bool:
    """Check if a branch exists on remote."""
    result = run_cmd(
        [
            "gh",
            "api",
            f"/repos/{REPO}/branches/{branch}",
        ],
        check=False,
    )
    return result.returncode == 0


def create_or_update_branch(branch: str, base: str = "main") -> None:
    """Create or update a reference branch on remote.

    Args:
        branch: Branch name to create/update
        base: Base branch to branch from (default: main)
    """
    print(f"  Creating/updating branch {branch} from {base}...")

    # Get base branch SHA
    result = run_cmd(
        [
            "gh",
            "api",
            f"/repos/{REPO}/git/refs/heads/{base}",
        ]
    )
    base_data = json.loads(result.stdout)
    base_sha = base_data["object"]["sha"]

    # Try to update existing branch
    result = run_cmd(
        [
            "gh",
            "api",
            "--method",
            "PATCH",
            f"/repos/{REPO}/git/refs/heads/{branch}",
            "-f",
            f"sha={base_sha}",
            "-F",
            "force=true",
        ],
        check=False,
    )

    if result.returncode != 0:
        # Branch doesn't exist, create it
        run_cmd(
            [
                "gh",
                "api",
                "--method",
                "POST",
                f"/repos/{REPO}/git/refs",
                "-f",
                f"ref=refs/heads/{branch}",
                "-f",
                f"sha={base_sha}",
            ]
        )

    # Add a commit to make branch unique (required for PRs)
    # First get the current tree
    result = run_cmd(
        [
            "gh",
            "api",
            f"/repos/{REPO}/git/commits/{base_sha}",
        ]
    )
    commit_data = json.loads(result.stdout)
    tree_sha = commit_data["tree"]["sha"]

    # Create a new commit
    commit_message = f"Test commit for {branch}"
    result = run_cmd(
        [
            "gh",
            "api",
            "--method",
            "POST",
            f"/repos/{REPO}/git/commits",
            "-f",
            f"message={commit_message}",
            "-f",
            f"tree={tree_sha}",
            "-f",
            f"parents[]={base_sha}",
        ]
    )
    new_commit = json.loads(result.stdout)
    new_sha = new_commit["sha"]

    # Update branch to point to new commit
    run_cmd(
        [
            "gh",
            "api",
            "--method",
            "PATCH",
            f"/repos/{REPO}/git/refs/heads/{branch}",
            "-f",
            f"sha={new_sha}",
        ]
    )

    print(f"  ✓ Branch {branch} ready at {new_sha[:7]}")


def create_pr_if_needed(pr_number: int, head: str, base: str, title: str) -> None:
    """Create a PR if it doesn't exist or is closed.

    Args:
        pr_number: Expected PR number (for display only)
        head: Head branch name
        base: Base branch name
        title: PR title
    """
    # First ensure branch exists
    if not branch_exists_remote(head):
        create_or_update_branch(head, base)

    # Check if PR exists and is open
    if pr_exists_and_open(pr_number):
        print(f"  ✓ PR #{pr_number} exists and is open")
        return

    # Check if there's an existing PR for this head branch (might be closed)
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            REPO,
            "--head",
            head,
            "--base",
            base,
            "--state",
            "all",
            "--json",
            "number,state",
        ]
    )

    existing_prs = json.loads(result.stdout)

    if existing_prs:
        # Found existing PR(s)
        existing_pr = existing_prs[0]
        pr_num = existing_pr["number"]
        state = existing_pr["state"]

        if state == "CLOSED":
            print(f"  Found closed PR #{pr_num}, reopening...")
            run_cmd(
                [
                    "gh",
                    "pr",
                    "reopen",
                    str(pr_num),
                    "--repo",
                    REPO,
                ]
            )
            print(f"  ✓ Reopened PR #{pr_num}")
        elif state == "MERGED":
            print(f"  ⚠️  PR #{pr_num} was merged, creating new branch and PR...")
            # Need to recreate branch and PR
            create_or_update_branch(head, base)
            result = run_cmd(
                [
                    "gh",
                    "pr",
                    "create",
                    "--repo",
                    REPO,
                    "--head",
                    head,
                    "--base",
                    base,
                    "--title",
                    title,
                    "--body",
                    "Standard reference PR for integration tests.\n\n**DO NOT CLOSE OR MERGE THIS PR.**\n\nThis PR is used by integration tests in qen.",
                ]
            )
            print(f"  ✓ Created new PR: {result.stdout.strip()}")
    else:
        # No existing PR, create new one
        print(f"  Creating PR for {head} → {base}...")
        result = run_cmd(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                REPO,
                "--head",
                head,
                "--base",
                base,
                "--title",
                title,
                "--body",
                "Standard reference PR for integration tests.\n\n**DO NOT CLOSE OR MERGE THIS PR.**\n\nThis PR is used by integration tests in qen.",
            ]
        )
        print(f"  ✓ Created PR: {result.stdout.strip()}")


def get_pr_number_for_branch(head: str, base: str) -> int | None:
    """Get PR number for a branch.

    Args:
        head: Head branch name
        base: Base branch name

    Returns:
        PR number if found, None otherwise
    """
    result = run_cmd(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            REPO,
            "--head",
            head,
            "--base",
            base,
            "--state",
            "open",
            "--json",
            "number",
        ],
        check=False,
    )

    if result.returncode != 0:
        return None

    try:
        prs = json.loads(result.stdout)
        if prs:
            return prs[0]["number"]
    except json.JSONDecodeError:
        pass

    return None


def update_constants_file(pr_numbers: dict[str, int | list[int]]) -> None:
    """Update tests/integration/constants.py with actual PR numbers.

    Args:
        pr_numbers: Dictionary of PR numbers by key
    """
    constants_file = Path(__file__).parent.parent / "tests" / "integration" / "constants.py"

    if not constants_file.exists():
        print(f"Warning: {constants_file} not found, skipping update")
        return

    # Read current file
    content = constants_file.read_text()

    # Update PR numbers
    passing = pr_numbers["passing"]
    failing = pr_numbers["failing"]
    issue = pr_numbers["issue"]
    stack = pr_numbers["stack"]

    # Replace STANDARD_PRS dictionary
    pattern = r"STANDARD_PRS = \{[^}]+\}"
    replacement = f"""STANDARD_PRS = {{
    "passing": {passing},  # Branch: ref-passing-checks, Base: main, Status: Open with passing checks
    "failing": {failing},  # Branch: ref-failing-checks, Base: main, Status: Open with failing checks
    "issue": {issue},  # Branch: ref-issue-456-test, Base: main, Status: Open with issue pattern
    "stack": {stack},  # Stack: ref-stack-a → ref-stack-b → ref-stack-c
}}"""

    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Write back
    constants_file.write_text(content)
    print(f"\n✓ Updated {constants_file} with PR numbers")


def ensure_standard_prs() -> bool:
    """Ensure all standard reference PRs exist and are open.

    Returns:
        True if all PRs are ready, False if there were errors
    """
    print(f"\nVerifying standard reference PRs in {REPO}...")

    pr_numbers = {}

    # Check passing checks PR
    print("\n[1/6] Checking passing checks PR...")
    create_pr_if_needed(
        STANDARD_PRS["passing"],
        STANDARD_BRANCHES["passing"],
        "main",
        "Test PR - Always Pass Checks",
    )
    pr_numbers["passing"] = get_pr_number_for_branch(STANDARD_BRANCHES["passing"], "main")

    # Check failing checks PR
    print("\n[2/6] Checking failing checks PR...")
    create_pr_if_needed(
        STANDARD_PRS["failing"],
        STANDARD_BRANCHES["failing"],
        "main",
        "Test PR - Always Fail Checks",
    )
    pr_numbers["failing"] = get_pr_number_for_branch(STANDARD_BRANCHES["failing"], "main")

    # Check issue pattern PR
    print("\n[3/6] Checking issue pattern PR...")
    create_pr_if_needed(
        STANDARD_PRS["issue"],
        STANDARD_BRANCHES["issue"],
        "main",
        "Test PR - Issue #456 Pattern",
    )
    pr_numbers["issue"] = get_pr_number_for_branch(STANDARD_BRANCHES["issue"], "main")

    # Check stacked PRs
    stack_branches = [
        STANDARD_BRANCHES["stack_a"],
        STANDARD_BRANCHES["stack_b"],
        STANDARD_BRANCHES["stack_c"],
    ]

    print("\n[4/6] Checking stack A PR...")
    create_pr_if_needed(
        STANDARD_PRS["stack"][0],
        stack_branches[0],
        "main",
        "Test PR - Stack A",
    )

    print("\n[5/6] Checking stack B PR...")
    create_pr_if_needed(
        STANDARD_PRS["stack"][1],
        stack_branches[1],
        stack_branches[0],
        "Test PR - Stack B",
    )

    print("\n[6/6] Checking stack C PR...")
    create_pr_if_needed(
        STANDARD_PRS["stack"][2],
        stack_branches[2],
        stack_branches[1],
        "Test PR - Stack C",
    )

    # Get stack PR numbers
    pr_numbers["stack"] = [
        get_pr_number_for_branch(stack_branches[0], "main"),
        get_pr_number_for_branch(stack_branches[1], stack_branches[0]),
        get_pr_number_for_branch(stack_branches[2], stack_branches[1]),
    ]

    # Update constants file with actual PR numbers
    update_constants_file(pr_numbers)

    print("\n" + "=" * 60)
    print("✓ All standard reference PRs are ready for testing")
    print("  PR numbers:")
    print(f"    Passing: #{pr_numbers['passing']}")
    print(f"    Failing: #{pr_numbers['failing']}")
    print(f"    Issue: #{pr_numbers['issue']}")
    print(
        f"    Stack: #{pr_numbers['stack'][0]}, #{pr_numbers['stack'][1]}, #{pr_numbers['stack'][2]}"
    )
    print("=" * 60)

    return True


def main() -> int:
    """Main entry point."""
    print("QEN Integration Test Setup")
    print("=" * 60)

    # Check gh CLI
    if not check_gh_cli():
        print("ERROR: gh CLI not found or not authenticated")
        print("\nPlease install and authenticate gh CLI:")
        print("  brew install gh")
        print("  gh auth login")
        return 1

    try:
        success = ensure_standard_prs()
        return 0 if success else 1
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Command failed: {e.cmd}")
        print(f"Exit code: {e.returncode}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
