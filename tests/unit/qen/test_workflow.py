"""Unit tests for qen workflow operations.

Tests repository management workflows using in-memory storage and temp directories.
These are unit tests (not integration tests) - they use mocked fixtures.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

from qen.commands.add import add_repository
from qen.pyproject_utils import read_pyproject
from tests.unit.helpers.qenvy_test import QenvyTest


class TestRepositoryManagement:
    """Test repository management workflows."""

    def test_add_repository_to_project(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test adding a repository to a project."""
        # Setup: Add remote to meta repo
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        # Initialize qen config with in-memory storage
        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        # Create a project
        project_name = "integration-test"
        branch = "2025-12-05-integration-test"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        (project_dir / "README.md").write_text("# Integration Test\n")

        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('[tool.qen]\ncreated = "2025-12-05T10:00:00Z"\n')

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add repository using in-memory storage
        with (
            patch("qen.init_utils.ensure_initialized"),
            patch("qen.commands.add.ensure_correct_branch"),
        ):
            add_repository(
                repo=str(child_repo),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )

        # Verify: Repository was cloned (new structure: repos/{branch}/{repo})
        cloned_path = project_dir / "repos" / "main" / "child_repo"
        assert cloned_path.exists()
        assert (cloned_path / ".git").exists()

        # Verify: pyproject.toml was updated
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 1
        assert result["tool"]["qen"]["repos"][0]["url"] == str(child_repo)

    def test_add_multiple_repositories(
        self,
        meta_repo: Path,
        tmp_path: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test adding multiple repositories."""
        # Setup: Create two child repos
        child_repo1 = tmp_path / "child1"
        child_repo1.mkdir()
        subprocess.run(["git", "init"], cwd=child_repo1, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=child_repo1,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=child_repo1,
            check=True,
            capture_output=True,
        )
        (child_repo1 / "README.md").write_text("# Child 1\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=child_repo1, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"], cwd=child_repo1, check=True, capture_output=True
        )

        child_repo2 = tmp_path / "child2"
        child_repo2.mkdir()
        subprocess.run(["git", "init"], cwd=child_repo2, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=child_repo2,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=child_repo2,
            check=True,
            capture_output=True,
        )
        (child_repo2 / "README.md").write_text("# Child 2\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=child_repo2, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial"], cwd=child_repo2, check=True, capture_output=True
        )

        # Setup qen with in-memory storage
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "multi-repo-test"
        branch = "2025-12-05-multi-repo-test"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('[tool.qen]\ncreated = "2025-12-05T10:00:00Z"\n')

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add both repositories using in-memory storage
        with (
            patch("qen.init_utils.ensure_initialized"),
            patch("qen.commands.add.ensure_correct_branch"),
        ):
            add_repository(
                repo=str(child_repo1),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )
        with (
            patch("qen.init_utils.ensure_initialized"),
            patch("qen.commands.add.ensure_correct_branch"),
        ):
            add_repository(
                repo=str(child_repo2),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )

        # Verify: Both repositories were cloned (new structure: repos/{branch}/{repo})
        assert (project_dir / "repos" / "main" / "child1").exists()
        assert (project_dir / "repos" / "main" / "child2").exists()

        # Verify: pyproject.toml has both entries
        result = read_pyproject(project_dir)
        assert len(result["tool"]["qen"]["repos"]) == 2


class TestMetaTomlUpdates:
    """Test pyproject.toml update workflows."""

    def test_add_repo_updates_meta_toml(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that adding repo updates pyproject.toml."""
        # Setup qen with in-memory storage
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/testorg/meta"],
            cwd=meta_repo,
            check=True,
            capture_output=True,
        )

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_repo),
                "org": "testorg",
                "current_project": None,
            },
        )

        project_name = "toml-update-test"
        branch = "2025-12-05-toml-update-test"
        folder = f"proj/{branch}"
        project_dir = meta_repo / folder

        project_dir.mkdir(parents=True)
        (project_dir / "repos").mkdir()
        pyproject = project_dir / "pyproject.toml"
        pyproject.write_text('[tool.qen]\ncreated = "2025-12-05T10:00:00Z"\n')

        test_storage.write_profile(
            project_name,
            {
                "name": project_name,
                "branch": branch,
                "folder": folder,
                "repo": str(meta_repo),
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add repository and verify pyproject.toml is updated
        with (
            patch("qen.init_utils.ensure_initialized"),
            patch("qen.commands.add.ensure_correct_branch"),
        ):
            add_repository(
                repo=str(child_repo),
                branch="main",
                path=None,
                verbose=False,
                storage=test_storage,
            )

        # Verify: pyproject.toml exists and is valid
        assert pyproject.exists()
        result = read_pyproject(project_dir)
        assert "tool" in result
        assert "qen" in result["tool"]
        assert "repos" in result["tool"]["qen"]
        assert len(result["tool"]["qen"]["repos"]) == 1

        # Verify: Entry has correct structure
        repo_entry = result["tool"]["qen"]["repos"][0]
        assert "url" in repo_entry
        assert "branch" in repo_entry
        assert "path" in repo_entry
        assert repo_entry["url"] == str(child_repo)
        assert repo_entry["branch"] == "main"
        assert repo_entry["path"] == "repos/main/child_repo"
