"""Tests for qen.project module.

Tests project-related functionality including:
- Template path resolution
- Template rendering with variable substitution
- Project structure creation with templates
- Error handling for missing templates
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from qen.project import (
    ProjectError,
    create_project,
    create_project_structure,
    get_template_path,
    parse_project_name,
    render_template,
)

# ==============================================================================
# Test parse_project_name Function
# ==============================================================================


class TestParseProjectName:
    """Test suite for parse_project_name function."""

    def test_short_name_simple(self) -> None:
        """Test parsing a simple short name without date prefix."""
        config_name, explicit_branch = parse_project_name("myproj")
        assert config_name == "myproj"
        assert explicit_branch is None

    def test_short_name_with_hyphens(self) -> None:
        """Test parsing a short name containing hyphens."""
        config_name, explicit_branch = parse_project_name("my-project-name")
        assert config_name == "my-project-name"
        assert explicit_branch is None

    def test_short_name_with_numbers(self) -> None:
        """Test parsing a short name containing numbers."""
        config_name, explicit_branch = parse_project_name("project123")
        assert config_name == "project123"
        assert explicit_branch is None

    def test_fully_qualified_name(self) -> None:
        """Test parsing a fully-qualified name with YYMMDD prefix."""
        config_name, explicit_branch = parse_project_name("251210-myproj")
        assert config_name == "251210-myproj"
        assert explicit_branch == "251210-myproj"

    def test_fully_qualified_name_with_hyphens(self) -> None:
        """Test parsing a fully-qualified name with multiple hyphens."""
        config_name, explicit_branch = parse_project_name("251210-my-project-name")
        assert config_name == "251210-my-project-name"
        assert explicit_branch == "251210-my-project-name"

    def test_fully_qualified_name_with_numbers(self) -> None:
        """Test parsing a fully-qualified name with numbers in project part."""
        config_name, explicit_branch = parse_project_name("251210-proj123")
        assert config_name == "251210-proj123"
        assert explicit_branch == "251210-proj123"

    def test_edge_case_five_digits(self) -> None:
        """Test that 5-digit prefix is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("12345-proj")
        assert config_name == "12345-proj"
        assert explicit_branch is None

    def test_edge_case_seven_digits(self) -> None:
        """Test that 7-digit prefix is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("1234567-proj")
        assert config_name == "1234567-proj"
        assert explicit_branch is None

    def test_edge_case_alpha_prefix(self) -> None:
        """Test that alphabetic prefix is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("abc-proj")
        assert config_name == "abc-proj"
        assert explicit_branch is None

    def test_edge_case_alphanumeric_prefix(self) -> None:
        """Test that alphanumeric prefix is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("abc123-proj")
        assert config_name == "abc123-proj"
        assert explicit_branch is None

    def test_edge_case_no_hyphen(self) -> None:
        """Test that 6 digits without hyphen is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("251210proj")
        assert config_name == "251210proj"
        assert explicit_branch is None

    def test_edge_case_date_in_middle(self) -> None:
        """Test that date pattern in middle is NOT treated as YYMMDD pattern."""
        config_name, explicit_branch = parse_project_name("proj-251210-name")
        assert config_name == "proj-251210-name"
        assert explicit_branch is None

    def test_edge_case_single_char_name(self) -> None:
        """Test parsing a single character short name."""
        config_name, explicit_branch = parse_project_name("x")
        assert config_name == "x"
        assert explicit_branch is None

    def test_edge_case_fully_qualified_single_char(self) -> None:
        """Test parsing a fully-qualified name with single character project name."""
        config_name, explicit_branch = parse_project_name("251210-x")
        assert config_name == "251210-x"
        assert explicit_branch == "251210-x"

    def test_real_world_examples(self) -> None:
        """Test real-world project name examples."""
        # Short names
        assert parse_project_name("api-refactor") == ("api-refactor", None)
        assert parse_project_name("bug-fix-123") == ("bug-fix-123", None)
        assert parse_project_name("feature-auth") == ("feature-auth", None)

        # Fully-qualified names
        assert parse_project_name("251210-api-refactor") == (
            "251210-api-refactor",
            "251210-api-refactor",
        )
        assert parse_project_name("240101-bug-fix-123") == (
            "240101-bug-fix-123",
            "240101-bug-fix-123",
        )
        assert parse_project_name("251225-feature-auth") == (
            "251225-feature-auth",
            "251225-feature-auth",
        )

    def test_boundary_dates(self) -> None:
        """Test boundary date values (valid YYMMDD patterns)."""
        # Valid dates - function doesn't validate date correctness, only format
        assert parse_project_name("000000-proj")[1] == "000000-proj"
        assert parse_project_name("999999-proj")[1] == "999999-proj"
        assert parse_project_name("240101-proj")[1] == "240101-proj"
        assert parse_project_name("251231-proj")[1] == "251231-proj"


