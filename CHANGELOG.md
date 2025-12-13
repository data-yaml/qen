<!-- markdownlint-disable MD024 -->
# Changelog

All *user-visible* changes to this project will be *concisely* documented in this file (one line per *significant* change).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2025-12-13

### Fixed

- **Platform-specific config paths**: Use `platformdirs.user_config_dir()` instead of hardcoded `~/.config` (fixes macOS using wrong directory)
- **Fully-qualified project names**: `qen init 251208-project` now correctly detects existing remote branches
- **No more skipped tests**: `./poe test-all` now enforces GitHub token requirement, ensuring 100% pass rate with zero skipped tests
- **Wrapper integration tests**: Fixed 5 tests in test_qen_wrapper.py to correctly locate wrapper scripts in per-project meta clones

### Changed

- **Test infrastructure**: Systematic tech debt cleanup added integration test helpers, real GitHub remote tests, py.typed markers for full type safety, and parametrized tests (reduced ~250 lines through deduplication)
- **Documentation**: Updated README.md and AGENTS.md to reflect platform-specific config paths

## [0.4.0] - 2025-12-10

- **BREAKING**: Projects now use per-project meta clones instead of shared meta repository (use `uvx qen@0.3.0` for old behavior)

### Added

- **Per-project meta clones**: Each project now gets its own physical clone of meta repository (`meta-{project}/`)
- **Discovery-first init**: `qen init` now detects if project branch exists remotely and clones it automatically
- **qen del command**: Delete entire projects with safety checks for unpushed commits and unmerged PRs
- **Auto-upgrade legacy configs**: Existing configs automatically upgraded to include `meta_remote`, `meta_parent`, `meta_default_branch`
- **Project name parsing**: Support fully-qualified names (e.g., `251210-myproject`) to avoid ambiguity

### Fixed

- **--yes flag**: Now suppresses branch switch prompts during initialization
- Enhanced error messages for meta repository not found, remote unreachable, and directory conflicts
- Added safety checks for force mode with warnings for uncommitted changes and unpushed commits

## [0.3.0] - 2025-12-08

### Added

- **Interactive PR TUI**: New `prompt_toolkit`-based interface for PR operations with keyboard navigation
- **Auto-initialization**: Commands automatically detect and initialize qen if not configured
- **PR info in status**: `qen status --pr` displays PR number, state, checks, draft status, and base branch
- **Draft PRs by default**: PRs created through TUI are drafts to prevent accidental merges
- **Batch operations**: Continue-on-failure strategy for multi-repo operations with summary reporting
- **Clickable URLs**: `qen status` now displays clickable GitHub URLs for repositories and PRs
- **Branch validation**: All project commands now verify you're on the correct project branch before executing
- **Repository removal**: `qen rm` safely removes repositories with safety checks for unpushed commits, uncommitted changes, and unmerged PRs
- **Interactive shell mode**: `qen sh` with no command opens an interactive subshell in the project directory with custom prompt

### Changed

- **BREAKING**: Use `qen pr` interactive Terminal UI or `--action` instead of explicit commands

### Fixed

- **Branch creation**: `qen init <project>` now always branches from main/master, not current branch
- **Long project names**: Warn users when project names exceed 12 characters (may cause issues with some terminals)
- **Global install task**: Removed `./poe install` task to prevent accidental global installation during development (use `./qen` directly)
- **Branch validation bug**: Fixed bug where `ensure_correct_branch()` regenerated branch names with today's date instead of reading stored branch from project config

## [0.2.1] - 2025-12-08

### Added

- **Force flag for init**: `qen init <project> --force` recreates existing projects (cleans up branch, folder, and config)
- **Auto-initialization**: `qen init <project>` now auto-initializes qen if not already initialized
- **Branch push before PR prompt**: `qen init <project>` now pushes branch to remote before prompting for PR creation

### Changed

- **Smart --yes flag**: `qen add --yes` now enables force-like cleanup behavior, automatically removing and re-adding existing repos
- **Show help by default**: Running `qen` without arguments now shows help text instead of an error

### Fixed

- **PR check status parsing**: Fixed incorrect check status determination by extracting logic to shared utility
- **Branch name timezone**: Branch names now consistently use local time instead of UTC

## [0.2.0] - 2024-12-08

### Added

- **qen workspace command**: Generate `.code-workspace` files for multi-repo projects with auto-discovery of sub-repositories
- **Project wrapper executable**: Each project gets a `./qen` executable that runs commands in project context without `--proj` flag
- **1-based repository indices**: Status and PR commands now display repositories with `[1]`, `[2]` indices for easier reference
- **Template-based project initialization**: Projects now use external template files with variable substitution
- **Configuration override flags**: Global `--meta`, `--proj`, and `--config-dir` flags to override configuration
- **PR creation prompt**: `qen init <project>` now prompts to create a PR after initialization
- **Force flag for add**: `qen add --force` removes existing repository before cloning to enable re-cloning
- **Default PR subcommand**: `qen pr` now defaults to `qen pr status`

### Changed

- **Project ID format**: Changed from `YYYY-MM-DD` to `YYMMDD` (e.g., `251208-feature` instead of `2025-12-08-feature`)
- **Workspace regeneration**: `qen add` now auto-regenerates workspace files after adding repositories

### Fixed

- Remote branch tracking now properly set when cloning repositories

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

[Unreleased]: https://github.com/data-yaml/qen/compare/v0.4.1...HEAD
[0.4.1]: https://github.com/data-yaml/qen/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/data-yaml/qen/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/data-yaml/qen/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/data-yaml/qen/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/data-yaml/qen/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/data-yaml/qen/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/data-yaml/qen/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/data-yaml/qen/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/data-yaml/qen/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/data-yaml/qen/releases/tag/v0.1.1
