<!-- markdownlint-disable MD024 -->
# Changelog

All *user-visible* changes to this project will be *concisely* documented in this file (one line per *significant* change).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2024-12-08

### Added

- **Template-based project initialization**: Projects now use external template files instead of hardcoded strings
- **Project wrapper executable**: Each project gets a `./qen` executable that runs commands in project context without `--proj` flag
- **Configuration override flags**: Global `--meta`, `--proj`, and `--config-dir` flags to override configuration
- **PR creation prompt**: `qen init <project>` now prompts to create a PR after initialization
- **Force flag for add**: `qen add --force` removes existing repository before cloning to enable re-cloning
- **Default PR subcommand**: `qen pr` now defaults to `qen pr status`

### Changed

- Project files (README.md, pyproject.toml, .gitignore) now generated from templates with variable substitution
- Templates stored in `./proj` directory and included in distribution package
- Template variables: project_name, date, timestamp, branch_name, folder_path, github_org, meta_path

### Fixed

- Remote branch tracking now properly set when cloning repositories
- `qen add` and `qen pull` work correctly with repository management

### Documentation

- Updated README with project wrapper usage examples
- Added AGENTS.md with markdown best practices for AI coding agents
- Added comprehensive specifications for template system and CLI overrides

## [0.1.5] - 2024-12-07

### Added

- Implement `qen pr status` command for enumerating and retrieving PR information across all repositories
- Implement `qen pr stack` command for identifying and displaying stacked PRs across repositories
- Implement `qen pr restack` command for updating stacked PRs to be based on latest versions of their base branches

### Fixed

- Improve TypedDict schemas with NotRequired fields for better type safety
- Removed all mocks from integration tests - now use real GitHub API only
- Integration tests now require `GITHUB_TOKEN` and use <https://github.com/data-yaml/qen-test>
- Update AGENTS.md with testing philosophy and NO MOCKS requirement

### Development

- Add local test repository scripts that create git repos with mock PR data (deprecated in favor of NO MOCKS strategy)
- Add comprehensive mocking infrastructure for GitHub CLI in integration tests (deprecated - removed in next release)
- Update integration test fixtures to support both local and remote test repositories

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

[Unreleased]: https://github.com/data-yaml/qen/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/data-yaml/qen/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/data-yaml/qen/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/data-yaml/qen/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/data-yaml/qen/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/data-yaml/qen/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/data-yaml/qen/releases/tag/v0.1.1