# ==============================================================================
# Test get_template_path Function
# ==============================================================================


class TestGetTemplatePath:
    """Test get_template_path function for locating template files."""

    def test_get_template_path_success_readme(self, tmp_path: Path) -> None:
        """Test that get_template_path returns correct path for README.md template."""
        # Since get_template_path looks for real files, we test it returns a Path
        # and that the file exists (this tests the actual template location)
        result = get_template_path("README.md")
        assert isinstance(result, Path)
        assert result.exists()
        assert result.name == "README.md"

    def test_get_template_path_success_pyproject(self, tmp_path: Path) -> None:
        """Test that get_template_path returns correct path for pyproject.toml template."""
        result = get_template_path("pyproject.toml")
        assert isinstance(result, Path)
        assert result.name == "pyproject.toml"

    def test_get_template_path_success_gitignore(self, tmp_path: Path) -> None:
        """Test that get_template_path returns correct path for .gitignore template."""
        result = get_template_path(".gitignore")
        assert isinstance(result, Path)
        assert result.name == ".gitignore"

    def test_get_template_path_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that get_template_path raises ProjectError for missing templates."""

        # Mock Path to simulate template not existing
        def mock_path_init(self_path: Path, *args, **kwargs):
            original_init(self_path, *args, **kwargs)

        original_init = Path.__init__

        # Mock the exists method to return False
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(ProjectError) as exc_info:
                get_template_path("nonexistent.txt")

            # Verify error message mentions the expected path
            assert "Template file not found" in str(exc_info.value)
            assert "nonexistent.txt" in str(exc_info.value)

    def test_get_template_path_error_message_includes_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that error message includes the expected template path."""
        # Mock exists to return False
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(ProjectError) as exc_info:
                get_template_path("missing.md")

            error_msg = str(exc_info.value)
            assert "missing.md" in error_msg
            assert "packaging error" in error_msg


# ==============================================================================
# Test render_template Function
# ==============================================================================


class TestRenderTemplate:
    """Test render_template function for template variable substitution."""

    def test_render_template_success(self, tmp_path: Path) -> None:
        """Test that render_template substitutes variables correctly."""
        # Create a temporary template file
        template_file = tmp_path / "test_template.txt"
        template_content = "Hello ${name}! Today is ${day}."
        template_file.write_text(template_content)

        # Render template with variables
        result = render_template(template_file, name="World", day="Monday")

        # Verify all variables are substituted
        assert result == "Hello World! Today is Monday."
        assert "${name}" not in result
        assert "${day}" not in result

    def test_render_template_multiple_variables(self, tmp_path: Path) -> None:
        """Test template rendering with multiple variables."""
        template_file = tmp_path / "multi_var.txt"
        template_file.write_text("${var1}-${var2}-${var3}")

        result = render_template(template_file, var1="A", var2="B", var3="C")

        assert result == "A-B-C"

    def test_render_template_partial_substitution(self, tmp_path: Path) -> None:
        """Test safe_substitute behavior with missing variables."""
        # Create template with multiple variables
        template_file = tmp_path / "partial.txt"
        template_file.write_text("Existing: ${existing}, Missing: ${missing}")

        # Only provide 'existing' variable
        result = render_template(template_file, existing="FOUND")

        # Verify ${existing} is substituted
        assert "FOUND" in result
        # Verify ${missing} remains as-is (safe_substitute behavior)
        assert "${missing}" in result

    def test_render_template_no_variables(self, tmp_path: Path) -> None:
        """Test rendering template with no variables."""
        template_file = tmp_path / "plain.txt"
        template_content = "This is plain text with no variables."
        template_file.write_text(template_content)

        result = render_template(template_file)

        assert result == template_content

    def test_render_template_file_not_found(self, tmp_path: Path) -> None:
        """Test render_template with non-existent file."""
        nonexistent_path = tmp_path / "does_not_exist.txt"

        # Verify ProjectError is raised
        with pytest.raises(ProjectError) as exc_info:
            render_template(nonexistent_path, var="value")

        # Verify error message mentions file not found
        assert "Template file not found" in str(exc_info.value)
        assert str(nonexistent_path) in str(exc_info.value)

    def test_render_template_complex_content(self, tmp_path: Path) -> None:
        """Test rendering template with complex multi-line content."""
        template_file = tmp_path / "complex.txt"
        template_content = """# ${title}

## Section 1
${section1}

## Section 2
${section2}

Date: ${date}
"""
        template_file.write_text(template_content)

        result = render_template(
            template_file,
            title="My Document",
            section1="First section content",
            section2="Second section content",
            date="2025-12-07",
        )

        assert "# My Document" in result
        assert "First section content" in result
        assert "Second section content" in result
        assert "Date: 2025-12-07" in result
        assert "${" not in result  # All variables substituted


