"""Tests for qen config command.

Tests the config command functionality including:
- Displaying current project configuration
- Listing all projects
- Switching between projects
- Showing global configuration
- JSON output format
"""

import json
from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from qen.commands.config import (
    config_command,
    count_repositories,
    display_current_project,
    display_global_config,
    display_project_list,
    get_current_project_name,
    list_all_projects,
    switch_project,
)
from qen.config import QenConfig
from tests.unit.helpers.qenvy_test import QenvyTest


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def config_with_projects(test_storage: QenvyTest, tmp_path: Path) -> QenConfig:
    """Create a config with meta repo and multiple projects."""
    config = QenConfig(storage=test_storage)

    # Create main config
    meta_path = tmp_path / "meta"
    meta_path.mkdir()
    config.write_main_config(
        meta_path=str(meta_path),
        meta_remote="git@github.com:testorg/meta.git",
        meta_parent=str(meta_path / ".."),
        meta_default_branch="main",
        org="testorg",
        current_project="project-one",
    )

    # Create project directories and configs
    for i, project_name in enumerate(["project-one", "project-two", "project-three"]):
        branch = f"2025-01-0{i + 1}-{project_name}"
        folder = f"proj/{branch}"
        project_dir = meta_path / folder
        project_dir.mkdir(parents=True, exist_ok=True)

        # Create pyproject.toml
        pyproject = project_dir / "pyproject.toml"
        if i == 0:
            # Project one has 2 repos
            pyproject.write_text(
                """[[tool.qen.repos]]
url = "https://github.com/testorg/repo1"
branch = "main"
path = "repos/repo1"

[[tool.qen.repos]]
url = "https://github.com/testorg/repo2"
branch = "main"
path = "repos/repo2"
"""
            )
        elif i == 1:
            # Project two has 1 repo
            pyproject.write_text(
                """[[tool.qen.repos]]
url = "https://github.com/testorg/repo3"
branch = "main"
path = "repos/repo3"
"""
            )
        else:
            # Project three has no repos
            pyproject.write_text("[tool.qen]\n")

        config.write_project_config(
            project_name=project_name,
            branch=branch,
            folder=folder,
            repo=str(meta_path),
            created=f"2025-01-0{i + 1}T10:00:00Z",
        )

    return config


class TestGetCurrentProjectName:
    """Test getting current project name from config."""

    def test_get_current_project_none(self, test_storage: QenvyTest) -> None:
        """Test when no current project is set."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path="/tmp/meta",
            meta_remote="git@github.com:testorg/meta.git",
            meta_parent="/tmp",
            meta_default_branch="main",
            org="testorg",
            current_project=None,
        )

        result = get_current_project_name(config)
        assert result is None

    def test_get_current_project_set(self, test_storage: QenvyTest) -> None:
        """Test when current project is set."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path="/tmp/meta",
            meta_remote="git@github.com:testorg/meta.git",
            meta_parent="/tmp",
            meta_default_branch="main",
            org="testorg",
            current_project="my-project",
        )

        result = get_current_project_name(config)
        assert result == "my-project"

    def test_get_current_project_no_config(self, test_storage: QenvyTest) -> None:
        """Test when main config doesn't exist."""
        config = QenConfig(storage=test_storage)

        result = get_current_project_name(config)
        assert result is None


class TestCountRepositories:
    """Test counting repositories in a project."""

    def test_count_repositories_zero(self, tmp_path: Path) -> None:
        """Test counting repositories when project has none."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create empty pyproject.toml
        (project_dir / "pyproject.toml").write_text("[tool.qen]\n")

        project_config = {"folder": "project", "repo": str(tmp_path)}
        result = count_repositories(project_config)
        assert result == 0

    def test_count_repositories_multiple(self, tmp_path: Path) -> None:
        """Test counting repositories when project has multiple."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        # Create pyproject.toml with repos
        (project_dir / "pyproject.toml").write_text(
            """[[tool.qen.repos]]
url = "https://github.com/org/repo1"
branch = "main"
path = "repos/repo1"

[[tool.qen.repos]]
url = "https://github.com/org/repo2"
branch = "main"
path = "repos/repo2"
"""
        )

        project_config = {"folder": "project", "repo": str(tmp_path)}
        result = count_repositories(project_config)
        assert result == 2

    def test_count_repositories_missing_pyproject(self, tmp_path: Path) -> None:
        """Test counting repositories when pyproject.toml is missing."""
        project_config = {"folder": "nonexistent", "repo": str(tmp_path)}
        result = count_repositories(project_config)
        assert result == 0


