"""
Integration tests for qen end-to-end workflows.

Tests complete workflows including:
- Full workflow: init → create project → add repos → status
- Multi-repo management
- Real git operations
"""

import subprocess
from pathlib import Path

from qen.commands.add import add_repository
from qen.pyproject_utils import read_pyproject

from tests.helpers.qenvy_test import QenvyTest

# Note: Some tests are placeholders that will be implemented
# as additional qen functionality (status, branch management, etc.) is built.


class TestBasicWorkflow:
    """Test basic qen workflow from init to status."""

    def test_complete_init_workflow(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """
        Test complete workflow:
        1. qen init (discover meta repo)
        2. Create project configuration
        3. Add child repository
        4. Check status
        """
        # Placeholder: Will test complete workflow
        # 1. Run qen init in meta_repo
        # 2. Create a project config
        # 3. Add child_repo to project
        # 4. Run qen status
        pass

    def test_workflow_with_multiple_repos(
        self,
        meta_repo: Path,
        tmp_path: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test workflow with multiple child repositories."""
        # Placeholder: Will test multi-repo workflow
        pass

    def test_workflow_preserves_git_state(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that qen operations don't corrupt git state."""
        # Placeholder: Will test git state preservation
        pass


class TestProjectCreation:
    """Test project creation workflows."""

    def test_create_project_from_scratch(
        self,
        meta_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test creating a new project from scratch."""
        # Placeholder: Will test project creation
        pass

    def test_create_project_with_existing_repos(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test creating project with existing repositories."""
        # Placeholder: Will test project with repos
        pass

    def test_create_multiple_projects(
        self,
        meta_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test creating multiple projects."""
        # Placeholder: Will test multiple projects
        pass


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
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add repository using in-memory storage
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
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add both repositories using in-memory storage
        add_repository(
            repo=str(child_repo1),
            branch="main",
            path=None,
            verbose=False,
            storage=test_storage,
        )
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

    def test_remove_repository_from_project(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test removing a repository from a project."""
        # Placeholder: Will test removing repo
        pass

    def test_update_repository_metadata(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test updating repository metadata."""
        # Placeholder: Will test metadata updates
        pass


class TestStatusOperations:
    """Test status checking workflows."""

    def test_status_shows_all_repos(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that status shows all repositories."""
        # Placeholder: Will test status output
        pass

    def test_status_shows_git_state(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that status shows git state for each repo."""
        # Placeholder: Will test git state in status
        pass

    def test_status_with_uncommitted_changes(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test status when repos have uncommitted changes."""
        # Placeholder: Will test uncommitted changes
        pass

    def test_status_with_untracked_files(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test status when repos have untracked files."""
        # Placeholder: Will test untracked files
        pass


class TestBranchManagement:
    """Test branch management workflows."""

    def test_create_branch_across_repos(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test creating a branch across multiple repos."""
        # Placeholder: Will test branch creation
        pass

    def test_switch_branch_across_repos(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test switching branches across repos."""
        # Placeholder: Will test branch switching
        pass

    def test_handle_detached_head(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test handling of detached HEAD state."""
        # Placeholder: Will test detached HEAD
        pass


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
                "created": "2025-12-05T10:00:00Z",
            },
        )

        main_config = test_storage.read_profile("main")
        main_config["current_project"] = project_name
        test_storage.write_profile("main", main_config)

        # Test: Add repository and verify pyproject.toml is updated
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

    def test_remove_repo_updates_meta_toml(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that removing repo updates meta.toml."""
        # Placeholder: Will test meta.toml cleanup
        pass

    def test_meta_toml_remains_valid(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that meta.toml remains valid TOML."""
        # Placeholder: Will test TOML validity
        pass


class TestErrorRecovery:
    """Test error recovery in workflows."""

    def test_recover_from_failed_git_operation(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test recovery from failed git operations."""
        # Placeholder: Will test error recovery
        pass

    def test_recover_from_corrupted_config(
        self,
        meta_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test recovery from corrupted configuration."""
        # Placeholder: Will test config recovery
        pass

    def test_handle_network_errors(
        self,
        meta_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test handling of network errors during clone."""
        # Placeholder: Will test network error handling
        pass


class TestConcurrentOperations:
    """Test handling of concurrent operations."""

    def test_handle_external_git_changes(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test handling changes made outside qen."""
        # Placeholder: Will test external changes
        pass

    def test_detect_conflicting_states(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test detection of conflicting repository states."""
        # Placeholder: Will test conflict detection
        pass


class TestOfflineMode:
    """Test offline operation."""

    def test_all_operations_work_offline(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that all operations work without network."""
        # All qen operations should work offline with local repos
        # Placeholder: Will verify offline functionality
        pass

    def test_status_works_offline(
        self,
        meta_repo: Path,
        child_repo: Path,
        test_storage: QenvyTest,
    ) -> None:
        """Test that status command works offline."""
        # Placeholder: Will test offline status
        pass


# Note: These are placeholder tests that will be implemented
# once the full qen functionality is built out according to the spec.
# The integration tests follow the structure outlined in the testing
# spec but are minimal stubs for now since the CLI currently only
# prints "Hello from qen!"
#
# These tests are designed to run offline and not require network access,
# using local git repositories created by the fixtures.