# ==============================================================================
# Test create_project_structure Function
# ==============================================================================


class TestCreateProjectStructure:
    """Test create_project_structure function."""

    def test_create_project_structure_with_templates(self, tmp_path: Path, mocker) -> None:
        """Test that create_project_structure uses templates correctly."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        project_name = "test-project"
        branch_name = "2025-12-07-test-project"
        folder_path = "proj/2025-12-07-test-project"

        # Mock get_template_path to return temporary template files
        readme_template = tmp_path / "README.md"
        readme_template.write_text("# ${project_name}\nBranch: ${branch_name}")

        pyproject_template = tmp_path / "pyproject.toml"
        pyproject_template.write_text("[tool.qen]\ncreated = '${timestamp}'")

        gitignore_template = tmp_path / ".gitignore"
        gitignore_template.write_text("repos/\n*.pyc")

        qen_template = tmp_path / "qen"
        qen_template.write_text("#!/bin/bash\necho qen")

        # Mock get_template_path
        def mock_get_template_path(name: str) -> Path:
            if name == "README.md":
                return readme_template
            elif name == "pyproject.toml":
                return pyproject_template
            elif name == ".gitignore":
                return gitignore_template
            elif name == "qen":
                return qen_template
            raise FileNotFoundError(name)

        mocker.patch("qen.project.get_template_path", side_effect=mock_get_template_path)

        # Create project structure
        create_project_structure(
            meta_path=meta_path,
            project_name=project_name,
            branch_name=branch_name,
            folder_path=folder_path,
            github_org="test-org",
        )

        # Verify project directory was created
        project_dir = meta_path / folder_path
        assert project_dir.exists()
        assert project_dir.is_dir()

        # Verify README.md was created with rendered content
        readme_path = project_dir / "README.md"
        assert readme_path.exists()
        readme_content = readme_path.read_text()
        assert "# test-project" in readme_content
        assert "Branch: 2025-12-07-test-project" in readme_content
        assert "${project_name}" not in readme_content

        # Verify pyproject.toml was created with rendered content
        pyproject_path = project_dir / "pyproject.toml"
        assert pyproject_path.exists()
        pyproject_content = pyproject_path.read_text()
        assert "[tool.qen]" in pyproject_content
        assert "${timestamp}" not in pyproject_content

        # Verify .gitignore was created with rendered content
        gitignore_path = project_dir / ".gitignore"
        assert gitignore_path.exists()
        gitignore_content = gitignore_path.read_text()
        assert "repos/" in gitignore_content

        # Verify repos/ directory was created
        repos_dir = project_dir / "repos"
        assert repos_dir.exists()
        assert repos_dir.is_dir()

    def test_create_project_structure_template_variables(self, tmp_path: Path, mocker) -> None:
        """Test that template_vars includes all required variables."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Create a template that uses all variables
        readme_template = tmp_path / "README.md"
        readme_template.write_text(
            "Project: ${project_name}\n"
            "Date: ${date}\n"
            "Timestamp: ${timestamp}\n"
            "Branch: ${branch_name}\n"
            "Folder: ${folder_path}\n"
            "Org: ${github_org}\n"
            "Meta: ${meta_path}"
        )

        pyproject_template = tmp_path / "pyproject.toml"
        pyproject_template.write_text("[tool.qen]\nname = '${project_name}'")

        gitignore_template = tmp_path / ".gitignore"
        gitignore_template.write_text("repos/")

        qen_template = tmp_path / "qen"
        qen_template.write_text("#!/bin/bash\necho qen")

        def mock_get_template_path(name: str) -> Path:
            if name == "README.md":
                return readme_template
            elif name == "pyproject.toml":
                return pyproject_template
            elif name == ".gitignore":
                return gitignore_template
            elif name == "qen":
                return qen_template
            raise FileNotFoundError(name)

        mocker.patch("qen.project.get_template_path", side_effect=mock_get_template_path)

        # Create project structure
        create_project_structure(
            meta_path=meta_path,
            project_name="my-project",
            branch_name="2025-12-07-my-project",
            folder_path="proj/2025-12-07-my-project",
            github_org="my-org",
        )

        # Verify all variables were substituted
        project_dir = meta_path / "proj/2025-12-07-my-project"
        readme_content = (project_dir / "README.md").read_text()

        assert "Project: my-project" in readme_content
        assert "Branch: 2025-12-07-my-project" in readme_content
        assert "Folder: proj/2025-12-07-my-project" in readme_content
        assert "Org: my-org" in readme_content
        # Verify no unreplaced template variables
        assert "${" not in readme_content

    def test_create_project_structure_github_org_default(self, tmp_path: Path, mocker) -> None:
        """Test default github_org value when not provided."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Create template that uses github_org
        readme_template = tmp_path / "README.md"
        readme_template.write_text("Organization: ${github_org}")

        pyproject_template = tmp_path / "pyproject.toml"
        pyproject_template.write_text("[tool.qen]")

        gitignore_template = tmp_path / ".gitignore"
        gitignore_template.write_text("repos/")

        qen_template = tmp_path / "qen"
        qen_template.write_text("#!/bin/bash\necho qen")

        def mock_get_template_path(name: str) -> Path:
            if name == "README.md":
                return readme_template
            elif name == "pyproject.toml":
                return pyproject_template
            elif name == ".gitignore":
                return gitignore_template
            elif name == "qen":
                return qen_template
            raise FileNotFoundError(name)

        mocker.patch("qen.project.get_template_path", side_effect=mock_get_template_path)

        # Create project structure without github_org
        create_project_structure(
            meta_path=meta_path,
            project_name="test-project",
            branch_name="2025-12-07-test-project",
            folder_path="proj/2025-12-07-test-project",
            github_org=None,  # Not provided
        )

        # Verify default value 'your-org' was used
        project_dir = meta_path / "proj/2025-12-07-test-project"
        readme_content = (project_dir / "README.md").read_text()
        assert "Organization: your-org" in readme_content

    def test_create_project_structure_already_exists(self, tmp_path: Path) -> None:
        """Test that creating duplicate project structure fails."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Create the project directory manually
        project_dir = meta_path / "proj/2025-12-07-test-project"
        project_dir.mkdir(parents=True)

        # Try to create project structure - should fail
        with pytest.raises(ProjectError) as exc_info:
            create_project_structure(
                meta_path=meta_path,
                project_name="test-project",
                branch_name="2025-12-07-test-project",
                folder_path="proj/2025-12-07-test-project",
            )

        assert "already exists" in str(exc_info.value)

    def test_create_project_structure_template_error(self, tmp_path: Path, mocker) -> None:
        """Test error handling when template rendering fails."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Mock get_template_path to raise error
        mocker.patch(
            "qen.project.get_template_path",
            side_effect=ProjectError("Template not found"),
        )

        # Should propagate the error
        with pytest.raises(ProjectError):
            create_project_structure(
                meta_path=meta_path,
                project_name="test-project",
                branch_name="2025-12-07-test-project",
                folder_path="proj/2025-12-07-test-project",
            )


# ==============================================================================
# Test create_project Function
# ==============================================================================


class TestCreateProject:
    """Test create_project function integration."""

    def test_create_project_with_github_org(self, tmp_path: Path, mocker) -> None:
        """Test that create_project passes github_org to create_project_structure."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Mock all the functions that create_project calls
        mocker.patch("qen.project.create_branch")
        mock_create_structure = mocker.patch("qen.project.create_project_structure")
        mocker.patch("qen.project.stage_project_files")
        mocker.patch("qen.project.commit_project")

        # Call create_project with github_org
        create_project(
            meta_path=meta_path,
            project_name="test-project",
            github_org="custom-org",
        )

        # Verify create_project_structure was called with github_org
        mock_create_structure.assert_called_once()
        # call_args[0] are positional args, call_args[1] are kwargs
        call_positional_args = mock_create_structure.call_args[0]
        # create_project_structure(meta_path, project_name, branch_name, folder_path, github_org)
        assert call_positional_args[1] == "test-project"  # project_name
        assert call_positional_args[4] == "custom-org"  # github_org

    def test_create_project_without_github_org(self, tmp_path: Path, mocker) -> None:
        """Test that create_project works without explicit github_org."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Mock all the functions that create_project calls
        mocker.patch("qen.project.create_branch")
        mock_create_structure = mocker.patch("qen.project.create_project_structure")
        mocker.patch("qen.project.stage_project_files")
        mocker.patch("qen.project.commit_project")

        # Call create_project without github_org
        create_project(
            meta_path=meta_path,
            project_name="test-project",
            github_org=None,
        )

        # Verify create_project_structure was called with None
        mock_create_structure.assert_called_once()
        call_positional_args = mock_create_structure.call_args[0]
        # create_project_structure(meta_path, project_name, branch_name, folder_path, github_org)
        assert call_positional_args[4] is None  # github_org

    def test_create_project_date_propagation(self, tmp_path: Path, mocker) -> None:
        """Test that custom date is used for branch and folder names."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Mock all the functions that create_project calls
        mocker.patch("qen.project.create_branch")
        mock_create_structure = mocker.patch("qen.project.create_project_structure")
        mocker.patch("qen.project.stage_project_files")
        mocker.patch("qen.project.commit_project")

        # Use custom date
        custom_date = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        create_project(
            meta_path=meta_path,
            project_name="test-project",
            date=custom_date,
        )

        # Verify branch and folder names use the custom date
        mock_create_structure.assert_called_once()
        call_positional_args = mock_create_structure.call_args[0]
        # create_project_structure(meta_path, project_name, branch_name, folder_path, github_org)
        assert call_positional_args[2] == "240115-test-project"  # branch_name
        assert call_positional_args[3] == "proj/240115-test-project"  # folder_path


