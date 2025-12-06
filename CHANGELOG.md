<!-- markdownlint-disable MD024 -->
# Changelog

All *user-visible* changes to this project will be *concisely* documented in this file (one line per *significant* change).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Implement `qen pr status` command for enumerating and retrieving PR information across all repositories
- Implement `qen pr stack` command for identifying and displaying stacked PRs across repositories
- Implement `qen pr restack` command for updating stacked PRs to be based on latest versions of their base branches

## [0.1.4] - 2024-12-05

### Added

- Implement `qen pull` command with GitHub PR/issue integration via gh CLI
- Implement `qen status` command for comprehensive multi-repo git status tracking
- Implement `qen config` command for interactive configuration management
- Implement `qen commit` command for committing changes across multiple repos
- Implement `qen push` command for pushing changes across multiple repos
- Add specifications for `qen pull` and `qen push` commands

## [0.1.3] - 2024-12-05

Re-released 0.1.2 to fix CI.

## [0.1.2] - 2024-12-05

### Added

- Implement `qen init` and `qen add` command with comprehensive testing infrastructure
- Add `qenvy` XDG configuration library for cross-platform config management
- Add Poe the Poet task runner with shim script (`./poe`) for dev workflows

### Development

- Add `./poe lint` as a single command to handle `ruff` formatting and `mypy` type checking
- Add `./poe version` to display current version and bump versions (major/minor/patch)

## [0.1.1] - 2024-12-05

### Added

- Initial release with CI/CD setup
- GitHub Actions workflow with OIDC authentication
- TestPyPI and PyPI publishing support

[Unreleased]: https://github.com/data-yaml/qen/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/data-yaml/qen/releases/tag/v0.1.1