class TestListAllProjects:
    """Test listing all projects."""

    def test_list_all_projects_empty(self, test_storage: QenvyTest) -> None:
        """Test listing projects when none exist."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path="/tmp/meta",
            meta_remote="git@github.com:testorg/meta.git",
            meta_parent="/tmp",
            meta_default_branch="main",
            org="testorg",
        )

        result = list_all_projects(config)
        assert result == []

    def test_list_all_projects_multiple(self, config_with_projects: QenConfig) -> None:
        """Test listing multiple projects."""
        result = list_all_projects(config_with_projects)

        assert len(result) == 3
        # Should be sorted by created date (newest first)
        assert result[0].name == "project-three"
        assert result[1].name == "project-two"
        assert result[2].name == "project-one"

        # Check current project marker
        assert result[2].is_current is True  # project-one is current
        assert result[0].is_current is False
        assert result[1].is_current is False

    def test_list_all_projects_with_repo_counts(self, config_with_projects: QenConfig) -> None:
        """Test that repo counts are correct."""
        result = list_all_projects(config_with_projects)

        # Find each project
        project_one = next(p for p in result if p.name == "project-one")
        project_two = next(p for p in result if p.name == "project-two")
        project_three = next(p for p in result if p.name == "project-three")

        assert project_one.repository_count == 2
        assert project_two.repository_count == 1
        assert project_three.repository_count == 0


class TestDisplayCurrentProject:
    """Test displaying current project configuration."""

    def test_display_no_current_project(
        self, test_storage: QenvyTest, config_with_projects: QenConfig
    ) -> None:
        """Test display when no current project is set."""
        # Update to have no current project
        config_with_projects.update_current_project(None)

        # Capture output
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_current_project(config_with_projects)

        result = output.getvalue()
        assert "No current project set" in result
        assert "project-one" in result  # Should list available projects

    def test_display_current_project_text(self, config_with_projects: QenConfig) -> None:
        """Test display current project in text format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_current_project(config_with_projects, json_output=False)

        result = output.getvalue()
        assert "Current project: project-one" in result
        assert "Branch:" in result
        assert "2025-01-01-project-one" in result
        assert "Repositories (2):" in result

    def test_display_current_project_json(self, config_with_projects: QenConfig) -> None:
        """Test display current project in JSON format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_current_project(config_with_projects, json_output=True)

        result = output.getvalue()
        data = json.loads(result)

        assert data["current_project"] == "project-one"
        assert data["project"]["name"] == "project-one"
        assert data["project"]["branch"] == "2025-01-01-project-one"
        assert "repositories" in data["project"]


class TestDisplayProjectList:
    """Test displaying project list."""

    def test_display_list_empty(self, test_storage: QenvyTest) -> None:
        """Test displaying list when no projects exist."""
        config = QenConfig(storage=test_storage)
        config.write_main_config(
            meta_path="/tmp/meta",
            meta_remote="git@github.com:testorg/meta.git",
            meta_parent="/tmp",
            meta_default_branch="main",
            org="testorg",
        )

        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_project_list(config)

        result = output.getvalue()
        assert "No projects found" in result

    def test_display_list_text_format(self, config_with_projects: QenConfig) -> None:
        """Test displaying list in text format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_project_list(config_with_projects, compact=False)

        result = output.getvalue()
        assert "Available projects:" in result
        assert "* project-one (current)" in result
        assert "project-two" in result
        assert "project-three" in result
        assert "3 projects total" in result

    def test_display_list_compact_format(self, config_with_projects: QenConfig) -> None:
        """Test displaying list in compact format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_project_list(config_with_projects, compact=True)

        result = output.getvalue()
        assert "* project-one" in result
        assert "2 repos" in result
        assert "2025-01-01" in result

    def test_display_list_json_format(self, config_with_projects: QenConfig) -> None:
        """Test displaying list in JSON format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_project_list(config_with_projects, json_output=True)

        result = output.getvalue()
        data = json.loads(result)

        assert data["current_project"] == "project-one"
        assert len(data["projects"]) == 3
        assert data["projects"][0]["name"] == "project-three"  # Newest first
        assert data["projects"][0]["is_current"] is False
        assert any(p["is_current"] for p in data["projects"])


