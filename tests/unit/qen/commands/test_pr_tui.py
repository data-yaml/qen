"""Tests for TUI adapter functions and action handlers.

Tests the data transformation and handler logic without testing the
interactive prompt_toolkit components themselves.

Focus is on:
- build_pr_table(): Converting PrInfo to TUI table rows
- handle_*() functions: Action handlers with mocked subprocess calls
- PrTableState: Table state management
"""

import subprocess
from unittest.mock import Mock, patch

from qen.commands.pr import PrInfo
from qen.commands.pr_tui import (
    PrTableRow,
    PrTableState,
    build_pr_table,
    handle_close,
    handle_create,
    handle_merge,
    handle_stack_view,
    handle_update_branch,
    prompt_for_action,
)


class TestBuildPrTable:
    """Test conversion of PrInfo to TUI table rows."""

    def test_build_pr_table_with_prs(self) -> None:
        """Test building table with PRs that exist."""
        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="main",
                has_pr=True,
                pr_number=123,
                pr_state="open",
                pr_checks="passing",
            ),
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature",
                has_pr=True,
                pr_number=456,
                pr_state="merged",
                pr_checks="failing",
            ),
        ]

        rows = build_pr_table(pr_infos)

        assert len(rows) == 2

        # First row
        assert rows[0].index == 1
        assert rows[0].repo_name == "repo1"
        assert rows[0].branch == "main"
        assert rows[0].pr_number == "#123"
        assert rows[0].pr_state == "open"
        assert rows[0].checks == "passing"
        assert rows[0].pr_info == pr_infos[0]

        # Second row
        assert rows[1].index == 2
        assert rows[1].repo_name == "repo2"
        assert rows[1].branch == "feature"
        assert rows[1].pr_number == "#456"
        assert rows[1].pr_state == "merged"
        assert rows[1].checks == "failing"
        assert rows[1].pr_info == pr_infos[1]

    def test_build_pr_table_without_prs(self) -> None:
        """Test building table for repos without PRs."""
        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="main",
                has_pr=False,
            ),
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature",
                has_pr=False,
            ),
        ]

        rows = build_pr_table(pr_infos)

        assert len(rows) == 2

        # First row - no PR
        assert rows[0].index == 1
        assert rows[0].pr_number == "-"
        assert rows[0].pr_state == "-"
        assert rows[0].checks == "-"

        # Second row - no PR
        assert rows[1].index == 2
        assert rows[1].pr_number == "-"
        assert rows[1].pr_state == "-"
        assert rows[1].checks == "-"

    def test_build_pr_table_mixed(self) -> None:
        """Test building table with mix of PRs and non-PRs."""
        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="main",
                has_pr=True,
                pr_number=123,
                pr_state="open",
                pr_checks="pending",
            ),
            PrInfo(
                repo_path="repo2",
                repo_url="https://github.com/org/repo2",
                branch="feature",
                has_pr=False,
            ),
        ]

        rows = build_pr_table(pr_infos)

        assert rows[0].pr_number == "#123"
        assert rows[0].checks == "pending"
        assert rows[1].pr_number == "-"
        assert rows[1].checks == "-"

    def test_build_pr_table_empty(self) -> None:
        """Test building table with empty list."""
        rows = build_pr_table([])
        assert rows == []

    def test_build_pr_table_pr_without_number(self) -> None:
        """Test building table when PR exists but number is None."""
        pr_infos = [
            PrInfo(
                repo_path="repo1",
                repo_url="https://github.com/org/repo1",
                branch="main",
                has_pr=True,
                pr_number=None,  # Edge case
                pr_state="open",
            )
        ]

        rows = build_pr_table(pr_infos)

        assert len(rows) == 1
        assert rows[0].pr_number == "-"


