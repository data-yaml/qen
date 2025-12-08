# GitHub Actions Workflows for qen-test Repository

These workflows should be placed in the `data-yaml/qen-test` repository at `.github/workflows/`.

## Workflows

### always-pass.yml
Always passes for all branches except test-* branches.

### always-fail.yml
Fails for any branch containing "-failing-" in the name, passes otherwise.

### slow-check.yml
Simulates a slow check (35 seconds) to test check status polling.

## Setup Instructions

```bash
# Clone the test repo
git clone https://github.com/data-yaml/qen-test
cd qen-test

# Create workflows directory
mkdir -p .github/workflows

# Copy workflows
cp /path/to/qen/docs/qen-test-workflows/*.yml .github/workflows/

# Commit and push
git add .github/workflows/
git commit -m "Add GitHub Actions workflows for integration testing"
git push origin main
```

## Testing

After setup, create a test branch to verify:

```bash
# This should pass always-fail.yml
git checkout -b test-passing
git push origin test-passing

# This should fail always-fail.yml
git checkout -b test-failing-checks
git push origin test-failing-checks
```
