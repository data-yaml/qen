#!/usr/bin/env python3
"""Integration test runner that auto-detects GitHub token and fails hard if missing.

This script automatically detects a GitHub token from:
1. GITHUB_TOKEN environment variable (if already set)
2. gh CLI (via `gh auth token`)

If no token is found, the script exits with error code 1 to prevent
silent test skipping. This ensures 100% test pass rate with no skipped tests.
"""

import os
import subprocess
import sys


def main() -> int:
    """Run integration tests with auto-detected GitHub token."""
    # Check if GITHUB_TOKEN is already set
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        # Try to get token from gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=True,
            )
            token = result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "Error: No GitHub token found. Integration tests REQUIRE a token.",
                file=sys.stderr,
            )
            print(
                "To fix: Run 'gh auth login' or set GITHUB_TOKEN environment variable",
                file=sys.stderr,
            )
            return 1

    # Set token in environment
    os.environ["GITHUB_TOKEN"] = token

    # Build pytest command with all args passed through
    pytest_args = ["pytest", "tests/", "-m", "integration", "-v"] + sys.argv[1:]

    # Run pytest (use execvp to replace current process)
    os.execvp("pytest", pytest_args)


if __name__ == "__main__":
    sys.exit(main())