class TestSwitchProject:
    """Test switching between projects."""

    def test_switch_project_success(self, config_with_projects: QenConfig, mocker) -> None:
        """Test successfully switching to an existing project."""
        import io
        from contextlib import redirect_stdout

        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-01-02-project-two")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        output = io.StringIO()
        with redirect_stdout(output):
            switch_project("project-two", config=config_with_projects)

        result = output.getvalue()
        assert "Switched to project: project-two" in result

        # Verify current project changed
        current = get_current_project_name(config_with_projects)
        assert current == "project-two"

    def test_switch_project_not_found(
        self, config_with_projects: QenConfig, runner: CliRunner
    ) -> None:
        """Test switching to non-existent project."""
        import io
        from contextlib import redirect_stderr, redirect_stdout

        output = io.StringIO()
        errors = io.StringIO()

        with redirect_stdout(output), redirect_stderr(errors):
            with pytest.raises(click.Abort):
                switch_project("nonexistent-project", config=config_with_projects)

        error_output = errors.getvalue() + output.getvalue()
        assert "not found" in error_output.lower()


class TestDisplayGlobalConfig:
    """Test displaying global configuration."""

    def test_display_global_text_format(self, config_with_projects: QenConfig) -> None:
        """Test displaying global config in text format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_global_config(config_with_projects, json_output=False)

        result = output.getvalue()
        assert "Global QEN Configuration:" in result
        assert "Meta Repository:" in result
        assert "testorg" in result
        assert "Current Project:" in result
        assert "project-one" in result

    def test_display_global_json_format(self, config_with_projects: QenConfig) -> None:
        """Test displaying global config in JSON format."""
        import io
        from contextlib import redirect_stdout

        output = io.StringIO()
        with redirect_stdout(output):
            display_global_config(config_with_projects, json_output=True)

        result = output.getvalue()
        data = json.loads(result)

        assert "meta_path" in data
        assert data["github_org"] == "testorg"
        assert data["current_project"] == "project-one"
        assert "tools" in data
        assert "git" in data["tools"]


class TestConfigCommand:
    """Test the config CLI command."""

    def test_config_not_initialized(
        self, test_storage: QenvyTest, runner: CliRunner, mocker
    ) -> None:
        """Test config command when qen is not initialized."""
        # Create a config without main config file
        config = QenConfig(storage=test_storage)
        # Don't call write_main_config - leave it uninitialized

        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(config_command, obj={"config": config})

        assert result.exit_code != 0
        assert "not initialized" in result.output.lower()

    def test_config_show_current(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command showing current project."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(config_command, obj={"config": config_with_projects})

        assert result.exit_code == 0
        assert "Current project: project-one" in result.output

    def test_config_list_projects(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command listing all projects."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(config_command, ["--list"], obj={"config": config_with_projects})

        assert result.exit_code == 0
        assert "Available projects:" in result.output
        assert "project-one" in result.output
        assert "project-two" in result.output
        assert "project-three" in result.output

    def test_config_list_compact(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command listing projects in compact format."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(
            config_command, ["--list", "--compact"], obj={"config": config_with_projects}
        )

        assert result.exit_code == 0
        assert "project-one" in result.output
        assert "repos" in result.output
        assert "2025-01-01" in result.output

    def test_config_show_global(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command showing global configuration."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(config_command, ["--global"], obj={"config": config_with_projects})

        assert result.exit_code == 0
        assert "Global QEN Configuration:" in result.output
        assert "testorg" in result.output

    def test_config_json_output(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command with JSON output."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(config_command, ["--json"], obj={"config": config_with_projects})

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["current_project"] == "project-one"

    def test_config_switch_project(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test config command switching projects."""
        # Mock git operations for switch_project
        mocker.patch("qen.git_utils.get_current_branch", return_value="2025-01-02-project-two")
        mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
        mocker.patch("qen.git_utils.checkout_branch")

        result = runner.invoke(
            config_command, ["project-two"], obj={"config": config_with_projects}
        )

        assert result.exit_code == 0
        assert "Switched to project: project-two" in result.output

        # Verify switch worked
        current = get_current_project_name(config_with_projects)
        assert current == "project-two"

    def test_config_switch_json_error(
        self, config_with_projects: QenConfig, runner: CliRunner, mocker
    ) -> None:
        """Test that switching with --json flag produces an error."""
        # Mock ensure_correct_branch
        mocker.patch("qen.init_utils.ensure_correct_branch")

        result = runner.invoke(
            config_command, ["project-two", "--json"], obj={"config": config_with_projects}
        )

        assert result.exit_code != 0
        assert "Cannot combine" in result.output or "json" in result.output.lower()
