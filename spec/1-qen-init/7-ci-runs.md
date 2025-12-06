# CI Workflow Execution Analysis

## Problem Statement

GitHub Actions workflows can trigger multiple times for the same code change, wasting CI resources and creating confusion. We need to understand when each workflow runs and optimize for efficiency.

## Current State (After Recent Changes)

### test.yml
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: ["**"]
```

**Triggers:**
- Push to `main` branch
- Any PR update (create/push/sync)

### publish.yml
```yaml
on:
  push:
    tags: ['v*']
    branches: ['*']
  workflow_dispatch:
```

**Triggers:**
- Push to ANY branch
- Push any tag matching `v*`
- Manual workflow dispatch

## Execution Matrix

| Scenario | test.yml | publish.yml | Total Runs | Notes |
|----------|----------|-------------|------------|-------|
| Push to feature branch (no PR) | ❌ 0 | ✅ 1 (build) | **1** | OK - pre-commit hooks test locally |
| Create PR | ✅ 1 (PR) | ❌ 0 | **1** | Good - no branch trigger |
| Push to PR branch | ✅ 1 (PR) | ✅ 1 (build) | **2** | DUPLICATE - both workflows run |
| Merge PR to main | ✅ 1 (push) | ✅ 1 (build) | **2** | Expected - validates main |
| Push tag `v0.1.3` | ❌ 0 | ✅ 1 (publish) | **1** | Good - only publishes |
| Push tag `v0.1.3-dev.*` | ❌ 0 | ✅ 1 (test-pypi) | **1** | Good - only test publishes |

### Issue: Row 3 - Push to PR Branch

When you push commits to a branch with an open PR:
- `test.yml` runs via `pull_request` trigger
- `publish.yml` runs via `push.branches: ['*']` trigger
- Both build the package (redundant)
- `publish.yml` uploads artifacts but doesn't publish (wasteful)

## GitHub Actions Best Practices

### 1. Avoid Duplicate Runs

**Problem:** Both `push` and `pull_request` triggers on same branch = 2x runs

**Solutions:**
- **Option A:** Only `pull_request` (requires PRs for all work)
- **Option B:** Only `push` (less visibility in PR UI)
- **Option C:** Use `concurrency` groups to cancel redundant runs
- **Option D:** Conditional logic to skip duplicate contexts

### 2. Separate Concerns

Different workflows for different purposes:
- **CI Testing:** Run on PRs and main
- **Build Artifacts:** Only when needed (releases)
- **Publishing:** Only on tags

### 3. Resource Efficiency

- Don't build artifacts on every branch push
- Use short retention for temporary artifacts
- Cancel in-progress runs when new commits arrive

## Optimal State

### test.yml (CI Testing)
```yaml
name: Test

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true

jobs:
  test:
    # ... existing test matrix ...

  lint:
    # ... existing lint job ...

  # REMOVE build job - it's redundant with publish.yml
```

**Changes:**
- ✅ Add `concurrency` to cancel old runs when new commits pushed
- ✅ `pull_request` only targets `main` (can expand if needed)
- ✅ Remove `build` job (already in publish.yml)

### publish.yml (Build & Publish)
```yaml
name: Publish Python Package

on:
  push:
    tags: ['v*']           # Keep: needed for releases
    # REMOVE branches: ['*'] - wasteful
  pull_request:             # ADD: build artifacts for PRs
    branches: [main]
  workflow_dispatch:        # Keep: manual releases

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true

jobs:
  build:
    name: Build distribution
    # ... existing build steps ...

  publish-to-pypi:
    if: startsWith(github.ref, 'refs/tags/') && !contains(github.ref, '-dev')
    # ... existing publish steps ...

  publish-to-testpypi:
    if: startsWith(github.ref, 'refs/tags/') && contains(github.ref, '-dev')
    # ... existing publish steps ...
```

**Changes:**
- ❌ Remove `branches: ['*']` - only build when needed
- ✅ Add `pull_request` trigger - build artifacts for PRs targeting main
- ✅ Add `concurrency` to cancel redundant builds

## Optimized Execution Matrix

| Scenario | test.yml | publish.yml | Total Runs | Notes |
|----------|----------|-------------|------------|-------|
| Push to feature branch (no PR) | ❌ 0 | ❌ 0 | **0** | OK - pre-commit hooks test locally |
| Create PR to main | ✅ 1 (test+lint) | ✅ 1 (build) | **2** | Different jobs, both needed |
| Push to PR branch | ✅ 1 (test+lint) | ✅ 1 (build) | **2** | Different jobs, cancels old runs |
| Merge PR to main | ✅ 1 (test+lint) | ❌ 0 | **1** | IMPROVED - no redundant build |
| Push tag `v0.1.3` | ❌ 0 | ✅ 1 (build+publish) | **1** | Good - release flow |
| Push tag `v0.1.3-dev.*` | ❌ 0 | ✅ 1 (build+testpypi) | **1** | Good - dev release flow |

### Key Improvements

1. **Row 1:** Feature branches without PRs don't waste CI (hooks test locally)
2. **Row 3:** Cancels old runs when pushing new commits (saves resources)
3. **Row 4:** Merge to main only runs tests, not build (build happens on tag)
4. **Row 2-3:** PR gets both test AND build, showing both pass before merge

## Alternative: Simpler Approach

If we don't need artifacts for PRs:

### test.yml (keeps build job)
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.head_ref || github.run_id }}
  cancel-in-progress: true
```

### publish.yml (only tags)
```yaml
on:
  push:
    tags: ['v*']
  workflow_dispatch:

# No concurrency needed - tags are immutable
```

**Result:**
- PRs only run `test.yml` (test + lint + build)
- Merges to main only run `test.yml`
- Tags trigger `publish.yml` (build + publish)
- Cleaner separation, less duplication

## Recommendation

**Use the Simpler Approach:**

1. **test.yml:** Test + Lint + Build on PRs and main
   - Add `concurrency` to cancel old runs
   - Restrict `pull_request` to `branches: [main]`

2. **publish.yml:** Only tags and manual dispatch
   - Remove `branches: ['*']`
   - Keep tag-based publishing logic

**Why:**
- Clear separation: test.yml = CI, publish.yml = release
- No redundant runs on main branch
- Artifacts built on every PR (catches packaging issues early)
- Tags get fresh build + publish in one workflow

## Implementation

1. Update `test.yml` to add concurrency and restrict PR branches
2. Update `publish.yml` to remove `branches: ['*']`
3. Test with next PR push to verify single workflow run
4. Verify tag-based release still works

## References

- [GitHub Actions: Workflow triggers](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows)
- [GitHub Actions: Concurrency](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#concurrency)
- [Best practices for avoiding duplicate workflow runs](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#running-your-workflow-only-when-a-push-affects-specific-files)
