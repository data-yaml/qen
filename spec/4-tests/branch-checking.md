# Branch Checking for qen config Command

## Test Scenario: Branch Switching Validation

### Purpose
Verify that the `qen config` command correctly switches the current git branch when changing between projects.

### Motivation
Ensure that project context switching via `qen config` works as expected, maintaining the core promise of project-specific branches.

### Test Description

1. Initialize a meta repository
2. Create two distinct projects
3. Verify `qen config` switches the current git branch appropriately

### Success Criteria

- When calling `qen config <project1>`, the git branch changes to project1's branch
- When calling `qen config <project2>`, the git branch changes to project2's branch
- Branch names contain the respective project names
- Each branch switch is performed without errors

### Failure Conditions

- `qen config` fails to change the current git branch
- Branch names do not match the expected project names
- Branch switching causes unexpected git state changes

### Test Implementation

The test implementation is defined in `tests/integration/test_branch_checking.py`.

### Technical Details

- Uses unique project names to prevent test conflicts
- Relies on `run_qen()` helper to execute qen commands
- Uses subprocess to check current git branch
- Verifies branch switching via git branch name

### Related Commands

- `qen init`
- `qen config`
- `git branch`

### Assumptions

- A meta repository is available for testing
- Git is installed and configured
- The qen CLI is functional

### Open Questions

- How should branch naming handle very long project names?
- What happens with special characters in project names?

## Recommended Future Improvements

- Add test cases for edge case project names
- Implement stricter git branch naming validation
- Add logging for branch switching operations
