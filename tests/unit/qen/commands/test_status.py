"""Tests for qen status command.

Tests status detection, sync status, output formatting, and error handling.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from qen.cli import main
from qen.commands.status import (
    ProjectStatus,
    format_status_output,
    get_project_status,
)
from qen.config import QenConfigError
from qen.git_utils import RepoStatus, SyncStatus
from qen.pyproject_utils import RepoConfig


class TestSyncStatus:
    """Test SyncStatus data class and methods."""

    def test_sync_status_up_to_date(self) -> None:
        """Test sync status when up-to-date."""
        sync = SyncStatus(has_upstream=True, ahead=0, behind=0)

        assert sync.is_up_to_date()
        assert not sync.is_diverged()
        assert sync.description() == "up-to-date"

    def test_sync_status_ahead(self) -> None:
        """Test sync status when ahead of remote."""
        sync = SyncStatus(has_upstream=True, ahead=3, behind=0)

        assert not sync.is_up_to_date()
        assert not sync.is_diverged()
        assert sync.description() == "ahead 3 commits"

    def test_sync_status_ahead_singular(self) -> None:
        """Test sync status when ahead by 1 commit (singular)."""
        sync = SyncStatus(has_upstream=True, ahead=1, behind=0)

        assert sync.description() == "ahead 1 commit"

    def test_sync_status_behind(self) -> None:
        """Test sync status when behind remote."""
        sync = SyncStatus(has_upstream=True, ahead=0, behind=2)

        assert not sync.is_up_to_date()
        assert not sync.is_diverged()
        assert sync.description() == "behind 2 commits"

    def test_sync_status_behind_singular(self) -> None:
        """Test sync status when behind by 1 commit (singular)."""
        sync = SyncStatus(has_upstream=True, ahead=0, behind=1)

        assert sync.description() == "behind 1 commit"

    def test_sync_status_diverged(self) -> None:
        """Test sync status when diverged from remote."""
        sync = SyncStatus(has_upstream=True, ahead=2, behind=3)

        assert not sync.is_up_to_date()
        assert sync.is_diverged()
        assert sync.description() == "diverged (ahead 2 commits, behind 3 commits)"

    def test_sync_status_diverged_singular(self) -> None:
        """Test sync status when diverged (singular counts)."""
        sync = SyncStatus(has_upstream=True, ahead=1, behind=1)

        assert sync.description() == "diverged (ahead 1 commit, behind 1 commit)"

    def test_sync_status_no_upstream(self) -> None:
        """Test sync status when no upstream configured."""
        sync = SyncStatus(has_upstream=False)

        assert not sync.is_up_to_date()
        assert not sync.is_diverged()
        assert sync.description() == "no remote"


class TestRepoStatus:
    """Test RepoStatus data class and methods."""

    def test_repo_status_clean(self) -> None:
        """Test repository status when clean."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=[],
            untracked=[],
        )

        assert status.is_clean()
        assert status.status_description() == "clean"

    def test_repo_status_modified(self) -> None:
        """Test repository status with modified files."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=["file1.py", "file2.py", "file3.py"],
            staged=[],
            untracked=[],
        )

        assert not status.is_clean()
        assert status.status_description() == "3 modified"

    def test_repo_status_staged(self) -> None:
        """Test repository status with staged files."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=["file1.py", "file2.py"],
            untracked=[],
        )

        assert not status.is_clean()
        assert status.status_description() == "2 staged"

    def test_repo_status_untracked(self) -> None:
        """Test repository status with untracked files."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=[],
            untracked=["temp.txt"],
        )

        assert not status.is_clean()
        assert status.status_description() == "1 untracked"

    def test_repo_status_mixed(self) -> None:
        """Test repository status with mixed changes."""
        status = RepoStatus(
            exists=True,
            branch="main",
            modified=["file1.py"],
            staged=["file2.py", "file3.py"],
            untracked=["temp.txt"],
        )

        assert not status.is_clean()
        assert status.status_description() == "mixed (1 modified, 2 staged, 1 untracked)"

    def test_repo_status_not_exists(self) -> None:
        """Test repository status when not cloned."""
        status = RepoStatus(exists=False)

        assert not status.is_clean()
        assert status.status_description() == "not cloned"

    def test_repo_status_post_init_defaults(self) -> None:
        """Test RepoStatus __post_init__ sets default empty lists."""
        status = RepoStatus(exists=True, branch="main")

        assert status.modified == []
        assert status.staged == []
        assert status.untracked == []


class TestFormatStatusOutput:
    """Test status output formatting."""

    def test_format_clean_project(self) -> None:
        """Test formatting output for clean project."""
        meta_status = RepoStatus(
            exists=True,
            branch="2025-12-05-test-project",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=0, behind=0),
        )

        project_status = ProjectStatus(
            project_name="2025-12-05-test-project",
            project_dir=Path("/tmp/meta/proj/2025-12-05-test-project"),
            branch="2025-12-05-test-project",
            meta_status=meta_status,
            repo_statuses=[],
        )

        output = format_status_output(project_status)

        assert "Project: 2025-12-05-test-project" in output
        assert "Branch: 2025-12-05-test-project" in output
        assert "Meta Repository" in output
        assert "Status: clean" in output
        assert "Sync:   up-to-date" in output

    def test_format_with_subrepos(self) -> None:
        """Test formatting output with sub-repositories."""
        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo",
            branch="main",
            path="repos/repo",
        )
        repo_status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=1, behind=0),
        )

        project_status = ProjectStatus(
            project_name="test-project",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status)

        assert "Sub-repositories:" in output
        assert "repos/repo (https://github.com/org/repo)" in output
        assert "Status: clean" in output
        assert "Sync:   ahead 1 commit" in output

    def test_format_verbose_with_changes(self) -> None:
        """Test formatting verbose output with file changes."""
        meta_status = RepoStatus(
            exists=True,
            branch="main",
            modified=["README.md", "src/main.py"],
            staged=["tests/test.py"],
            untracked=["temp.txt"],
        )

        project_status = ProjectStatus(
            project_name="test-project",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[],
        )

        output = format_status_output(project_status, verbose=True)

        assert "Modified files:" in output
        assert "- README.md" in output
        assert "- src/main.py" in output
        assert "Staged files:" in output
        assert "- tests/test.py" in output
        assert "Untracked files:" in output
        assert "- temp.txt" in output

    def test_format_meta_only(self) -> None:
        """Test formatting with --meta-only flag."""
        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(exists=True, branch="main")

        project_status = ProjectStatus(
            project_name="test-project",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status, meta_only=True)

        assert "Meta Repository" in output
        assert "Sub-repositories:" not in output

    def test_format_repos_only(self) -> None:
        """Test formatting with --repos-only flag."""
        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(exists=True, branch="main")

        project_status = ProjectStatus(
            project_name="test-project",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status, repos_only=True)

        assert "Project:" not in output
        assert "Meta Repository" not in output
        assert "Sub-repositories:" in output

    def test_format_missing_repo(self) -> None:
        """Test formatting output for missing repository."""
        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(exists=False)

        project_status = ProjectStatus(
            project_name="test-project",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status)

        assert "Warning: Repository not cloned" in output


class TestGetProjectStatus:
    """Test get_project_status function."""

    @patch("qen.commands.status.get_current_branch")
    @patch("qen.commands.status.get_repo_status")
    @patch("qen.commands.status.load_repos_from_pyproject")
    def test_get_project_status_success(
        self, mock_load_repos: Mock, mock_get_repo_status: Mock, mock_get_branch: Mock
    ) -> None:
        """Test getting project status successfully."""
        project_dir = Path("/tmp/test")
        meta_path = Path("/tmp/meta")

        mock_get_branch.return_value = "main"
        mock_get_repo_status.return_value = RepoStatus(exists=True, branch="main")
        mock_load_repos.return_value = []

        status = get_project_status(project_dir, meta_path, fetch=False)

        assert status.project_name == "test"
        assert status.branch == "main"
        assert status.meta_status.exists
        assert len(status.repo_statuses) == 0

    @patch("qen.commands.status.get_current_branch")
    @patch("qen.commands.status.get_repo_status")
    @patch("qen.commands.status.load_repos_from_pyproject")
    def test_get_project_status_with_repos(
        self, mock_load_repos: Mock, mock_get_repo_status: Mock, mock_get_branch: Mock
    ) -> None:
        """Test getting project status with sub-repositories."""
        project_dir = Path("/tmp/test")
        meta_path = Path("/tmp/meta")

        mock_get_branch.return_value = "main"
        mock_get_repo_status.side_effect = [
            RepoStatus(exists=True, branch="main"),  # meta
            RepoStatus(exists=True, branch="develop"),  # repo1
        ]

        repo_config = RepoConfig(
            url="https://github.com/org/repo1", branch="main", path="repos/repo1"
        )
        mock_load_repos.return_value = [repo_config]

        status = get_project_status(project_dir, meta_path, fetch=False)

        assert len(status.repo_statuses) == 1
        assert status.repo_statuses[0][0] == repo_config
        assert status.repo_statuses[0][1].exists


class TestStatusCommand:
    """Test status CLI command."""

    @patch("qen.cli.RuntimeContext.from_cli")
    def test_status_command_no_config(self, mock_from_cli: Mock) -> None:
        """Test status command when qen is not initialized."""
        from qen.context.runtime import RuntimeContext, RuntimeContextError

        runner = CliRunner()

        # Mock RuntimeContext to raise error when getting current project
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.side_effect = RuntimeContextError(
            "No current project set"
        )

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        result = runner.invoke(main, ["status"])

        assert result.exit_code != 0
        assert "No current project set" in result.output

    @patch("qen.cli.RuntimeContext.from_cli")
    def test_status_command_no_active_project(self, mock_from_cli: Mock) -> None:
        """Test status command when no project is active."""
        from qen.context.runtime import RuntimeContext, RuntimeContextError

        runner = CliRunner()

        # Mock RuntimeContext that has no current project
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.side_effect = RuntimeContextError(
            "No current project set. Use 'qen config <project>' to set one, or use --proj option."
        )

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        result = runner.invoke(main, ["status"])

        assert result.exit_code != 0
        assert "No current project set" in result.output

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_command_success(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status command successful execution."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[],
        )
        mock_get_status.return_value = project_status

        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "Project: test" in result.output
        assert "Branch: main" in result.output

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_command_verbose(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status command with --verbose flag."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        meta_status = RepoStatus(
            exists=True, branch="main", modified=["README.md"], staged=[], untracked=[]
        )
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[],
        )
        mock_get_status.return_value = project_status

        result = runner.invoke(main, ["status", "--verbose"])

        assert result.exit_code == 0
        assert "Modified files:" in result.output
        assert "- README.md" in result.output

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.fetch_all_repos")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_command_with_fetch(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_fetch: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status command with --fetch flag."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[],
        )
        mock_get_status.return_value = project_status

        result = runner.invoke(main, ["status", "--fetch"])

        assert result.exit_code == 0
        mock_fetch.assert_called_once()

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_command_meta_only(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status command with --meta-only flag."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(exists=True, branch="main")

        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )
        mock_get_status.return_value = project_status

        result = runner.invoke(main, ["status", "--meta-only"])

        assert result.exit_code == 0
        assert "Meta Repository" in result.output
        assert "Sub-repositories:" not in result.output

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_command_repos_only(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status command with --repos-only flag."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        meta_status = RepoStatus(exists=True, branch="main")
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(exists=True, branch="main")

        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )
        mock_get_status.return_value = project_status

        result = runner.invoke(main, ["status", "--repos-only"])

        assert result.exit_code == 0
        assert "Meta Repository" not in result.output
        assert "Sub-repositories:" in result.output


class TestStatusErrorHandling:
    """Test status command error handling."""

    def test_status_invalid_project_name(self) -> None:
        """Test status with invalid project name."""
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with config service that raises error for nonexistent project
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_config_service = Mock()
        mock_config_service.read_project_config.side_effect = QenConfigError("Project not found")
        mock_runtime_ctx.config_service = mock_config_service
        mock_runtime_ctx.get_current_project.return_value = "nonexistent"

        result = runner.invoke(
            main, ["status", "--project", "nonexistent"], obj={"runtime_context": mock_runtime_ctx}
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("qen.context.runtime.RuntimeContext.from_cli")
    @patch("qen.commands.status.get_project_status")
    @patch("pathlib.Path.exists")
    def test_status_git_error(
        self,
        mock_exists: Mock,
        mock_get_status: Mock,
        mock_from_cli: Mock,
    ) -> None:
        """Test status when git error occurs."""
        from qen.commands.status import StatusError
        from qen.context.runtime import RuntimeContext

        runner = CliRunner()

        # Mock RuntimeContext with proper config service
        mock_runtime_ctx = Mock(spec=RuntimeContext)
        mock_runtime_ctx.get_current_project.return_value = "test-project"

        mock_config_service = Mock()
        mock_config_service.read_project_config.return_value = {
            "folder": "proj/2025-01-01-test",
            "repo": "/tmp/meta",
        }
        mock_runtime_ctx.config_service = mock_config_service

        # Make from_cli return our mocked context
        mock_from_cli.return_value = mock_runtime_ctx

        mock_exists.return_value = True

        mock_get_status.side_effect = StatusError("Failed to get status")

        result = runner.invoke(main, ["status"])

        assert result.exit_code != 0
        assert "Failed to get status" in result.output


class TestBuildBranchUrl:
    """Test build_branch_url function for generating GitHub branch URLs."""

    def test_build_branch_url_basic(self) -> None:
        """Test building branch URL from GitHub repository URL."""
        from qen.commands.status import build_branch_url

        url = build_branch_url("https://github.com/org/repo", "main")
        assert url == "https://github.com/org/repo/tree/main"

    def test_build_branch_url_feature_branch(self) -> None:
        """Test building URL for feature branch with slash."""
        from qen.commands.status import build_branch_url

        url = build_branch_url("https://github.com/org/repo", "feature/new-thing")
        assert url == "https://github.com/org/repo/tree/feature/new-thing"

    def test_build_branch_url_trailing_slash(self) -> None:
        """Test handling repository URL with trailing slash."""
        from qen.commands.status import build_branch_url

        url = build_branch_url("https://github.com/org/repo/", "main")
        assert url == "https://github.com/org/repo/tree/main"

    def test_build_branch_url_git_suffix(self) -> None:
        """Test handling repository URL with .git suffix."""
        from qen.commands.status import build_branch_url

        url = build_branch_url("https://github.com/org/repo.git", "main")
        assert url == "https://github.com/org/repo/tree/main"

    def test_build_branch_url_trailing_slash_and_git(self) -> None:
        """Test handling both trailing slash and .git suffix."""
        from qen.commands.status import build_branch_url

        url = build_branch_url("https://github.com/org/repo/.git", "main")
        assert url == "https://github.com/org/repo/tree/main"

    def test_build_branch_url_non_github(self) -> None:
        """Test non-GitHub URLs return None."""
        from qen.commands.status import build_branch_url

        assert build_branch_url("https://gitlab.com/org/repo", "main") is None
        assert build_branch_url("https://bitbucket.org/org/repo", "main") is None

    def test_build_branch_url_local_path(self) -> None:
        """Test local filesystem paths return None."""
        from qen.commands.status import build_branch_url

        assert build_branch_url("/local/path/repo", "main") is None
        assert build_branch_url("file:///Users/user/repo", "main") is None

    def test_build_branch_url_ssh_format(self) -> None:
        """Test SSH format URLs return None (not supported)."""
        from qen.commands.status import build_branch_url

        assert build_branch_url("git@github.com:org/repo.git", "main") is None


class TestFormatStatusOutputWithUrls:
    """Test status output formatting with branch and PR URLs."""

    def test_format_status_output_includes_branch_url(self) -> None:
        """Test that branch URLs are included in status output."""
        # Setup mock repo status with GitHub URL
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="feature-branch", path="repos/repo"
        )
        repo_status = RepoStatus(
            exists=True,
            branch="feature-branch",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=0, behind=0),
        )

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status, verbose=False)

        # Verify branch URL appears in output
        assert "Branch: feature-branch → https://github.com/org/repo/tree/feature-branch" in output

    def test_format_status_output_includes_pr_url(self) -> None:
        """Test that PR URLs are included when PR exists."""
        from qen.commands.pr import PrInfo

        # Setup repo with PR info
        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="pr-branch", path="repos/repo"
        )
        repo_status = RepoStatus(
            exists=True,
            branch="pr-branch",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=0, behind=0),
        )

        pr_info = PrInfo(
            repo_path="/tmp/test/repos/repo",
            repo_url="https://github.com/org/repo",
            branch="pr-branch",
            has_pr=True,
            pr_number=123,
            pr_url="https://github.com/org/repo/pull/123",
            pr_state="OPEN",
            pr_checks="passing",
        )

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
            pr_infos=[pr_info],
        )

        output = format_status_output(project_status, verbose=False)

        # Verify PR URL appears in output
        assert "PR:     #123" in output
        assert "→ https://github.com/org/repo/pull/123" in output

    def test_format_status_output_no_url_for_non_github(self) -> None:
        """Test that non-GitHub repos don't show branch URLs."""
        repo_config = RepoConfig(
            url="https://gitlab.com/org/repo", branch="main", path="repos/repo"
        )
        repo_status = RepoStatus(
            exists=True,
            branch="main",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=0, behind=0),
        )

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
        )

        output = format_status_output(project_status, verbose=False)

        # Verify no arrow or URL in branch line
        assert "Branch: main" in output
        # Get the branch line and check it doesn't have an arrow
        branch_line = [line for line in output.split("\n") if "Branch: main" in line][0]
        assert "→" not in branch_line

    def test_format_status_output_handles_missing_pr_url(self) -> None:
        """Test graceful handling when PR exists but pr_url is None."""
        from qen.commands.pr import PrInfo

        repo_config = RepoConfig(
            url="https://github.com/org/repo", branch="pr-branch", path="repos/repo"
        )
        repo_status = RepoStatus(
            exists=True,
            branch="pr-branch",
            modified=[],
            staged=[],
            untracked=[],
            sync=SyncStatus(has_upstream=True, ahead=0, behind=0),
        )

        pr_info = PrInfo(
            repo_path="/tmp/test/repos/repo",
            repo_url="https://github.com/org/repo",
            branch="pr-branch",
            has_pr=True,
            pr_number=123,
            pr_url=None,  # Simulate missing PR URL
            pr_state="OPEN",
            pr_checks="passing",
        )

        meta_status = RepoStatus(exists=True, branch="main")
        project_status = ProjectStatus(
            project_name="test",
            project_dir=Path("/tmp/test"),
            branch="main",
            meta_status=meta_status,
            repo_statuses=[(repo_config, repo_status)],
            pr_infos=[pr_info],
        )

        output = format_status_output(project_status, verbose=False)

        # Verify PR info shown but no URL
        assert "PR:     #123" in output
        # Should not have arrow after PR line
        pr_line = [line for line in output.split("\n") if "PR:" in line][0]
        assert "→" not in pr_line
