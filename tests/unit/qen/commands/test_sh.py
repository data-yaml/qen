"""Tests for qen sh command.

Tests shell command execution, directory navigation, and error handling.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import click
import pytest
from click.testing import CliRunner

from qen.cli import main
from qen.commands.sh import (
    ShellContext,
    create_shell_env,
    detect_shell,
    execute_shell_command,
    open_interactive_shell,
    prepare_shell_context,
)
from qen.config import QenConfigError


class TestShellCommand:
    """Test shell command execution."""

    def test_sh_no_init(self, tmp_path: Path) -> None:
        """Test sh command when qen is not initialized."""
        runner = CliRunner()

        # Simulate auto-init failure
        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
            mock_ensure.side_effect = click.Abort()

            result = runner.invoke(main, ["sh", "ls"])

            assert result.exit_code != 0
            mock_ensure.assert_called_once()

    def test_sh_no_active_project(self, tmp_path: Path) -> None:
        """Test sh command when no active project exists."""
        runner = CliRunner()

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
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

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-c", "notadir.txt", "ls"])

            assert result.exit_code != 0
            assert "not a directory" in result.output


class TestExecuteShellCommand:
    """Test execute_shell_command function directly."""

    def test_execute_with_config_error(self) -> None:
        """Test execution when config read fails."""
        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
            mock_config = Mock()
            mock_config.read_main_config.side_effect = QenConfigError("Config error")
            mock_ensure.return_value = mock_config

            with pytest.raises(QenConfigError) as exc_info:
                execute_shell_command("ls", yes=True)

            assert "Config error" in str(exc_info.value)


class TestInteractiveShellMode:
    """Test interactive shell mode functionality."""

    def test_sh_no_command_calls_interactive_shell(self, tmp_path: Path) -> None:
        """Test that qen sh with no command opens interactive shell."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
            patch("qen.commands.sh.open_interactive_shell") as mock_open,
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            runner.invoke(main, ["sh"])

            # Should call open_interactive_shell, not execute_shell_command
            mock_open.assert_called_once()
            assert mock_open.call_args[1]["project_name"] is None

    def test_sh_interactive_no_prompt(self, tmp_path: Path) -> None:
        """Test that qen sh (interactive) doesn't show prompt."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
            patch("qen.commands.sh.open_interactive_shell") as mock_open,
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            # Run without input - should not require user input
            result = runner.invoke(main, ["sh"])

            # Should succeed without prompting
            assert result.exit_code == 0
            # Should NOT contain the confirmation prompt
            assert "Run command in this directory?" not in result.output
            # Should call open_interactive_shell
            mock_open.assert_called_once()

    def test_sh_with_command_executes_single_command(self, tmp_path: Path) -> None:
        """Test that qen sh with command executes single command."""
        runner = CliRunner()

        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            result = runner.invoke(main, ["sh", "-y", "echo hello"])

            assert result.exit_code == 0
            assert "hello" in result.output


class TestDetectShell:
    """Test detect_shell function."""

    def test_detect_shell_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test shell detection from $SHELL environment variable."""
        monkeypatch.setenv("SHELL", "/bin/zsh")
        with patch("pathlib.Path.is_file", return_value=True):
            assert detect_shell() == "/bin/zsh"

    def test_detect_shell_fallback_bash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test shell detection falls back to /bin/bash."""
        monkeypatch.delenv("SHELL", raising=False)
        with patch("pathlib.Path.is_file", return_value=True):
            assert detect_shell() == "/bin/bash"

    def test_detect_shell_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test error when no shell found."""
        monkeypatch.delenv("SHELL", raising=False)
        with patch("pathlib.Path.is_file", return_value=False):
            with pytest.raises(click.ClickException, match="Could not detect shell"):
                detect_shell()


