<!-- markdownlint-disable MD024 -->
# Changelog

All *user-visible* changes to this project will be *concisely* documented in this file (one line per *significant* change).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
