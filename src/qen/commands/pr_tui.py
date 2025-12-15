"""Interactive TUI for PR management using prompt_toolkit.

Provides an interactive table interface for selecting repositories and performing
PR operations (merge, close, create, restack, view stack).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Container, HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl

from .pr import (
    PrInfo,
    format_stack_display,
    identify_stacks,
    parse_repo_owner_and_name,
    restack_pr,
)


@dataclass
class PrTableRow:
    """Represents a row in the PR table for display."""

    index: int
    repo_name: str
    branch: str
    pr_base: str  # Base branch for the PR (or "-" if no PR)
    pr_number: str  # Can be "-" if no PR
    pr_state: str  # Can be "-" if no PR
    checks: str  # Can be "-" if no PR
    pr_info: PrInfo  # Original PrInfo object for operations


class PrTableState:
    """Manages the state of the PR table UI."""

    def __init__(self, rows: list[PrTableRow]) -> None:
        """Initialize table state.

        Args:
            rows: List of table rows to display
        """
        self.rows = rows
        self.current_row = 0
        self.selected_indices: set[int] = set()

    def move_up(self) -> None:
        """Move cursor up one row."""
        if self.current_row > 0:
            self.current_row -= 1

    def move_down(self) -> None:
        """Move cursor down one row."""
        if self.current_row < len(self.rows) - 1:
            self.current_row += 1

    def toggle_selection(self) -> None:
        """Toggle selection of current row."""
        if self.current_row in self.selected_indices:
            self.selected_indices.remove(self.current_row)
        else:
            self.selected_indices.add(self.current_row)

    def get_selected_rows(self) -> list[PrTableRow]:
        """Get list of selected rows.

        Returns:
            List of selected PrTableRow objects
        """
        return [self.rows[i] for i in sorted(self.selected_indices)]

    def format_table(self) -> str:
        """Format the table for display.

        Returns:
            Formatted table string with ANSI escape codes
        """
        lines = []

        # Header
        header = (
            f"{'Index':<7} {'Repo':<20} {'Branch':<20} {'Base':<15} "
            f"{'PR#':<8} {'Status':<10} {'Checks':<12}"
        )
        lines.append(header)
        lines.append("-" * len(header))

        # Rows
        for i, row in enumerate(self.rows):
            # Selection indicator
            sel = "[✓]" if i in self.selected_indices else "[ ]"

            # Cursor indicator
            cursor = ">" if i == self.current_row else " "

            # Format row
            repo_short = row.repo_name[:18] + ".." if len(row.repo_name) > 20 else row.repo_name
            branch_short = row.branch[:18] + ".." if len(row.branch) > 20 else row.branch
            base_short = row.pr_base[:13] + ".." if len(row.pr_base) > 15 else row.pr_base

            # Color coding for checks
            checks_display = row.checks
            if row.checks == "passing":
                checks_display = f"\033[32m{row.checks}\033[0m"  # Green
            elif row.checks == "failing":
                checks_display = f"\033[31m{row.checks}\033[0m"  # Red
            elif row.checks == "pending":
                checks_display = f"\033[33m{row.checks}\033[0m"  # Yellow

            line = (
                f"{cursor} {sel} [{row.index}]   {repo_short:<20} {branch_short:<20} "
                f"{base_short:<15} {row.pr_number:<8} {row.pr_state:<10} {checks_display}"
            )
            lines.append(line)

        return "\n".join(lines)


def build_pr_table(pr_infos: list[PrInfo]) -> list[PrTableRow]:
    """Build table rows from PR information.

    Args:
        pr_infos: List of PrInfo objects

    Returns:
        List of PrTableRow objects for display
    """
    rows = []
    for idx, pr_info in enumerate(pr_infos, start=1):
        # Extract repo name from path
        repo_name = pr_info.repo_path

        # Format PR number, state, checks, and base
        pr_number = f"#{pr_info.pr_number}" if pr_info.has_pr and pr_info.pr_number else "-"

        # Show draft status in state column
        if pr_info.has_pr and pr_info.pr_state:
            pr_state = pr_info.pr_state
            if pr_info.is_draft:
                pr_state = f"{pr_state} (draft)"
        else:
            pr_state = "-"

        checks = pr_info.pr_checks if pr_info.has_pr and pr_info.pr_checks else "-"
        pr_base = pr_info.pr_base if pr_info.has_pr and pr_info.pr_base else "-"

        rows.append(
            PrTableRow(
                index=idx,
                repo_name=repo_name,
                branch=pr_info.branch,
                pr_base=pr_base,
                pr_number=pr_number,
                pr_state=pr_state,
                checks=checks,
                pr_info=pr_info,
            )
        )

    return rows


def display_interactive_table(pr_infos: list[PrInfo]) -> list[PrTableRow] | None:
    """Display interactive PR table and return selected rows.

    Args:
        pr_infos: List of PrInfo objects to display

    Returns:
        List of selected PrTableRow objects, or None if user quit
    """
    rows = build_pr_table(pr_infos)
    state = PrTableState(rows)

    # Build key bindings
    kb = KeyBindings()

    @kb.add("up")
    def _(event: Any) -> None:
        """Move cursor up."""
        state.move_up()

    @kb.add("down")
    def _(event: Any) -> None:
        """Move cursor down."""
        state.move_down()

    @kb.add("space")
    def _(event: Any) -> None:
        """Toggle selection."""
        state.toggle_selection()

    @kb.add("enter")
    def _(event: Any) -> None:
        """Confirm selection and exit."""
        event.app.exit(result=state.get_selected_rows())

    @kb.add("q")
    @kb.add("escape")
    def _(event: Any) -> None:
        """Quit without selection."""
        event.app.exit(result=None)

    # Create layout
    def get_text() -> str:
        """Get current table text."""
        return (
            state.format_table()
            + "\n\n"
            + "Controls: ↑/↓ navigate, Space select, Enter confirm, q/Esc quit"
        )

    text_area = FormattedTextControl(text=get_text)
    window = Window(content=text_area, wrap_lines=False)
    container: Container = HSplit([window])
    layout = Layout(container)

    # Create application
    app: Application[list[PrTableRow] | None] = Application(
        layout=layout, key_bindings=kb, full_screen=False, mouse_support=False
    )

    # Run application
    result = app.run()
    return result


def prompt_for_action() -> str | None:
    """Prompt user to select an action.

    Returns:
        Action name ('merge', 'close', 'create', 'update', 'stack', or None if cancelled)
    """
    click.echo("\nWhat do you want to do?")
    click.echo("  [m] Merge PR(s)")
    click.echo("  [c] Close PR(s)")
    click.echo("  [n] Create new PR")
    click.echo("  [u] Update branch (sync with base)")
    click.echo("  [s] View stack relationships")
    click.echo("  [q] Cancel")

    choice = click.prompt("Choose action", type=str, default="q").lower().strip()

    action_map = {
        "m": "merge",
        "c": "close",
        "n": "create",
        "u": "update",
        "s": "stack",
        "q": None,
    }

    return action_map.get(choice, None)


def handle_merge(
    selected_rows: list[PrTableRow],
    skip_confirm: bool = False,
    merge_strategy: str | None = None,
) -> tuple[int, int]:
    """Handle merge operation for selected repositories.

    Args:
        selected_rows: List of selected table rows
        skip_confirm: If True, skip confirmation prompts
        merge_strategy: Merge strategy (squash/merge/rebase), or None to prompt

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    for row in selected_rows:
        pr_info = row.pr_info

        # Verify PR exists
        if not pr_info.has_pr or not pr_info.pr_number:
            click.echo(f"✗ [{row.index}] {row.repo_name}: No PR exists", err=True)
            failure_count += 1
            continue

        # Confirm merge
        if not skip_confirm:
            confirm = click.confirm(
                f"Merge PR #{pr_info.pr_number} ({row.repo_name}/{row.branch})?",
                default=False,
            )
            if not confirm:
                click.echo(f"  Skipped [{row.index}] {row.repo_name}")
                failure_count += 1
                continue

        # Determine merge strategy
        strategy = merge_strategy
        if not strategy and not skip_confirm:
            strategy = click.prompt(
                "Merge method",
                type=click.Choice(["squash", "merge", "rebase"]),
                default="squash",
            )

        # Execute merge via gh CLI
        try:
            cmd = ["gh", "pr", "merge", str(pr_info.pr_number)]
            if strategy:
                cmd.append(f"--{strategy}")
            if skip_confirm:
                cmd.append("--auto")

            result = subprocess.run(
                cmd,
                cwd=Path(pr_info.repo_path).parent,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                click.echo(f"✓ [{row.index}] Merged PR #{pr_info.pr_number}")
                success_count += 1
            else:
                click.echo(
                    f"✗ [{row.index}] Failed to merge PR #{pr_info.pr_number}: {result.stderr}",
                    err=True,
                )
                failure_count += 1

        except subprocess.TimeoutExpired:
            click.echo(f"✗ [{row.index}] Timeout merging PR #{pr_info.pr_number}", err=True)
            failure_count += 1
        except Exception as e:
            click.echo(f"✗ [{row.index}] Error: {e}", err=True)
            failure_count += 1

    return (success_count, failure_count)


def handle_close(selected_rows: list[PrTableRow], skip_confirm: bool = False) -> tuple[int, int]:
    """Handle close operation for selected repositories.

    Args:
        selected_rows: List of selected table rows
        skip_confirm: If True, skip confirmation prompts

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    for row in selected_rows:
        pr_info = row.pr_info

        # Verify PR exists
        if not pr_info.has_pr or not pr_info.pr_number:
            click.echo(f"✗ [{row.index}] {row.repo_name}: No PR exists", err=True)
            failure_count += 1
            continue

        # Confirm close
        if not skip_confirm:
            confirm = click.confirm(
                f"Close PR #{pr_info.pr_number} without merging ({row.repo_name})?",
                default=False,
            )
            if not confirm:
                click.echo(f"  Skipped [{row.index}] {row.repo_name}")
                failure_count += 1
                continue

        # Optional comment
        comment = None
        if not skip_confirm:
            comment = click.prompt("Reason for closing (optional)", default="", show_default=False)

        # Execute close via gh CLI
        try:
            cmd = ["gh", "pr", "close", str(pr_info.pr_number)]
            if comment:
                cmd.extend(["--comment", comment])

            result = subprocess.run(
                cmd,
                cwd=Path(pr_info.repo_path).parent,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                click.echo(f"✓ [{row.index}] Closed PR #{pr_info.pr_number}")
                success_count += 1
            else:
                click.echo(
                    f"✗ [{row.index}] Failed to close PR #{pr_info.pr_number}: {result.stderr}",
                    err=True,
                )
                failure_count += 1

        except subprocess.TimeoutExpired:
            click.echo(f"✗ [{row.index}] Timeout closing PR #{pr_info.pr_number}", err=True)
            failure_count += 1
        except Exception as e:
            click.echo(f"✗ [{row.index}] Error: {e}", err=True)
            failure_count += 1

    return (success_count, failure_count)


def handle_create(
    selected_rows: list[PrTableRow],
    skip_confirm: bool = False,
    title: str | None = None,
    body: str | None = None,
    base: str | None = None,
    draft: bool = True,
) -> tuple[int, int]:
    """Handle create PR operation for selected repositories.

    Args:
        selected_rows: List of selected table rows
        skip_confirm: If True, skip confirmation prompts
        title: PR title (if None, prompt user)
        body: PR body (if None, prompt user)
        base: Base branch (if None, use default)
        draft: Create as draft PR (default: True)

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    for row in selected_rows:
        pr_info = row.pr_info

        # Verify NO PR exists
        if pr_info.has_pr:
            click.echo(f"✗ [{row.index}] {row.repo_name}: PR already exists", err=True)
            failure_count += 1
            continue

        # Get PR title
        pr_title = title
        if not pr_title:
            pr_title = click.prompt(f"PR title for [{row.index}] {row.repo_name}", type=str)

        # Get PR body
        pr_body = body
        if not pr_body and not skip_confirm:
            pr_body = click.prompt(
                "PR description (optional)", default="", show_default=False, type=str
            )

        # Get base branch - use repo's default_branch
        repo_default = getattr(pr_info, "default_branch", "main")
        pr_base = base or repo_default
        if not base and not skip_confirm:
            pr_base = click.prompt("Base branch", default=repo_default, type=str)

        # Execute create via gh CLI
        try:
            cmd = ["gh", "pr", "create", "--title", pr_title, "--base", pr_base]
            if pr_body:
                cmd.extend(["--body", pr_body])
            if draft:
                cmd.append("--draft")

            result = subprocess.run(
                cmd,
                cwd=Path(pr_info.repo_path).parent,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                click.echo(f"✓ [{row.index}] Created PR for {row.repo_name}")
                success_count += 1
            else:
                click.echo(
                    f"✗ [{row.index}] Failed to create PR: {result.stderr}",
                    err=True,
                )
                failure_count += 1

        except subprocess.TimeoutExpired:
            click.echo(f"✗ [{row.index}] Timeout creating PR", err=True)
            failure_count += 1
        except Exception as e:
            click.echo(f"✗ [{row.index}] Error: {e}", err=True)
            failure_count += 1

    return (success_count, failure_count)


def handle_update_branch(selected_rows: list[PrTableRow], dry_run: bool = False) -> tuple[int, int]:
    """Handle branch update operation for selected repositories.

    Updates the branch to sync with its base branch. When a PR exists, uses GitHub's
    update-branch API to merge the latest base branch changes.

    Args:
        selected_rows: List of selected table rows
        dry_run: If True, show what would be done without making changes

    Returns:
        Tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    for row in selected_rows:
        pr_info = row.pr_info

        # Verify PR exists
        if not pr_info.has_pr or not pr_info.pr_number:
            click.echo(f"✗ [{row.index}] {row.repo_name}: No PR exists", err=True)
            failure_count += 1
            continue

        # Parse owner and repo from URL
        parsed = parse_repo_owner_and_name(pr_info.repo_url)
        if not parsed:
            click.echo(f"✗ [{row.index}] Failed to parse repo URL", err=True)
            failure_count += 1
            continue

        owner, repo = parsed
        click.echo(
            f"[{row.index}] Updating branch for PR #{pr_info.pr_number} ({row.repo_name})..."
        )

        # Call update function
        success = restack_pr(owner, repo, pr_info.pr_number, dry_run=dry_run)
        if success:
            success_count += 1
        else:
            failure_count += 1

    return (success_count, failure_count)


def handle_stack_view(selected_rows: list[PrTableRow]) -> None:
    """Display stack relationships for selected repositories.

    Args:
        selected_rows: List of selected table rows
    """
    # Get PrInfo objects for selected rows
    pr_infos = [row.pr_info for row in selected_rows]

    # Filter to only PRs that exist
    prs_with_pr = [pr for pr in pr_infos if pr.has_pr]

    if not prs_with_pr:
        click.echo("No PRs found in selected repositories.")
        return

    # Identify stacks
    stacks = identify_stacks(prs_with_pr)

    if not stacks:
        click.echo("No stacks found in selected repositories.")
        click.echo("\nStacks are identified when a PR's base branch is another feature branch.")
        return

    # Display stacks
    click.echo("\nStacked PRs:")
    click.echo(format_stack_display(stacks, verbose=False))
