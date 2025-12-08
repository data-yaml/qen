#!/usr/bin/env python3
"""Integration test runner that auto-detects GitHub token.

This script automatically detects a GitHub token from:
1. GITHUB_TOKEN environment variable (if already set)
2. gh CLI (via `gh auth token`)

Then runs pytest with the integration marker and passes through all arguments.
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
                "Warning: No GitHub token found. Integration tests may fail.",
                file=sys.stderr,
            )
            print(
                "To fix: Run 'gh auth login' or set GITHUB_TOKEN environment variable",
                file=sys.stderr,
            )

    # Set token in environment if found
    if token:
        os.environ["GITHUB_TOKEN"] = token

    # Build pytest command with all args passed through
    pytest_args = ["pytest", "tests/", "-m", "integration", "-v"] + sys.argv[1:]

    # Run pytest (use execvp to replace current process)
    os.execvp("pytest", pytest_args)


if __name__ == "__main__":
    sys.exit(main())
