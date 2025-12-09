"""Tests for qen sh command.

Tests shell command execution, directory navigation, and error handling.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from qen.cli import main
from qen.commands.sh import execute_shell_command
from qen.config import QenConfigError


class TestShellCommand:
    """Test shell command execution."""

    def test_sh_no_init(self, tmp_path: Path) -> None:
        """Test sh command when qen is not initialized."""
        runner = CliRunner()

        # Simulate auto-init failure
        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_ensure.side_effect = click.Abort()

            result = runner.invoke(main, ["sh", "ls"])

            assert result.exit_code != 0
            mock_ensure.assert_called_once()

    def test_sh_no_active_project(self, tmp_path: Path) -> None:
        """Test sh command when no active project exists."""
        runner = CliRunner()

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(tmp_path / "meta"),
                "org": "testorg",
                # No current_project
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "ls"])

            assert result.exit_code != 0
            assert "No active project" in result.output

    def test_sh_project_not_found(self, tmp_path: Path) -> None:
        """Test sh command when project config doesn't exist."""
        runner = CliRunner()

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(tmp_path / "meta"),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.side_effect = QenConfigError("Project not found")
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "ls"])

            assert result.exit_code != 0
            assert "not found in qen configuration" in result.output

    def test_sh_project_folder_not_exists(self, tmp_path: Path) -> None:
        """Test sh command when project folder doesn't exist."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "ls"])

            assert result.exit_code != 0
            assert "Project folder does not exist" in result.output

    def test_sh_invalid_subdirectory(self, tmp_path: Path) -> None:
        """Test sh command with invalid subdirectory."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-c", "nonexistent", "ls"])

            assert result.exit_code != 0
            assert "Specified subdirectory does not exist" in result.output

    def test_sh_basic_execution_with_yes(self, tmp_path: Path) -> None:
        """Test basic shell command execution with --yes flag."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        # Create a test file to list
        (project_dir / "test.txt").write_text("test content")

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-y", "ls"])

            assert result.exit_code == 0
            assert "test.txt" in result.output

    def test_sh_execution_in_subdirectory(self, tmp_path: Path) -> None:
        """Test shell command execution in subdirectory."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        # Create subdirectory
        repos_dir = project_dir / "repos"
        repos_dir.mkdir()
        (repos_dir / "subfile.txt").write_text("subdir content")

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-c", "repos", "-y", "ls"])

            assert result.exit_code == 0
            assert "subfile.txt" in result.output

    def test_sh_verbose_output(self, tmp_path: Path) -> None:
        """Test shell command with verbose output."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "--verbose", "-y", "echo hello"])

            assert result.exit_code == 0
            assert "Project: test-project" in result.output
            assert "Project path (from config):" in result.output
            assert "Target directory:" in result.output
            assert "Command:" in result.output

    def test_sh_confirmation_prompt_yes(self, tmp_path: Path) -> None:
        """Test shell command with confirmation prompt (user says yes)."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            # Simulate user pressing enter (default Yes)
            result = runner.invoke(main, ["sh", "echo hello"], input="\n")

            assert result.exit_code == 0
            assert "Run command in this directory?" in result.output

    def test_sh_confirmation_prompt_no(self, tmp_path: Path) -> None:
        """Test shell command with confirmation prompt (user says no)."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            # Simulate user entering 'n'
            result = runner.invoke(main, ["sh", "echo hello"], input="n\n")

            assert result.exit_code != 0
            assert "Run command in this directory?" in result.output

    def test_sh_command_failure(self, tmp_path: Path) -> None:
        """Test shell command that fails."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            # Use a command that will fail
            result = runner.invoke(main, ["sh", "-y", "exit 1"])

            assert result.exit_code != 0
            assert "Command failed with exit code 1" in result.output

    def test_sh_with_specific_project(self, tmp_path: Path) -> None:
        """Test shell command with specific project option."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-other-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",  # Different from --project
            }
            mock_config.read_project_config.return_value = {
                "name": "other-project",
                "branch": "2025-12-06-other-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "--project", "other-project", "-y", "pwd"])

            assert result.exit_code == 0
            # Verify it used the specified project
            mock_config.read_project_config.assert_called_with("other-project")

    def test_sh_chdir_is_file(self, tmp_path: Path) -> None:
        """Test sh command when chdir points to a file, not directory."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        # Create a file, not a directory
        (project_dir / "notadir.txt").write_text("I am a file")

        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(meta_path),
                "org": "testorg",
                "current_project": "test-project",
            }
            mock_config.read_project_config.return_value = {
                "name": "test-project",
                "branch": "2025-12-06-test-project",
                "folder": project_folder,
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-c", "notadir.txt", "ls"])

            assert result.exit_code != 0
            assert "not a directory" in result.output


class TestExecuteShellCommand:
    """Test execute_shell_command function directly."""

    def test_execute_with_config_error(self) -> None:
        """Test execution when config read fails."""
        with patch("qen.commands.sh.ensure_initialized") as mock_ensure:
            mock_config = Mock()
            mock_config.read_main_config.side_effect = QenConfigError("Config error")
            mock_ensure.return_value = mock_config

            with pytest.raises(QenConfigError) as exc_info:
                execute_shell_command("ls", yes=True)

            assert "Config error" in str(exc_info.value)
