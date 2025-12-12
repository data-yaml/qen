# DEPRECATED - See 08-integration-test-overhaul.md

**This document has been superseded by a more comprehensive plan.**

**Date:** 2025-12-11 (Deprecated same day)
**Status:** Replaced
**See instead:** [08-integration-test-overhaul.md](./08-integration-test-overhaul.md)

---

## Why This Plan Was Too Timid

This original plan identified problems in 30 tests across 3-4 files. It proposed shared fixtures to eliminate duplication.

**What it missed:**

The ENTIRE integration test suite (9 files, 3,873 lines) has systemic duplication:

- ~1,500 lines of copy-paste setup code (38% duplication!)
- 17+ instances of the same meta repo setup block
- Wrong remote URLs everywhere
- No single source of truth

**The real problem is much bigger than this plan addressed.**

---

## The Comprehensive Solution

See [08-integration-test-overhaul.md](./08-integration-test-overhaul.md) for:

1. **Full scope analysis** - All 9 test files, 1,500+ lines of duplication
2. **Complete fixture architecture** - 3 composable fixtures that eliminate ALL duplication
3. **File-by-file migration plan** - Concrete steps for each of 5 files
4. **Before/after examples** - 82 lines → 25 lines per test
5. **Code metrics** - 43% reduction in test code, 100% elimination of duplication
6. **5-hour timeline** - Realistic estimate with phase breakdown

---

## Key Insight

The problem isn't just "some tests have duplication."

The problem is "the entire integration test suite is 38% duplicated setup code."

That requires a comprehensive overhaul, not incremental fixes.

---

**READ:** [08-integration-test-overhaul.md](./08-integration-test-overhaul.md)