class TestCreateShellEnv:
    """Test create_shell_env function."""

    def test_create_shell_env_basic(self, tmp_path: Path) -> None:
        """Test environment creation with basic project."""
        context = ShellContext(
            project_name="my-project",
            project_dir=tmp_path / "proj" / "my-project",
            target_dir=tmp_path / "proj" / "my-project",
            config=Mock(),
        )

        env = create_shell_env(context, chdir=None)

        assert "QEN_PROJECT" in env
        assert env["QEN_PROJECT"] == "my-project"
        assert "QEN_PROJECT_DIR" in env
        assert "QEN_TARGET_DIR" in env
        assert "(my-project)" in env["PS1"]

    def test_create_shell_env_with_subdir(self, tmp_path: Path) -> None:
        """Test environment creation with subdirectory."""
        context = ShellContext(
            project_name="my-project",
            project_dir=tmp_path / "proj" / "my-project",
            target_dir=tmp_path / "proj" / "my-project" / "repos" / "api",
            config=Mock(),
        )

        env = create_shell_env(context, chdir="repos/api")

        assert "(my-project:repos/api)" in env["PS1"]

    def test_create_shell_env_preserves_original_ps1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that original PS1 is preserved."""
        monkeypatch.setenv("PS1", "custom> ")

        context = ShellContext(
            project_name="my-project",
            project_dir=tmp_path / "proj" / "my-project",
            target_dir=tmp_path / "proj" / "my-project",
            config=Mock(),
        )

        env = create_shell_env(context, chdir=None)

        assert "(my-project) custom> " == env["PS1"]


class TestPrepareShellContext:
    """Test prepare_shell_context function."""

    def test_prepare_shell_context_success(self, tmp_path: Path) -> None:
        """Test successful context preparation."""
        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            context = prepare_shell_context(
                project_name=None, chdir=None, yes=True, verbose=False, config_overrides=None
            )

            assert context.project_name == "test-project"
            assert context.project_dir == project_dir
            assert context.target_dir == project_dir

    def test_prepare_shell_context_with_subdir(self, tmp_path: Path) -> None:
        """Test context preparation with subdirectory."""
        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)
        repos_dir = project_dir / "repos"
        repos_dir.mkdir()

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            context = prepare_shell_context(
                project_name=None, chdir="repos", yes=True, verbose=False, config_overrides=None
            )

            assert context.target_dir == repos_dir

    def test_prepare_shell_context_no_project(self, tmp_path: Path) -> None:
        """Test error when no active project."""
        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
        ):
            mock_config = Mock()
            mock_config.read_main_config.return_value = {
                "meta_path": str(tmp_path / "meta"),
                "org": "testorg",
                # No current_project
            }
            mock_ensure.return_value = mock_config

            with pytest.raises(click.ClickException, match="No active project"):
                prepare_shell_context(
                    project_name=None, chdir=None, yes=True, verbose=False, config_overrides=None
                )


class TestOpenInteractiveShell:
    """Test open_interactive_shell function."""

    def test_open_interactive_shell_calls_execve(self, tmp_path: Path) -> None:
        """Test that open_interactive_shell calls os.execve."""
        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
            patch("qen.commands.sh.detect_shell", return_value="/bin/bash"),
            patch("os.chdir") as mock_chdir,
            patch("os.execve") as mock_execve,
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            open_interactive_shell(yes=True)

            # Verify it changed to target directory
            mock_chdir.assert_called_once_with(project_dir)

            # Verify it called execve
            mock_execve.assert_called_once()
            assert mock_execve.call_args[0][0] == "/bin/bash"

    def test_open_interactive_shell_exec_fails(self, tmp_path: Path) -> None:
        """Test error handling when exec fails."""
        meta_path = tmp_path / "meta"
        project_folder = "proj/2025-12-06-test-project"
        project_dir = meta_path / project_folder
        project_dir.mkdir(parents=True)

        with (
            patch("qen.commands.sh.ensure_initialized") as mock_ensure,
            patch("qen.commands.sh.ensure_correct_branch"),
            patch("qen.commands.sh.detect_shell", return_value="/bin/bash"),
            patch("os.chdir"),
            patch("os.execve", side_effect=OSError("exec failed")),
        ):
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
                "repo": str(meta_path),
            }
            mock_ensure.return_value = mock_config

            with pytest.raises(click.ClickException, match="Failed to spawn shell"):
                open_interactive_shell(yes=True)
