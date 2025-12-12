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

## Success Criteria

- All tests reside in either `tests/unit/` or `tests/integration/`
- No top-level `tests/qen/`, `tests/qenvy/`, `tests/schemas/` directories
- All tests pass after reorganization
- Test file locations clearly indicate their category (unit vs integration)

## Notes

- This is ONLY about directory reorganization
- Code quality issues within tests will be addressed AFTER this reorganization
- Focus on structural cleanup first, then content cleanup
