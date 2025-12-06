#!/usr/bin/env python3
"""Version management script for pyproject.toml."""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_version() -> str:
    """Get the current version from pyproject.toml.

    Returns:
        Current version string

    Raises:
        SystemExit: If pyproject.toml not found or version not found
    """
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)

    content = pyproject_path.read_text()

    # Find current version
    version_match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not version_match:
        print("Error: Could not find version in pyproject.toml", file=sys.stderr)
        sys.exit(1)

    return version_match.group(1)


def bump_version(version: str, part: str) -> str:
    """Bump the version number based on semver rules.

    Args:
        version: Current version string (e.g., "0.1.1")
        part: Which part to bump ("major", "minor", or "patch")

    Returns:
        New version string
    """
    major, minor, patch = map(int, version.split("."))

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid part: {part}. Must be 'major', 'minor', or 'patch'")


def set_version(new_version: str) -> None:
    """Set the version in pyproject.toml.

    Args:
        new_version: New version string to set
    """
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()

    # Replace version in file
    new_content = re.sub(
        r'^version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    pyproject_path.write_text(new_content)


def main(bump: str | None = None, tag: bool = False, dev: bool = False) -> None:
    """Main entry point for version management.

    Args:
        bump: Optional version part to bump ("major", "minor", or "patch").
              If provided, bumps version and commits (does NOT push).
        tag: If True, create release tag for current version and push everything.
        dev: If True, create dev tag for current version and push everything.
    """
    current_version = get_version()

    # Handle bump (separate from tagging/releasing)
    if bump is not None:
        if bump not in ("major", "minor", "patch"):
            print(
                f"Error: Invalid bump type '{bump}'. Must be 'major', 'minor', or 'patch'",
                file=sys.stderr,
            )
            sys.exit(1)

        new_version = bump_version(current_version, bump)
        set_version(new_version)
        print(f"{current_version} -> {new_version}")

        # Update uv.lock
        print("Updating uv.lock...")
        try:
            subprocess.run(["uv", "lock"], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error updating uv.lock: {e.stderr.decode()}", file=sys.stderr)
            sys.exit(1)

        # Commit the changes (but don't push)
        print("Committing version bump...")
        try:
            subprocess.run(
                ["git", "add", "pyproject.toml", "uv.lock"], check=True, capture_output=True
            )
            commit_msg = f"chore: bump version to {new_version}"
            subprocess.run(["git", "commit", "-m", commit_msg], check=True, capture_output=True)
            print(f"Committed: {commit_msg}")
            print("(Not pushed - use --tag or --dev to create a release)")
        except subprocess.CalledProcessError as e:
            print(f"Error committing changes: {e.stderr.decode()}", file=sys.stderr)
            sys.exit(1)
        return

    # Handle release tagging (separate from bumping)
    if tag or dev:
        if dev:
            # Add timestamp for dev tags: v0.1.2.dev20241205162345 (PEP 440)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            tag_suffix = f".dev{timestamp}"
        else:
            tag_suffix = ""
        tag_name = f"v{current_version}{tag_suffix}"
        tag_msg = f"Development release {tag_name}" if dev else f"Release {tag_name}"

        print(f"Creating tag {tag_name} for current version {current_version}...")
        try:
            # Create tag
            subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", tag_msg], check=True, capture_output=True
            )

            # Push commits first
            print("Pushing commits...")
            subprocess.run(["git", "push"], check=True, capture_output=True)

            # Push tag
            print(f"Pushing tag {tag_name}...")
            subprocess.run(["git", "push", "origin", tag_name], check=True, capture_output=True)
            print(f"Released: {tag_name}")
        except subprocess.CalledProcessError as e:
            print(f"Error creating/pushing release: {e.stderr.decode()}", file=sys.stderr)
            sys.exit(1)
        return

    # Default: just show current version
    print(current_version)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bump version in pyproject.toml")
    parser.add_argument(
        "part",
        nargs="?",
        default="patch",
        choices=["major", "minor", "patch"],
        help="Version part to bump (default: patch)",
    )

    args = parser.parse_args()
    main(args.part)
