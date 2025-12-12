# Migration Guide: QEN v0.3.x to v0.4.0

**Date:** 2025-12-10
**Status:** Official

---

## Breaking Change Notice

QEN v0.4.0 introduces a **fundamental architectural change** that is incompatible with v0.3.x:

### What Changed

**v0.3.x (Old Model):**

- Single meta repository with multiple project branches
- Switch branches to work on different projects
- Sub-repos in `repos/` get lost when switching branches
- Cannot work on multiple projects simultaneously

**v0.4.0 (New Model):**

- Per-project meta clones (`meta-{project}/`)
- Each project has its own physical directory
- Sub-repos stay cloned and ready
- Work on multiple projects simultaneously without friction

### Why This Change

The old single-branch model had critical limitations:

1. **Branch switching disrupts workspace** - IDE confused, language servers restart
2. **repos/ directory thrashing** - Sub-repos lost on branch switch
3. **Cannot multi-task** - Can't work on two projects at once
4. **Accidental contamination** - Easy to commit to wrong project branch

The new per-project meta architecture solves all these issues with **physical isolation**.

---

## Migration Strategy

### Option 1: Keep Using Old Version (Recommended for Active Projects)

If you have active projects in v0.3.x and don't want to disrupt your workflow:

```bash
# Explicitly use v0.3.0
uvx qen@0.3.0 status
uvx qen@0.3.0 add myrepo
uvx qen@0.3.0 pr

# Pin to v0.3.0 in your shell alias (optional)
alias qen="uvx qen@0.3.0"
```

This is the **safest option** if:

- You have active projects with uncommitted work
- You're mid-project and don't want disruption
- You prefer the single-branch workflow

### Option 2: Clean Migration (Recommended for New Start)

If you want to adopt the new architecture:

#### Step 1: Finish or Archive Current Projects

Before migrating, ensure all your current projects are in a clean state:

```bash
# Check status of all projects
uvx qen@0.3.0 config --list

# For each project, either:
# A) Finish and merge the PR
uvx qen@0.3.0 config --switch myproj
uvx qen@0.3.0 pr  # merge or close

# B) Or archive the work
cd ~/path/to/meta
git push origin YYMMDD-myproj  # Push branch to remote for safekeeping
```

#### Step 2: Delete Old Configuration

Remove v0.3.x configuration files:

```bash
# Backup first (optional)
cp -r ~/.config/qen ~/.config/qen.backup.v0.3.0

# Delete old configs
rm -rf ~/.config/qen/
```

**Note:** Your meta repository and project branches on the remote are NOT deleted. They remain accessible via git.

#### Step 3: Reinitialize with v0.4.0

```bash
# Initialize QEN (extracts meta prime metadata)
cd ~/path/to/meta  # or anywhere near your meta repo
uvx qen init

# Recreate projects as needed
uvx qen init my-new-project
```

#### Step 4: Re-add Repositories

For each new project, re-add your repositories:

```bash
cd meta-my-new-project/proj/YYMMDD-my-new-project
./qen add org/repo1
./qen add org/repo2
```

---

## What Happens to Old Project Branches?

**Nothing.** Your old project branches remain on the remote and in your local meta repository:

- Old branches: `YYMMDD-project-name` (e.g., `251203-readme-bootstrap`)
- Still accessible via: `git checkout 251203-readme-bootstrap`
- Still visible on GitHub/GitLab
- Can still create PRs from them
- Can still merge them into main

The old branches are **not touched** by the migration. You can:

1. **Leave them as-is** - They're harmless and provide history
2. **Merge them** - Create PRs and merge into main
3. **Delete them locally** - `git branch -D 251203-old-project`
4. **Delete them remotely** - `git push origin --delete 251203-old-project`

---

## Configuration Schema Changes

### Global Config (config.toml)

**v0.3.x:**

```toml
meta_path = "/Users/ernest/GitHub/meta"
org = "my-org"
current_project = "myproj"
```

