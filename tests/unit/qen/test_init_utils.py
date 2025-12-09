"""Tests for qen.init_utils module.

Tests ensure_initialized() function including:
- Fast path when config already exists
- Successful auto-initialization
- Error handling for various failure modes
- Verbose mode output
- Runtime override handling
"""

from pathlib import Path

import click
import pytest

from qen.config import QenConfig
from qen.git_utils import (
    AmbiguousOrgError,
    GitError,
    MetaRepoNotFoundError,
    NotAGitRepoError,
)
from qen.init_utils import ensure_initialized
from tests.helpers.qenvy_test import QenvyTest

# ==============================================================================
# Test ensure_initialized Function
# ==============================================================================


class TestEnsureInitialized:
    """Test ensure_initialized function for auto-initialization."""

    def test_ensure_initialized_config_exists(self, test_storage: QenvyTest, mocker) -> None:
        """Test that ensure_initialized returns immediately when config exists.

        When main config already exists, ensure_initialized should:
        - Return immediately without calling init_qen
        - Not produce any output
        - Return a valid QenConfig instance
        """
        # Setup: Create existing config
        test_storage.write_profile(
            "main",
            {
                "meta_path": "/fake/meta",
                "github_org": "testorg",
                "current_project": None,
            },
        )

        # Mock init_qen to verify it's NOT called
        # Note: init_qen is imported inside ensure_initialized, so patch at source
        mock_init_qen = mocker.patch("qen.commands.init.init_qen")

        # Execute
        config = ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was NOT called (fast path)
        mock_init_qen.assert_not_called()

        # Verify: config is valid QenConfig instance
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

    def test_ensure_initialized_auto_init_success(self, test_storage: QenvyTest, mocker) -> None:
        """Test successful auto-initialization when config doesn't exist.

        When main config doesn't exist, ensure_initialized should:
        - Call init_qen with correct parameters
        - Create the main config
        - Return a valid QenConfig instance
        """
        # Setup: No existing config (test_storage is empty by default)

        # Mock init_qen to simulate successful initialization
        def mock_init_side_effect(**kwargs):
            # Simulate init_qen creating the config
            storage = kwargs.get("storage")
            storage.write_profile(
                "main",
                {
                    "meta_path": "/fake/meta",
                    "github_org": "testorg",
                    "current_project": None,
                },
            )

        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen", side_effect=mock_init_side_effect
        )

        # Execute
        config = ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: init_qen received correct parameters
        call_kwargs = mock_init_qen.call_args.kwargs
        assert call_kwargs["verbose"] is False
        assert call_kwargs["storage"] is test_storage
        assert call_kwargs["config_dir"] is None
        assert call_kwargs["meta_path_override"] is None
        assert call_kwargs["current_project_override"] is None

        # Verify: config is valid
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

    def test_ensure_initialized_not_in_git_repo(
        self, test_storage: QenvyTest, mocker, capsys
    ) -> None:
        """Test error handling when not in a git repository.

        When init_qen raises NotAGitRepoError, ensure_initialized should:
        - Display helpful error message
        - Provide actionable guidance
        - Raise click.Abort
        """
        # Setup: No existing config

        # Mock init_qen to raise NotAGitRepoError
        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen",
            side_effect=NotAGitRepoError("Not in a git repository"),
        )

        # Execute and verify exception
        with pytest.raises(click.exceptions.Abort):
            ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: error message shown
        captured = capsys.readouterr()
        assert "Error: qen is not initialized." in captured.err
        assert "Not in a git repository" in captured.err
        assert "Navigate to your meta repository" in captured.err
        assert "qen init" in captured.err
        assert "qen --meta /path/to/meta" in captured.err

    def test_ensure_initialized_no_meta_repo_found(
        self, test_storage: QenvyTest, mocker, capsys
    ) -> None:
        """Test error handling when meta repository cannot be found.

        When init_qen raises MetaRepoNotFoundError, ensure_initialized should:
        - Display helpful error message
        - Provide actionable guidance
        - Raise click.Abort
        """
        # Setup: No existing config

        # Mock init_qen to raise MetaRepoNotFoundError
        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen",
            side_effect=MetaRepoNotFoundError(
                "Could not find meta repository (no 'proj/' directory found)"
            ),
        )

        # Execute and verify exception
        with pytest.raises(click.exceptions.Abort):
            ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: error message shown
        captured = capsys.readouterr()
        assert "Error: qen is not initialized." in captured.err
        assert "Could not find meta repository" in captured.err
        assert "proj/" in captured.err
        assert "Navigate to your meta repository" in captured.err
        assert "qen --meta /path/to/meta" in captured.err

    def test_ensure_initialized_ambiguous_org(
        self, test_storage: QenvyTest, mocker, capsys
    ) -> None:
        """Test error handling when multiple organizations detected.

        When init_qen raises AmbiguousOrgError, ensure_initialized should:
        - Display error explaining the ambiguity
        - Ask user to run qen init manually
        - Raise click.Abort
        """
        # Setup: No existing config

        # Mock init_qen to raise AmbiguousOrgError
        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen",
            side_effect=AmbiguousOrgError("Multiple organizations detected: org1, org2"),
        )

        # Execute and verify exception
        with pytest.raises(click.exceptions.Abort):
            ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: error message shown
        captured = capsys.readouterr()
        assert "Error: Cannot auto-initialize qen." in captured.err
        assert "Multiple organizations detected" in captured.err
        assert "org1, org2" in captured.err
        assert "run 'qen init' manually" in captured.err

    def test_ensure_initialized_with_meta_override(
        self, test_storage: QenvyTest, mocker, tmp_path: Path
    ) -> None:
        """Test auto-initialization with meta_path_override.

        When meta_path_override is provided, ensure_initialized should:
        - Pass the override to init_qen
        - Successfully initialize using the override path
        """
        # Setup: No existing config
        meta_path = tmp_path / "custom-meta"

        # Mock init_qen to simulate successful initialization
        def mock_init_side_effect(**kwargs):
            storage = kwargs.get("storage")
            storage.write_profile(
                "main",
                {
                    "meta_path": str(meta_path),
                    "github_org": "testorg",
                    "current_project": None,
                },
            )

        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen", side_effect=mock_init_side_effect
        )

        # Execute
        config = ensure_initialized(
            storage=test_storage,
            meta_path_override=meta_path,
            verbose=False,
        )

        # Verify: init_qen was called with override
        mock_init_qen.assert_called_once()
        call_kwargs = mock_init_qen.call_args.kwargs
        assert call_kwargs["meta_path_override"] == meta_path

        # Verify: config was created successfully
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

    def test_ensure_initialized_verbose_mode(self, test_storage: QenvyTest, mocker, capsys) -> None:
        """Test verbose mode output during auto-initialization.

        When verbose=True, ensure_initialized should:
        - Show "Auto-initializing..." message before init
        - Show success message after init
        - Still call init_qen successfully
        """
        # Setup: No existing config

        # Mock init_qen to simulate successful initialization
        def mock_init_side_effect(**kwargs):
            storage = kwargs.get("storage")
            storage.write_profile(
                "main",
                {
                    "meta_path": "/fake/meta",
                    "github_org": "testorg",
                    "current_project": None,
                },
            )

        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen", side_effect=mock_init_side_effect
        )

        # Execute with verbose=True
        config = ensure_initialized(storage=test_storage, verbose=True)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: verbose messages shown
        captured = capsys.readouterr()
        assert "Configuration not found. Auto-initializing..." in captured.out
        assert "✓ Auto-initialized qen configuration" in captured.out

        # Verify: config was created
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

    def test_ensure_initialized_git_error(self, test_storage: QenvyTest, mocker, capsys) -> None:
        """Test error handling for general git errors.

        When init_qen raises a general GitError, ensure_initialized should:
        - Display error message
        - Ask user to run qen init manually
        - Raise click.Abort
        """
        # Setup: No existing config

        # Mock init_qen to raise GitError
        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen",
            side_effect=GitError("Failed to execute git command"),
        )

        # Execute and verify exception
        with pytest.raises(click.exceptions.Abort):
            ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()

        # Verify: error message shown
        captured = capsys.readouterr()
        assert "Error: Cannot auto-initialize qen." in captured.err
        assert "Failed to execute git command" in captured.err
        assert "run 'qen init' manually" in captured.err

    def test_ensure_initialized_with_all_overrides(
        self, test_storage: QenvyTest, mocker, tmp_path: Path
    ) -> None:
        """Test that all parameters are passed through to init_qen.

        Verify that ensure_initialized correctly forwards all parameters:
        - config_dir
        - storage
        - meta_path_override
        - current_project_override
        """
        # Setup: No existing config
        config_dir = tmp_path / "config"
        meta_path = tmp_path / "meta"

        # Mock init_qen to simulate successful initialization
        def mock_init_side_effect(**kwargs):
            storage = kwargs.get("storage")
            storage.write_profile(
                "main",
                {
                    "meta_path": str(meta_path),
                    "github_org": "testorg",
                    "current_project": "test-project",
                },
            )

        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen", side_effect=mock_init_side_effect
        )

        # Execute with all overrides
        config = ensure_initialized(
            config_dir=config_dir,
            storage=test_storage,
            meta_path_override=meta_path,
            current_project_override="test-project",
            verbose=False,
        )

        # Verify: init_qen was called with all parameters
        mock_init_qen.assert_called_once()
        call_kwargs = mock_init_qen.call_args.kwargs
        assert call_kwargs["verbose"] is False
        assert call_kwargs["storage"] is test_storage
        assert call_kwargs["config_dir"] == config_dir
        assert call_kwargs["meta_path_override"] == meta_path
        assert call_kwargs["current_project_override"] == "test-project"

        # Verify: config was created
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

    def test_ensure_initialized_verbose_with_existing_config(
        self, test_storage: QenvyTest, capsys
    ) -> None:
        """Test verbose mode with existing config (fast path).

        When verbose=True but config exists, ensure_initialized should:
        - Return immediately (fast path)
        - NOT show any auto-init messages (because no init needed)
        """
        # Setup: Create existing config
        test_storage.write_profile(
            "main",
            {
                "meta_path": "/fake/meta",
                "github_org": "testorg",
                "current_project": None,
            },
        )

        # Execute with verbose=True
        config = ensure_initialized(storage=test_storage, verbose=True)

        # Verify: config is valid
        assert isinstance(config, QenConfig)
        assert config.main_config_exists()

        # Verify: NO auto-init messages shown (fast path)
        captured = capsys.readouterr()
        assert "Auto-initializing" not in captured.out
        assert "✓ Auto-initialized" not in captured.out

    def test_ensure_initialized_click_abort_from_init_qen(
        self, test_storage: QenvyTest, mocker
    ) -> None:
        """Test that click.Abort from init_qen is re-raised.

        When init_qen raises click.Abort directly (not wrapped in our exception
        handling), ensure_initialized should let it propagate.
        """
        # Setup: No existing config

        # Mock init_qen to raise click.Abort directly
        # Note: This tests the edge case where init_qen might abort
        # for reasons other than the exceptions we explicitly handle
        mock_init_qen = mocker.patch(
            "qen.commands.init.init_qen",
            side_effect=click.exceptions.Abort(),
        )

        # Execute and verify exception propagates
        with pytest.raises(click.exceptions.Abort):
            ensure_initialized(storage=test_storage, verbose=False)

        # Verify: init_qen was called
        mock_init_qen.assert_called_once()
