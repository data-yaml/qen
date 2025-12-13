# Tech Debt: Test Organization

**Reorganize the tests/ directory to match the canonical structure defined in CLAUDE.md, eliminating inconsistent folder organization and clarifying unit vs integration test separation.**

## Problem Statement

The test directory structure is inconsistent and violates the canonical structure defined in CLAUDE.md.

## Current State (Inconsistent)

```tree
tests/
├── unit/           # Some unit tests here
│   └── qen/
├── qen/            # More tests here (unclear category)
│   └── commands/
├── qenvy/          # Qenvy tests (outside unit/)
├── integration/    # Integration tests
├── fixtures/       # Test fixtures
├── helpers/        # Test helpers
└── schemas/        # Schema tests
```

## Target State (Per CLAUDE.md)

```tree
tests/
├── unit/           # Unit tests (mocks OK)
│   ├── qen/
│   └── qenvy/
└── integration/    # Integration tests (NO MOCKS)
```

## Detailed Reorganization Plan

### Test File Locations

#### Unit Tests to Move

1. From `/tests/qen/` to `/tests/unit/qen/`
   - `test_add.py`
   - `test_config.py`
   - `test_git_status.py`
   - `test_init.py`
   - `test_pull.py`

2. From `/tests/qen/commands/` to `/tests/unit/qen/commands/`
   - `test_config.py`
   - `test_pr.py`
   - `test_pr_tui.py`
   - `test_sh.py`
   - `test_status.py`

#### Integration Tests (Verified Location)

- `/tests/integration/` is already correctly located
  - Includes: `test_add.py`, `test_branch_checking.py`, `test_github_schema.py`, `test_init.py`, `test_pr_status.py`, `test_pull.py`, `test_qen_wrapper.py`, `test_rm.py`, `test_status.py`

#### Support Files to Reorganize

1. Move `/tests/helpers/` contents
   - `github_mock.py` → `/tests/unit/helpers/`
   - `qenvy_test.py` → `/tests/unit/helpers/`
   - `test_mock.py` → `/tests/unit/helpers/`
   - `test_qenvy_test.py` → `/tests/unit/helpers/`

2. Move `/tests/fixtures/`
   - `github_fixtures.py` → `/tests/unit/fixtures/`

3. Move `/tests/schemas/`
   - `github_pr.py` → `/tests/unit/schemas/`

### Reorganization Strategy

#### Import Statement Updates

1. Update imports in all test files to reflect new directory structure
   - Replace `from tests.qen.` with `from tests.unit.qen.`
   - Replace `from tests.helpers.` with `from tests.unit.helpers.`
   - Replace `from tests.fixtures.` with `from tests.unit.fixtures.`
   - Replace `from tests.schemas.` with `from tests.unit.schemas.`

#### Execution Plan

1. Create new directory structure

```bash
mkdir -p /Users/ernest/GitHub/qen/tests/unit/qen/commands
mkdir -p /Users/ernest/GitHub/qen/tests/unit/helpers
mkdir -p /Users/ernest/GitHub/qen/tests/unit/fixtures
mkdir -p /Users/ernest/GitHub/qen/tests/unit/schemas
```

2. Move files with preservation of git history

```bash
# Unit Tests in main qen directory
git mv tests/qen/test_add.py tests/unit/qen/
git mv tests/qen/test_config.py tests/unit/qen/
git mv tests/qen/test_git_status.py tests/unit/qen/
git mv tests/qen/test_init.py tests/unit/qen/
git mv tests/qen/test_pull.py tests/unit/qen/

# Command Tests
git mv tests/qen/commands/test_config.py tests/unit/qen/commands/
git mv tests/qen/commands/test_pr.py tests/unit/qen/commands/
git mv tests/qen/commands/test_pr_tui.py tests/unit/qen/commands/
git mv tests/qen/commands/test_sh.py tests/unit/qen/commands/
git mv tests/qen/commands/test_status.py tests/unit/qen/commands/

# Helpers
git mv tests/helpers/github_mock.py tests/unit/helpers/
git mv tests/helpers/qenvy_test.py tests/unit/helpers/
git mv tests/helpers/test_mock.py tests/unit/helpers/
git mv tests/helpers/test_qenvy_test.py tests/unit/helpers/

# Fixtures and Schemas
git mv tests/fixtures/github_fixtures.py tests/unit/fixtures/
git mv tests/schemas/github_pr.py tests/unit/schemas/
```

3. Validate Imports
   - Use `./poe test-fast` to quickly validate imports
   - Run global search and replace for import statements

4. Final Validation

```bash
./poe test  # Run full test suite
./poe lint  # Validate code style
```

## Required Actions

1. **Audit all test files** - Determine which are unit tests vs integration tests
2. **Move tests/qen/ files** - Relocate to either `tests/unit/qen/` or `tests/integration/`
3. **Move tests/qenvy/ files** - Relocate to `tests/unit/qenvy/`
4. **Handle special directories**:
   - `tests/fixtures/` - Move to `tests/unit/fixtures/` or inline if unused
   - `tests/helpers/` - Move to `tests/unit/helpers/` or inline if unused
   - `tests/schemas/` - Move to `tests/unit/schemas/` or delete if obsolete
5. **Update imports** - Fix all test imports after reorganization
6. **Verify tests pass** - Run `./poe test-all` after reorganization
7. **Remove empty folders**

## Success Criteria

- All tests reside in either `tests/unit/` or `tests/integration/`
- No top-level `tests/qen/`, `tests/qenvy/`, `tests/schemas/` directories
- All tests pass after reorganization
- Test file locations clearly indicate their category (unit vs integration)

## Post-Reorganization Checklist

- [ ] All test files moved to correct locations
- [ ] Import statements updated
- [ ] No broken imports or references
- [ ] Full test suite passes
- [ ] No loss of git history for moved files

## Potential Risks

1. Import statement resolution
2. Potential breaking changes in pytest discovery
3. Maintaining consistent module references

## Recommended Next Steps

1. Perform reorganization during a low-activity development period
2. Communicate changes to all team members
3. Update any documentation referencing test file locations
4. Consider adding a migration script to help developers update local checkouts

## Notes

- This is ONLY about directory reorganization
- Code quality issues within tests will be addressed AFTER this reorganization
- Focus on structural cleanup first, then content cleanup