**v0.4.0:**

```toml
meta_path = "/Users/ernest/GitHub/meta"  # Still points to meta prime
meta_remote = "git@github.com:org/meta.git"  # NEW - for cloning
meta_parent = "/Users/ernest/GitHub"  # NEW - where to clone
meta_default_branch = "main"  # NEW - main or master
org = "my-org"
current_project = "myproj"
```

### Project Config (projects/myproj.toml)

**v0.3.x:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
created = "2025-12-10T12:34:56Z"
```

**v0.4.0:**

```toml
name = "myproj"
branch = "251210-myproj"
folder = "proj/251210-myproj"
repo = "/Users/ernest/GitHub/meta-myproj"  # NEW - per-project meta path
created = "2025-12-10T12:34:56Z"
```

---

## Command Behavior Changes

### qen init

**v0.3.x:**

```bash
qen init myproj
# Creates branch in current meta repo
# Creates proj/YYMMDD-myproj/ in current repo
```

**v0.4.0:**

```bash
qen init myproj
# Clones meta repo -> meta-myproj/
# Creates branch in the clone
# Creates proj/YYMMDD-myproj/ in the clone
```

### qen add

**v0.3.x:**

```bash
qen add myrepo
# Clones into current meta/proj/YYMMDD-project/repos/
```

**v0.4.0:**

```bash
qen add myrepo
# Clones into meta-myproj/proj/YYMMDD-project/repos/
```

### All Other Commands

All commands (`status`, `pr`, `workspace`, etc.) now operate on the per-project meta clone instead of the single meta repository.

---

## Frequently Asked Questions

### Q: Can I use both v0.3.0 and v0.4.0 at the same time?

No. The configuration formats are incompatible. Choose one version.

### Q: Will I lose my work if I delete ~/.config/qen/?

No. Your work is in:

1. Your meta repository (branches still exist)
2. Remote git server (branches pushed there)
3. Sub-repositories (if you cloned them)

The ~/.config/qen/ directory only contains QEN's bookkeeping.

### Q: Can I import old v0.3.x projects into v0.4.0?

Not automatically. You must:

1. Finish/merge the old project
2. Create a new v0.4.0 project
3. Re-add repositories

### Q: What if I have uncommitted changes in a v0.3.x project?

**Option A:** Finish with v0.3.0

```bash
uvx qen@0.3.0 config --switch myproj
# commit and push your changes
```

**Option B:** Manual migration (advanced)

```bash
# Save your changes
cd ~/path/to/meta
git stash

# Switch to main
git checkout main

# Migrate to v0.4.0
rm -rf ~/.config/qen
uvx qen init

# Create new project
uvx qen init myproj

# Apply your stashed changes
cd meta-myproj
git stash pop
```

### Q: Do I need to recreate all my sub-repository clones?

Yes, for new v0.4.0 projects. But this is a one-time cost, and afterwards you get:

- Physical isolation
- No more repos/ thrashing
- Simultaneous multi-project work

### Q: Can I still use my old meta repository?

Yes! Your meta prime (`meta/`) is still the central repository. The per-project clones (`meta-{project}/`) are just working copies that push to the same remote.

---

## Support

If you encounter issues:

1. **Check version:** `uvx qen --version`
2. **Read the error message** - v0.4.0 has improved error messages
3. **File an issue:** <https://github.com/data-yaml/qen/issues>
4. **Fallback to v0.3.0:** `uvx qen@0.3.0` if you need to recover

---

## Summary

- **v0.4.0 is a breaking change** with a new per-project meta architecture
- **Use v0.3.0** if you have active projects: `uvx qen@0.3.0`
- **Migrate to v0.4.0** by deleting config and reinitializing
- **Old project branches are safe** - they remain on the remote
- **New model enables simultaneous multi-project work** without friction

Choose the version that fits your current workflow. Both are valid and stable.