class TestPrTableState:
    """Test table state management."""

    def test_initial_state(self) -> None:
        """Test initial table state."""
        rows = [
            PrTableRow(1, "repo1", "main", "main", "#123", "open", "passing", Mock()),
            PrTableRow(2, "repo2", "feature", "main", "#456", "merged", "failing", Mock()),
        ]

        state = PrTableState(rows)

        assert state.current_row == 0
        assert len(state.selected_indices) == 0
        assert len(state.rows) == 2

    def test_move_up(self) -> None:
        """Test moving cursor up."""
        rows = [Mock(), Mock(), Mock()]
        state = PrTableState(rows)

        # Start at row 0
        assert state.current_row == 0

        # Can't move up from row 0
        state.move_up()
        assert state.current_row == 0

        # Move to row 2
        state.current_row = 2
        state.move_up()
        assert state.current_row == 1

    def test_move_down(self) -> None:
        """Test moving cursor down."""
        rows = [Mock(), Mock(), Mock()]
        state = PrTableState(rows)

        assert state.current_row == 0
        state.move_down()
        assert state.current_row == 1

        state.move_down()
        assert state.current_row == 2

        # Can't move past last row
        state.move_down()
        assert state.current_row == 2

    def test_toggle_selection(self) -> None:
        """Test toggling row selection."""
        rows = [Mock(), Mock(), Mock()]
        state = PrTableState(rows)

        # Select row 0
        assert 0 not in state.selected_indices
        state.toggle_selection()
        assert 0 in state.selected_indices

        # Deselect row 0
        state.toggle_selection()
        assert 0 not in state.selected_indices

        # Select multiple rows
        state.current_row = 0
        state.toggle_selection()
        state.current_row = 2
        state.toggle_selection()
        assert 0 in state.selected_indices
        assert 2 in state.selected_indices
        assert 1 not in state.selected_indices

    def test_get_selected_rows(self) -> None:
        """Test getting selected rows."""
        row1 = PrTableRow(1, "repo1", "main", "main", "#123", "open", "passing", Mock())
        row2 = PrTableRow(2, "repo2", "feature", "main", "#456", "merged", "failing", Mock())
        row3 = PrTableRow(3, "repo3", "develop", "main", "#789", "open", "pending", Mock())

        state = PrTableState([row1, row2, row3])

        # Select rows 0 and 2
        state.selected_indices = {0, 2}

        selected = state.get_selected_rows()
        assert len(selected) == 2
        assert selected[0] == row1
        assert selected[1] == row3

    def test_get_selected_rows_sorted(self) -> None:
        """Test that selected rows are returned in sorted order."""
        rows = [Mock(), Mock(), Mock()]
        state = PrTableState(rows)

        # Select in reverse order
        state.selected_indices = {2, 0, 1}

        selected = state.get_selected_rows()
        assert len(selected) == 3
        # Should be sorted by index
        assert selected == [rows[0], rows[1], rows[2]]

    def test_format_table(self) -> None:
        """Test table formatting."""
        row1 = PrTableRow(1, "repo1", "main", "main", "#123", "open", "passing", Mock())
        row2 = PrTableRow(2, "repo2", "feature-branch", "-", "-", "-", "-", Mock())

        state = PrTableState([row1, row2])
        state.current_row = 0
        state.selected_indices = {0}

        output = state.format_table()

        # Check header
        assert "Index" in output
        assert "Repo" in output
        assert "Branch" in output
        assert "PR#" in output
        assert "Status" in output
        assert "Checks" in output

        # Check rows
        assert "[✓]" in output  # Selected indicator
        assert "[1]" in output
        assert "repo1" in output
        assert "#123" in output
        assert "[ ]" in output  # Unselected indicator
        assert "[2]" in output


class TestHandleMerge:
    """Test merge action handler."""

    @patch("subprocess.run")
    def test_handle_merge_success(self, mock_run: Mock) -> None:
        """Test successful merge operation."""
        mock_run.return_value = Mock(returncode=0, stdout="Merged", stderr="")

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_merge(rows, skip_confirm=True, merge_strategy="squash")

        assert success == 1
        assert failure == 0

        # Verify gh CLI was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "pr" in call_args
        assert "merge" in call_args
        assert "123" in call_args
        assert "--squash" in call_args
        assert "--auto" in call_args

    @patch("subprocess.run")
    def test_handle_merge_no_pr(self, mock_run: Mock) -> None:
        """Test merge when no PR exists."""
        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        success, failure = handle_merge(rows, skip_confirm=True)

        assert success == 0
        assert failure == 1
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_handle_merge_failure(self, mock_run: Mock) -> None:
        """Test merge operation failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Merge conflict")

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_merge(rows, skip_confirm=True)

        assert success == 0
        assert failure == 1

    @patch("subprocess.run")
    def test_handle_merge_timeout(self, mock_run: Mock) -> None:
        """Test merge operation timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_merge(rows, skip_confirm=True)

        assert success == 0
        assert failure == 1

    @patch("subprocess.run")
    def test_handle_merge_multiple_repos(self, mock_run: Mock) -> None:
        """Test merging multiple PRs."""
        mock_run.side_effect = [
            Mock(returncode=0, stdout="Merged", stderr=""),
            Mock(returncode=0, stdout="Merged", stderr=""),
        ]

        pr_info1 = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature1",
            has_pr=True,
            pr_number=123,
        )
        pr_info2 = PrInfo(
            repo_path="/tmp/repo2",
            repo_url="https://github.com/org/repo2",
            branch="feature2",
            has_pr=True,
            pr_number=456,
        )

        rows = [
            PrTableRow(1, "repo1", "feature1", "main", "#123", "open", "passing", pr_info1),
            PrTableRow(2, "repo2", "feature2", "main", "#456", "open", "passing", pr_info2),
        ]

        success, failure = handle_merge(rows, skip_confirm=True, merge_strategy="merge")

        assert success == 2
        assert failure == 0
        assert mock_run.call_count == 2