# ==============================================================================
# Test Error Cases
# ==============================================================================


class TestProjectErrorCases:
    """Test error handling in project module."""

    def test_render_template_read_error(self, tmp_path: Path, mocker) -> None:
        """Test that read errors are wrapped in ProjectError."""
        template_file = tmp_path / "template.txt"
        template_file.write_text("content")

        # Mock read_text to raise an error
        mocker.patch.object(Path, "read_text", side_effect=PermissionError("Access denied"))

        with pytest.raises(ProjectError) as exc_info:
            render_template(template_file)

        assert "Failed to render template" in str(exc_info.value)


# ==============================================================================
# Test QEN Executable Creation
# ==============================================================================


class TestQenExecutableCreation:
    """Test qen executable wrapper creation."""

    def test_qen_executable_created(self, tmp_path: Path, mocker) -> None:
        """Test that qen executable is created during project structure creation."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Mock template functions
        mocker.patch("qen.project.get_template_path", return_value=tmp_path / "template")
        mocker.patch("qen.project.render_template", return_value="rendered content")

        create_project_structure(
            meta_path, "test-proj", "2025-12-08-test-proj", "proj/2025-12-08-test-proj"
        )

        project_dir = meta_path / "proj" / "2025-12-08-test-proj"
        qen_executable = project_dir / "qen"

        assert qen_executable.exists()
        assert qen_executable.stat().st_mode & 0o111  # Check executable bits

    def test_qen_executable_has_meta_path_variable(self, tmp_path: Path, mocker) -> None:
        """Test that qen executable template receives meta_path variable."""
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        # Track all template renders
        render_calls = []

        def capture_render(template_path: Path, **variables):
            render_calls.append((template_path, variables))
            return "rendered content"

        # Return different paths for different templates
        def get_template(name: str) -> Path:
            return tmp_path / name

        mocker.patch("qen.project.get_template_path", side_effect=get_template)
        mocker.patch("qen.project.render_template", side_effect=capture_render)

        create_project_structure(
            meta_path, "test-proj", "2025-12-08-test-proj", "proj/2025-12-08-test-proj"
        )

        # Find the qen template render call
        qen_renders = [(path, vars) for path, vars in render_calls if path.name == "qen"]
        assert len(qen_renders) == 1
        _, qen_vars = qen_renders[0]

        assert "meta_path" in qen_vars
        assert qen_vars["meta_path"] == str(meta_path)
