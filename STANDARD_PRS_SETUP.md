# Standard PR Setup for Integration Tests

This document describes the one-time setup required to create standard reference PRs for fast integration testing.

## Current Status

**TODO:** The following standard PRs need to be created in `data-yaml/qen-test`

## Required Standard PRs

### PR #7: Passing Checks
- **Branch:** `ref-passing-checks`
- **Base:** `main`
- **Title:** "Reference: Passing Checks"
- **Body:** "Permanent reference PR for integration tests. DO NOT CLOSE. This PR should always have passing checks."
- **Purpose:** Test PR reading with passing checks (no `-failing-` in branch name)

### PR #8: Failing Checks
- **Branch:** `ref-failing-checks`
- **Base:** `main`
- **Title:** "Reference: Failing Checks"
- **Body:** "Permanent reference PR for integration tests. DO NOT CLOSE. This PR should always have failing checks due to branch name pattern."
- **Purpose:** Test PR reading with failing checks (branch contains `-failing-`)

### PR #9: Issue Pattern
- **Branch:** `ref-issue-456-test`
- **Base:** `main`
- **Title:** "Reference: Issue Pattern"
- **Body:** "Permanent reference PR for integration tests. DO NOT CLOSE. This PR tests issue number extraction from branch name."
- **Purpose:** Test issue number extraction from branch name pattern

### PR #10-12: Stacked PRs
- **PR #10:**
  - **Branch:** `ref-stack-a`
  - **Base:** `main`
  - **Title:** "Reference: Stack A"
  - **Body:** "Part of stacked PR reference. DO NOT CLOSE."

- **PR #11:**
  - **Branch:** `ref-stack-b`
  - **Base:** `ref-stack-a`
  - **Title:** "Reference: Stack B"
  - **Body:** "Part of stacked PR reference. DO NOT CLOSE."

- **PR #12:**
  - **Branch:** `ref-stack-c`
  - **Base:** `ref-stack-b`
  - **Title:** "Reference: Stack C"
  - **Body:** "Part of stacked PR reference. DO NOT CLOSE."

- **Purpose:** Test stacked PR detection

## Setup Commands

Run these commands in the `data-yaml/qen-test` repository:

```bash
# Navigate to qen-test repository
cd /tmp
git clone https://github.com/data-yaml/qen-test
cd qen-test

# Configure git
git config user.email "ernest@quilt.bio"
git config user.name "Ernest Prabhakar"

# PR #7: Passing Checks
git checkout main
git pull
git checkout -b ref-passing-checks
echo "# Reference: Passing Checks" > test-data/ref-passing.txt
git add test-data/ref-passing.txt
git commit -m "Add reference PR for passing checks"
git push -u origin ref-passing-checks
gh pr create --base main --head ref-passing-checks \
  --title "Reference: Passing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE. This PR should always have passing checks."

# PR #8: Failing Checks
git checkout main
git checkout -b ref-failing-checks
echo "# Reference: Failing Checks" > test-data/ref-failing.txt
git add test-data/ref-failing.txt
git commit -m "Add reference PR for failing checks"
git push -u origin ref-failing-checks
gh pr create --base main --head ref-failing-checks \
  --title "Reference: Failing Checks" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE. This PR should always have failing checks due to branch name pattern."

# PR #9: Issue Pattern
git checkout main
git checkout -b ref-issue-456-test
echo "# Reference: Issue Pattern" > test-data/ref-issue.txt
git add test-data/ref-issue.txt
git commit -m "Add reference PR for issue pattern"
git push -u origin ref-issue-456-test
gh pr create --base main --head ref-issue-456-test \
  --title "Reference: Issue Pattern" \
  --body "Permanent reference PR for integration tests. DO NOT CLOSE. This PR tests issue number extraction from branch name."

# PR #10: Stack A
git checkout main
git checkout -b ref-stack-a
echo "# Stack Level A" > test-data/ref-stack-a.txt
git add test-data/ref-stack-a.txt
git commit -m "Add stack level A"
git push -u origin ref-stack-a
gh pr create --base main --head ref-stack-a \
  --title "Reference: Stack A" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# PR #11: Stack B (based on stack-a)
git checkout ref-stack-a
git checkout -b ref-stack-b
echo "# Stack Level B" > test-data/ref-stack-b.txt
git add test-data/ref-stack-b.txt
git commit -m "Add stack level B"
git push -u origin ref-stack-b
gh pr create --base ref-stack-a --head ref-stack-b \
  --title "Reference: Stack B" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# PR #12: Stack C (based on stack-b)
git checkout ref-stack-b
git checkout -b ref-stack-c
echo "# Stack Level C" > test-data/ref-stack-c.txt
git add test-data/ref-stack-c.txt
git commit -m "Add stack level C"
git push -u origin ref-stack-c
gh pr create --base ref-stack-b --head ref-stack-c \
  --title "Reference: Stack C" \
  --body "Part of stacked PR reference. DO NOT CLOSE."

# Return to main
git checkout main
```

## Verification

After creating the PRs, verify they exist and are open:

```bash
gh pr list --repo data-yaml/qen-test --limit 20
```

Expected output should show PRs #7-12 with status OPEN.

## Update Constants

After creating the PRs, update the PR numbers in `tests/integration/constants.py` if they differ from the expected values (7-12).

## Notes

- These PRs should NEVER be closed or merged
- GitHub Actions will automatically run on these branches
- The `-failing-` pattern in `ref-failing-checks` will trigger the `always-fail.yml` workflow
- The issue pattern in `ref-issue-456-test` will be detected by qen
