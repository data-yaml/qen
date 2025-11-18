# QEN: A Developer Nest for Multi-Repo Innovation

**QEN** (“קֵן”, *nest* in [Biblical Hebrew](https://biblehub.com/hebrew/7064.htm)) is a tiny, extensible tool for organizing multi-repository development work.  
A “qen” is a lightweight context—a safe, structured “nest”—where complex feature development can incubate across multiple repos.

QEN does not replace your workflow.  
It simply gathers the pieces into one coherent workspace.

## 1. Installation

With **uv**:

```
uv pip install qen
```

Or with pip:

```
pip install qen
```

## 2. Quick Start

### Create a new context

```
qen init
```

### Add participating repositories

```
qen add-repo org/service-a feature/auth-flow
qen add-repo org/frontend-b feature/user-login
```

### Materialize the working workspace

```
qen sync
```

QEN clones the repositories, checks out the branches, and constructs a working “nest” under `workspace/`.

## 3. Concept: Context as a Repo

A QEN context is simply a small git repository that contains:

- a minimal `manifest.yml`  
- optional notes, prompts, or agent definitions  
- a generated `workspace/` directory that gathers the active repos

This makes multi-repo feature work:

- reproducible  
- shareable  
- archive-able  
- easy to resurrect  
- safe to experiment with

## 4. Minimal Example `manifest.yml`

```
feature: F-1234-improved-auth-flow
repos:
  - name: org/service-a
    branch: feature/auth-flow
  - name: org/frontend-b
    branch: feature/user-login
status: active
```

## 5. Philosophy

**QEN is intentionally small.**  
Its job is not to tell you how to develop—it simply creates a structured nest where complex, multi-repo work can grow.

Design principles:

- context over configuration  
- minimal manifests  
- always latest (with optional checkpoints)  
- zero global state  
- human-readable, human-manageable repos

## 6. License

MIT License.
