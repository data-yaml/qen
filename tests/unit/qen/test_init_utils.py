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
    MetaRepoNotFoundError,
    NotAGitRepoError,
)
from qen.init_utils import ensure_correct_branch, ensure_initialized
from tests.unit.helpers.qenvy_test import QenvyTest
from tests.unit.helpers.test_mock import create_test_config

# ==============================================================================
# Test ensure_initialized Function
# ==============================================================================


class TestEnsureInitialized:
    """Test ensure_initialized function for auto-initialization."""

    def test_ensure_initialized_config_exists(
        self, test_storage: QenvyTest, tmp_path: Path, mocker
    ) -> None:
        """Test that ensure_initialized returns immediately when config exists.

        When main config already exists, ensure_initialized should:
        - Return immediately without calling init_qen
        - Not produce any output
        - Return a valid QenConfig instance
        """
        # Setup: Create existing config with all required fields
        meta_path = tmp_path / "meta"
        meta_path.mkdir()

        test_storage.write_profile(
            "main",
            {
                "meta_path": str(meta_path),
                "meta_remote": "https://github.com/testorg/meta",
                "meta_parent": str(meta_path.parent),
                "meta_default_branch": "main",
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
        # Write directly to test_storage since RuntimeContext creates its own config
        def mock_init_side_effect(ctx, **kwargs):
            # Simulate init_qen creating the config
            test_storage.write_profile(
                "main",
                {
                    "meta_path": "/fake/meta",
                    "meta_remote": "https://github.com/testorg/meta",
                    "meta_parent": "/fake",
                    "meta_default_branch": "main",
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

        # Verify: init_qen received RuntimeContext and verbose=False
        call_kwargs = mock_init_qen.call_args.kwargs
        assert call_kwargs["verbose"] is False
        assert "ctx" in mock_init_qen.call_args.kwargs or len(mock_init_qen.call_args.args) > 0

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
        # Write directly to test_storage since RuntimeContext creates its own config
        def mock_init_side_effect(ctx, **kwargs):
            test_storage.write_profile(
                "main",
                {
                    "meta_path": str(meta_path),
                    "meta_remote": "https://github.com/testorg/meta",
                    "meta_parent": str(meta_path.parent),
                    "meta_default_branch": "main",
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

        # Verify: init_qen was called with RuntimeContext containing the override
        mock_init_qen.assert_called_once()
        # The context's meta_path_override should be set
        ctx_arg = mock_init_qen.call_args.kwargs.get("ctx") or mock_init_qen.call_args.args[0]
        assert ctx_arg.meta_path_override == meta_path

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
        # Write directly to test_storage since RuntimeContext creates its own config
        def mock_init_side_effect(ctx, **kwargs):
            test_storage.write_profile(
                "main",
                {
                    "meta_path": "/fake/meta",
                    "meta_remote": "https://github.com/testorg/meta",
                    "meta_parent": "/fake",
                    "meta_default_branch": "main",
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


# Branch Checking Tests
def test_ensure_correct_branch_on_correct_branch(mocker):
    """Test ensure_correct_branch when already on correct branch."""
    config = create_test_config()
    mocker.patch.object(
        config,
        "read_main_config",
        return_value={"current_project": "my-project", "meta_path": "/tmp/meta"},
    )
    mocker.patch.object(
        config,
        "read_project_config",
        return_value={"branch": "251208-my-project"},
    )
    mocker.patch("qen.git_utils.get_current_branch", return_value="251208-my-project")

    # Should not raise
    ensure_correct_branch(config)


def test_ensure_correct_branch_no_project(mocker):
    """Test ensure_correct_branch with no active project."""
    config = create_test_config()
    mocker.patch.object(
        config, "read_main_config", return_value={"current_project": None, "meta_path": "/tmp/meta"}
    )

    # Should not raise (nothing to check)
    ensure_correct_branch(config)


def test_ensure_correct_branch_dirty_repo(mocker):
    """Test ensure_correct_branch with uncommitted changes."""
    config = create_test_config()
    mocker.patch.object(
        config,
        "read_main_config",
        return_value={"current_project": "my-project", "meta_path": "/tmp/meta"},
    )
    mocker.patch.object(
        config,
        "read_project_config",
        return_value={"branch": "251208-my-project"},
    )
    mocker.patch("qen.git_utils.get_current_branch", return_value="main")
    mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=True)

    with pytest.raises(click.Abort):
        ensure_correct_branch(config)


def test_ensure_correct_branch_clean_repo_user_accepts(mocker):
    """Test ensure_correct_branch with clean repo, user accepts switch."""
    config = create_test_config()
    mocker.patch.object(
        config,
        "read_main_config",
        return_value={"current_project": "my-project", "meta_path": "/tmp/meta"},
    )
    mocker.patch.object(
        config,
        "read_project_config",
        return_value={"branch": "251208-my-project"},
    )
    mocker.patch("qen.git_utils.get_current_branch", return_value="main")
    mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
    mocker.patch("click.confirm", return_value=True)
    mock_checkout = mocker.patch("qen.git_utils.checkout_branch")

    ensure_correct_branch(config)

    mock_checkout.assert_called_once_with(Path("/tmp/meta"), "251208-my-project")


def test_ensure_correct_branch_clean_repo_user_declines(mocker):
    """Test ensure_correct_branch with clean repo, user declines switch."""
    config = create_test_config()
    mocker.patch.object(
        config,
        "read_main_config",
        return_value={"current_project": "my-project", "meta_path": "/tmp/meta"},
    )
    mocker.patch.object(
        config,
        "read_project_config",
        return_value={"branch": "251208-my-project"},
    )
    mocker.patch("qen.git_utils.get_current_branch", return_value="main")
    mocker.patch("qen.git_utils.has_uncommitted_changes", return_value=False)
    mocker.patch("click.confirm", return_value=False)

    with pytest.raises(click.Abort):
        ensure_correct_branch(config)
