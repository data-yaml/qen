# Spec: Interactive PR Management with TUI

**Status:** Requirements (Desired End State)
**Created:** 2025-12-08
**Related:** `src/qen/commands/pr.py`, `feat(indices)`

## Problem

Currently `qen pr` has multiple subcommands (`status`, `stack`, `restack`) that serve different but overlapping purposes. The distinction between "observing PR state" and "coordinating PR actions" is unclear.

## Desired End State

### Two Commands with Clear Purposes

**`qen status`** - Observe current workspace state (per-repo view)

- Which branch am I on?
- Do I have uncommitted changes?
- Am I ahead/behind remote?
- **Is there a PR for this branch?** (basic info: PR#, state, checks)
- Output: Sequential list, one section per repo, scrollable

**`qen pr`** - Coordinate PR operations across repos (cross-repo view)

- Interactive TUI displaying all repos and their PR status
- Select repos, choose action, system prompts for inputs
- Mechanical operations: merge, close, restack, create
- Output: Interactive table with selection

### The Key Distinction

- `qen status` = **observation** (read-only, informational)
- `qen pr` = **orchestration** (actions, human-in-the-loop)

## Interactive PR Manager Requirements

### Display: Table with Index-First Column

When user runs `qen pr`, show:

```text
Index | Repo       | Branch      | PR#  | Status | Checks
1     | foo        | feat-auth   | 123  | open   | passing
2     | bar        | feat-ui     | -    | -      | -
3     | baz        | fix-bug     | 124  | open   | failing
4     | deployment | main        | -    | -      | -
```

- **Index column is first** (allows `qen pr 1 3` style operations)
- Show all repos in project (including those without PRs)
- `-` indicates no PR exists for that branch

### Navigation

- Arrow keys: move up/down between rows
- Space: toggle selection (multi-select)
- Enter: confirm selection and proceed to action
- `q` or `Esc`: quit without action

### Action Selection

After user selects repo(s), system prompts:

```text
What do you want to do?
  [m] Merge PR(s)
  [c] Close PR(s)
  [r] Restack PR(s)
  [s] View stack relationships
  [n] Create new PR
```

### Input Prompts (Human-in-the-Loop)

System prompts for required information:

**For merge:**

- Confirm: "Merge PR #123 (foo/feat-auth)? [y/N]"
- Merge strategy if needed: "Merge method? [s]quash / [m]erge / [r]ebase"

**For close:**

- Confirm: "Close PR #123 without merging? [y/N]"
- Optional comment: "Reason for closing (optional):"

**For create (when repo has no PR):**

- Title: "PR title:"
- Body: "PR description (optional, opens editor if empty):"
- Base branch: "Base branch [main]:"

**For restack:**

- Confirm: "Update PR #123 to latest base? [y/N]"

### Flags to Skip Prompts

Allow pre-specifying choices:

```bash
qen pr --action merge --yes           # Select, action, no confirmation
qen pr 1 3 --action merge --yes       # Pre-select repos by index
qen pr --action merge --strategy squash --yes
qen pr --action create --title "..." --body "..."
```

### No PR Handling

When user selects a repo with no PR and chooses action:

- Merge/Close/Restack: "Error: No PR exists for foo/feat-auth"
- Create: Prompt for title/body, then `gh pr create`

### Multi-Repo Operations

When multiple repos selected:

- Show summary: "Selected 3 repos: foo, bar, baz"
- Prompt once for action
- Apply to all (with individual confirmations unless `--yes`)
- Show results: "✓ Merged 2 PRs, ✗ 1 failed"

### Stack View Integration

When user chooses "View stack relationships":

- Show current selection in stack context
- Display tree view (similar to current `qen pr stack` output)
- Allow returning to table or selecting stack operations

## Implementation Constraints

- Keep it really simple
- Use arrow keys + enter for selection
- System prompts user for any missing information
- `--yes` flag skips all confirmations
- Flags can pre-specify action, inputs, strategy

## Success Criteria

1. User can run `qen pr` and see all repos + PR status in a table
2. User can select repo(s) with arrow keys and space/enter
3. System prompts for action if not specified via `--action` flag
4. System prompts for required inputs if not specified via flags
5. System confirms before destructive operations unless `--yes`
6. User can create PR by prompting human for title/body
7. Multi-select works for batch operations
8. Repos without PRs are shown and can be selected to create PR

## Out of Scope

- GenAI-generated PR titles/descriptions (human provides text)
- Auto-approval (always require human decision, unless --yes)
- Complex merge conflict resolution
- PR review/comment features (use GitHub UI)
- Async operations or progress bars (keep it synchronous + simple)