class TestHandleClose:
    """Test close action handler."""

    @patch("subprocess.run")
    def test_handle_close_success(self, mock_run: Mock) -> None:
        """Test successful close operation."""
        mock_run.return_value = Mock(returncode=0, stdout="Closed", stderr="")

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_close(rows, skip_confirm=True)

        assert success == 1
        assert failure == 0
        mock_run.assert_called_once()

        # Verify gh CLI command
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "pr" in call_args
        assert "close" in call_args
        assert "123" in call_args

    @patch("subprocess.run")
    def test_handle_close_no_pr(self, mock_run: Mock) -> None:
        """Test close when no PR exists."""
        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        success, failure = handle_close(rows, skip_confirm=True)

        assert success == 0
        assert failure == 1
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_handle_close_failure(self, mock_run: Mock) -> None:
        """Test close operation failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Not found")

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_close(rows, skip_confirm=True)

        assert success == 0
        assert failure == 1


class TestHandleCreate:
    """Test create PR action handler."""

    @patch("click.prompt")
    @patch("subprocess.run")
    def test_handle_create_success(self, mock_run: Mock, mock_prompt: Mock) -> None:
        """Test successful PR creation."""
        mock_run.return_value = Mock(returncode=0, stdout="Created PR #789", stderr="")
        mock_prompt.return_value = "Test PR title"

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        success, failure = handle_create(
            rows, skip_confirm=True, title="Test PR", body="Description", base="main"
        )

        assert success == 1
        assert failure == 0
        mock_run.assert_called_once()

        # Verify gh CLI command
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "pr" in call_args
        assert "create" in call_args
        assert "--title" in call_args
        assert "Test PR" in call_args
        assert "--base" in call_args
        assert "main" in call_args
        assert "--body" in call_args
        assert "Description" in call_args

    @patch("subprocess.run")
    def test_handle_create_pr_already_exists(self, mock_run: Mock) -> None:
        """Test create when PR already exists."""
        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_create(rows, skip_confirm=True, title="Test PR")

        assert success == 0
        assert failure == 1
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_handle_create_failure(self, mock_run: Mock) -> None:
        """Test PR creation failure."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error creating PR")

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        success, failure = handle_create(rows, skip_confirm=True, title="Test PR", base="main")

        assert success == 0
        assert failure == 1


class TestHandleUpdateBranch:
    """Test branch update action handler."""

    @patch("qen.commands.pr_tui.restack_pr")
    @patch("qen.commands.pr_tui.parse_repo_owner_and_name")
    def test_handle_update_branch_success(self, mock_parse: Mock, mock_restack: Mock) -> None:
        """Test successful branch update operation."""
        mock_parse.return_value = ("org", "repo1")
        mock_restack.return_value = True

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_update_branch(rows, dry_run=False)

        assert success == 1
        assert failure == 0
        mock_parse.assert_called_once_with("https://github.com/org/repo1")
        mock_restack.assert_called_once_with("org", "repo1", 123, dry_run=False)

    @patch("qen.commands.pr_tui.restack_pr")
    @patch("qen.commands.pr_tui.parse_repo_owner_and_name")
    def test_handle_update_branch_no_pr(self, mock_parse: Mock, mock_restack: Mock) -> None:
        """Test branch update when no PR exists."""
        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        success, failure = handle_update_branch(rows, dry_run=False)

        assert success == 0
        assert failure == 1
        mock_parse.assert_not_called()
        mock_restack.assert_not_called()

    @patch("qen.commands.pr_tui.parse_repo_owner_and_name")
    def test_handle_update_branch_invalid_url(self, mock_parse: Mock) -> None:
        """Test branch update with invalid repo URL."""
        mock_parse.return_value = None

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="invalid-url",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_update_branch(rows, dry_run=False)

        assert success == 0
        assert failure == 1

    @patch("qen.commands.pr_tui.restack_pr")
    @patch("qen.commands.pr_tui.parse_repo_owner_and_name")
    def test_handle_update_branch_failure(self, mock_parse: Mock, mock_restack: Mock) -> None:
        """Test branch update operation failure."""
        mock_parse.return_value = ("org", "repo1")
        mock_restack.return_value = False

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_update_branch(rows, dry_run=False)

        assert success == 0
        assert failure == 1

    @patch("qen.commands.pr_tui.restack_pr")
    @patch("qen.commands.pr_tui.parse_repo_owner_and_name")
    def test_handle_update_branch_dry_run(self, mock_parse: Mock, mock_restack: Mock) -> None:
        """Test branch update in dry run mode."""
        mock_parse.return_value = ("org", "repo1")
        mock_restack.return_value = True

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        success, failure = handle_update_branch(rows, dry_run=True)

        assert success == 1
        assert failure == 0
        mock_restack.assert_called_once_with("org", "repo1", 123, dry_run=True)


