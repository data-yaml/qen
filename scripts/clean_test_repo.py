#!/usr/bin/env python3
"""Clean up test repository created by setup_test_repo.py."""

import shutil
import tempfile
from pathlib import Path


def main() -> None:
    """Remove the test repository."""
    test_repo_path = Path(tempfile.gettempdir()) / "qen-test-repo"

    if test_repo_path.exists():
        print(f"Removing test repository: {test_repo_path}")
        shutil.rmtree(test_repo_path)
        print("✓ Test repository removed")
    else:
        print("No test repository found (already clean)")


if __name__ == "__main__":
    main()
