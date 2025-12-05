# QEN: A Developer Nest for Multi-Repo Innovation

## 1. Introduction

**QEN** (“קֵן”, *nest* in [Biblical Hebrew](https://biblehub.com/hebrew/7064.htm)) is a tiny, extensible tool for organizing multi-repository development work.  
A “qen” is a lightweight context—a safe, structured “nest”—where complex feature development can incubate across multiple repos.

QEN does not replace your workflow.  
It simply gathers all context for a project (code, specs, artifacts, etc.) into a single managed folder inside a central repository (default `meta`).

## 2. Quick Start

### Initialize qen itself

```bash
qen init
```

1. Tries to find `meta` in current or parent folder (else errors)
2. Infers git repo, organization, etc.
3. Stores that in `$XDG_CONFIG_HOME/qen/config.toml`

### Initialize qen project in meta repo

```bash
qen init proj-name
```

1. Creates meta branch `YYYY-MM-DD-proj-name`
2. Creates folder `proj/YYYY-MM-DD-proj-name` in meta
3. Creates stub README.md
4. Creates `pyproject.toml` with [tool.qen] configuration for repo management
5. Creates and gitignores a 'repos' subfolder
6. Sets 'proj-name' as the current project in qen config.

### Add sub-repos

```bash
qen add repo
qen add org/repo
qen add org/repo -b custom-branch
```

1. Operates on current project
1. Infers org
1. Checks out repo into `repos/`
1. Defaults to the same branch name as project
1. Updates `pyproject.toml` ([tool.qen.repos] array)
1. Can have multiple instances of the same repo

> Question: should we do all this directly, or leverage .gitmodules and/or worktrees?

### Other Operations

- status: Shows git status across all sub-repos
- sync: push and pull sub-repos (error if uncommited changes)

## 3. Philosophy

**QEN is intentionally small.**  
Its job is not to tell you how to develop—it simply creates a structured nest where complex, multi-repo work can grow.

Design principles:

- context over configuration  
- minimal manifests  
- always latest (with optional checkpoints)  
- zero global state  
- human-readable, human-manageable repos

## 4. License

MIT License.