class TestHandleStackView:
    """Test stack view action handler."""

    @patch("qen.commands.pr_tui.identify_stacks")
    def test_handle_stack_view_no_prs(self, mock_identify: Mock) -> None:
        """Test stack view when no PRs exist."""
        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=False,
        )
        rows = [PrTableRow(1, "repo1", "feature", "-", "-", "-", "-", pr_info)]

        # Should not raise error, just display message
        handle_stack_view(rows)

        # identify_stacks should not be called if no PRs
        mock_identify.assert_not_called()

    @patch("qen.commands.pr_tui.identify_stacks")
    def test_handle_stack_view_no_stacks(self, mock_identify: Mock) -> None:
        """Test stack view when no stacks found."""
        mock_identify.return_value = {}

        pr_info = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature",
            has_pr=True,
            pr_number=123,
            pr_base="main",
        )
        rows = [PrTableRow(1, "repo1", "feature", "main", "#123", "open", "passing", pr_info)]

        # Should not raise error
        handle_stack_view(rows)

        mock_identify.assert_called_once()

    @patch("qen.commands.pr_tui.format_stack_display")
    @patch("qen.commands.pr_tui.identify_stacks")
    def test_handle_stack_view_with_stacks(self, mock_identify: Mock, mock_format: Mock) -> None:
        """Test stack view with actual stacks."""
        pr_info1 = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature-1",
            has_pr=True,
            pr_number=123,
            pr_base="main",
        )
        pr_info2 = PrInfo(
            repo_path="/tmp/repo1",
            repo_url="https://github.com/org/repo1",
            branch="feature-2",
            has_pr=True,
            pr_number=456,
            pr_base="feature-1",
        )

        mock_identify.return_value = {"feature-1": [pr_info1, pr_info2]}
        mock_format.return_value = "Stack output"

        rows = [
            PrTableRow(1, "repo1", "feature-1", "main", "#123", "open", "passing", pr_info1),
            PrTableRow(2, "repo1", "feature-2", "feature-1", "#456", "open", "passing", pr_info2),
        ]

        handle_stack_view(rows)

        mock_identify.assert_called_once()
        mock_format.assert_called_once()


class TestPromptForAction:
    """Test action prompt."""

    @patch("click.prompt")
    def test_prompt_for_action_merge(self, mock_prompt: Mock) -> None:
        """Test selecting merge action."""
        mock_prompt.return_value = "m"

        result = prompt_for_action()

        assert result == "merge"

    @patch("click.prompt")
    def test_prompt_for_action_close(self, mock_prompt: Mock) -> None:
        """Test selecting close action."""
        mock_prompt.return_value = "c"

        result = prompt_for_action()

        assert result == "close"

    @patch("click.prompt")
    def test_prompt_for_action_create(self, mock_prompt: Mock) -> None:
        """Test selecting create action."""
        mock_prompt.return_value = "n"

        result = prompt_for_action()

        assert result == "create"

    @patch("click.prompt")
    def test_prompt_for_action_update(self, mock_prompt: Mock) -> None:
        """Test selecting branch update action."""
        mock_prompt.return_value = "u"

        result = prompt_for_action()

        assert result == "update"

    @patch("click.prompt")
    def test_prompt_for_action_stack(self, mock_prompt: Mock) -> None:
        """Test selecting stack view action."""
        mock_prompt.return_value = "s"

        result = prompt_for_action()

        assert result == "stack"

    @patch("click.prompt")
    def test_prompt_for_action_quit(self, mock_prompt: Mock) -> None:
        """Test quitting without action."""
        mock_prompt.return_value = "q"

        result = prompt_for_action()

        assert result is None

    @patch("click.prompt")
    def test_prompt_for_action_invalid(self, mock_prompt: Mock) -> None:
        """Test invalid action returns None."""
        mock_prompt.return_value = "invalid"

        result = prompt_for_action()

        assert result is None

    @patch("click.prompt")
    def test_prompt_for_action_case_insensitive(self, mock_prompt: Mock) -> None:
        """Test that action selection is case-insensitive."""
        mock_prompt.return_value = "M"

        result = prompt_for_action()

        assert result == "merge"

    @patch("click.prompt")
    def test_prompt_for_action_whitespace(self, mock_prompt: Mock) -> None:
        """Test that whitespace is stripped."""
        mock_prompt.return_value = "  m  "

        result = prompt_for_action()

        assert result == "merge"
