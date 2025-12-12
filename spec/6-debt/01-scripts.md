# Tech Debt: Scripts

> VERDICT: OVERKILL. Leave as is.

**Review the scripts/ directory and identify technical debt including outdated dependencies, code duplication, missing tests, overly complex functions, inconsistent patterns, poor error handling, and areas lacking documentation or type safety.**

## Components in Scope

- `scripts/version.py` - Version management
- `scripts/integration_test.py` - Integration test runner
- Any other utility scripts

## Findings

### Version Management Script (`version.py`)

1. **Lack of Proper Error Handling**
   - Uses `sys.exit(1)` directly in functions, which is not ideal for testability
   - No validation for version string format before parsing
   - No handling for edge cases like non-standard version strings

2. **Regex Parsing Weaknesses**
   - Uses brittle regex for version extraction (`^version\s*=\s*"([^"]+)"`)
   - No validation that the extracted version is a valid semver
   - Could break with complex pyproject.toml configurations

3. **Limited Semantic Versioning Support**
   - Basic version bumping without pre-release or build metadata handling
   - No support for advanced semver scenarios (alpha, beta, rc)

4. **Side Effects in Core Functions**
   - `set_version()` directly modifies filesystem
   - `main()` performs multiple operations (bumping, committing, tagging)
   - Difficult to test or use functions in isolation

5. **No Logging or Verbose Mode**
   - Relies on `print()` for output
   - No structured logging
   - Lacks verbosity control

### Integration Test Runner (`integration_test.py`)

1. **Token Detection Limitations**
   - Assumes `gh` CLI is the primary token source
   - No fallback for other authentication methods
   - Weak error handling for token retrieval

2. **Process Replacement Approach**
   - Uses `os.execvp()` which replaces the current process
   - Prevents potential cleanup or additional processing
   - Makes the script less flexible for programmatic use

3. **Hardcoded Test Discovery**
   - Assumes `tests/` is the test directory
   - Hardcodes `-m integration` marker
   - Limited configurability

4. **Minimal Error Propagation**
   - Returns error code but doesn't provide detailed error information
   - Warning messages printed to stderr but no structured error handling

## Recommendations

### Version Management Script

1. **Improve Version Parsing**
   - Use `packaging.version` for robust semver parsing
   - Add comprehensive version validation
   - Support pre-release and build metadata
   - Create a dedicated `VersionManager` class

2. **Enhance Error Handling**
   - Replace `sys.exit()` with custom exceptions
   - Add logging with different verbosity levels
   - Create testable, pure functions without side effects

3. **Separate Concerns**
   - Split version bumping, file modification, and git operations
   - Make each function do one thing well
   - Allow easier mocking and testing

4. **Add Comprehensive Validation**
   - Validate version strings before modification
   - Add checks for pyproject.toml structure
   - Provide meaningful error messages

5. **Improve CLI Integration**
   - Consider using `click` or `typer` for more robust CLI handling
   - Add options for verbose output
   - Support more advanced versioning scenarios

### Integration Test Runner

1. **Token Detection Strategy**
   - Create pluggable token providers
   - Support multiple authentication sources
   - Add configuration for custom token retrieval

2. **Flexible Test Discovery**
   - Allow configurable test directory
   - Support custom pytest markers
   - Add CLI options for test configuration

3. **Robust Error Handling**
   - Create structured error reporting
   - Provide detailed diagnostics
   - Support different verbosity levels

4. **Process Management**
   - Replace `os.execvp()` with `subprocess.run()`
   - Allow for pre and post-test hooks
   - Improve process management and error tracking

### Cross-Cutting Recommendations

1. **Add Comprehensive Tests**
   - Create unit tests for both scripts
   - Use `pytest` for thorough coverage
   - Test edge cases and error scenarios

2. **Type Safety Improvements**
   - Add more precise type hints
   - Use `typing.Literal` for constrained types
   - Enable strict mypy checks

3. **Documentation**
   - Expand docstrings with examples
   - Add type information in docstrings
   - Create a README explaining script usage and configuration

4. **Configuration Management**
   - Consider using `pyproject.toml` for script configurations
   - Add support for environment-based configuration
   - Create a consistent configuration strategy

## Next Steps

1. Refactor scripts with proposed improvements
2. Add comprehensive test coverage
3. Update documentation
4. Validate improvements through code review
