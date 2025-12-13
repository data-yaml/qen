"""Implementation of qen init command.

Two modes:
1. qen init - Initialize qen tooling
2. qen init <proj-name> - Create new project
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import click

from ..config import QenConfigError
from ..context.runtime import RuntimeContext
from ..git_utils import (
    AmbiguousOrgError,
    GitError,
    MetaRepoNotFoundError,
    NotAGitRepoError,
    RemoteBranchInfo,
    extract_org_from_remotes,
    find_meta_repo,
    find_remote_branches,
)
from ..project import ProjectError, create_project, parse_project_name


@dataclass
class DiscoveryState:
    """State discovered about a project before initialization.

    This dataclass captures what exists locally and remotely before
    we decide what action to take for project initialization.

    Attributes:
        remote_branches: List of remote branches matching the project pattern
        local_config: Loaded project config dict if exists, None otherwise
        local_repo: Path to per-project meta clone if exists, None otherwise
    """

    remote_branches: list[RemoteBranchInfo]
    local_config: dict[str, str] | None
    local_repo: Path | None


@dataclass
class ActionPlan:
    """Plan of actions to take for project initialization.

    This dataclass describes what will happen based on the discovered state.

    Attributes:
        scenario: Name of the scenario (e.g., "create_new", "clone_existing")
        actions: List of human-readable action descriptions
        warnings: List of warning messages to show user
        target_branch: Branch name that will be used/created
    """

    scenario: str
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    target_branch: str = ""


def discover_project_state(
    ctx: RuntimeContext,
    config_name: str,
    meta_parent: Path,
    meta_remote: str,
    explicit_branch: str | None = None,
) -> DiscoveryState:
    """Discover existing project state from remote, local config, and local repo.

    This function performs a comprehensive check of three sources:
    1. Remote branches matching the project pattern
    2. Local project configuration file
    3. Local per-project meta clone

    Args:
        ctx: RuntimeContext for config access
        config_name: Project config name (what user typed)
        meta_parent: Parent directory where per-project metas are cloned
        meta_remote: Remote URL to query for branches
        explicit_branch: Explicit branch name if provided (from fully-qualified name)

    Returns:
        DiscoveryState with findings from all three sources

    Example:
        >>> state = discover_project_state(ctx, "myproj", Path("~/GitHub"), "git@...")
        >>> if state.remote_branches:
        ...     print(f"Found {len(state.remote_branches)} remote branches")
    """
    # 1. Check for remote branches matching pattern
    # If explicit_branch provided (fully-qualified name like "251208-proj"),
    # search for exact match. Otherwise, search with wildcard pattern.
    if explicit_branch:
        remote_branches_result = find_remote_branches(meta_remote, explicit_branch)
    else:
        remote_branches_result = find_remote_branches(meta_remote, f"*-{config_name}")

    # Handle network errors vs. empty results
    if remote_branches_result is None:
        # Network error occurred
        click.echo(
            "Warning: Could not query remote repository. Proceeding with local state only.",
            err=True,
        )
        remote_branches: list[RemoteBranchInfo] = []
    else:
        remote_branches = remote_branches_result

    # 2. Check if local config exists
    local_config: dict[str, str] | None = None
    if ctx.config_service.project_config_exists(config_name):
        try:
            local_config = ctx.config_service.read_project_config(config_name)
        except QenConfigError:
            # Config file exists but can't be read - treat as None
            local_config = None

    # 3. Check if local repo exists
    local_repo: Path | None = None
    repo_path = meta_parent / f"meta-{config_name}"
    if repo_path.exists() and (repo_path / ".git").exists():
        local_repo = repo_path

    return DiscoveryState(
        remote_branches=remote_branches,
        local_config=local_config,
        local_repo=local_repo,
    )


def build_action_plan(
    state: DiscoveryState,
    config_name: str,
    explicit_branch: str | None,
    generate_branch_fn: Callable[[str], str],
) -> ActionPlan:
    """Build an action plan based on discovered project state.

    Implements the decision matrix from the spec to determine what actions
    to take based on what exists (remote branches, local config, local repo).

    Args:
        state: Discovered project state
        config_name: Project config name (what user typed)
        explicit_branch: Explicit branch name if user provided one
        generate_branch_fn: Function to generate new branch name if needed

    Returns:
        ActionPlan describing what will happen
    """
    from ..git_utils import get_current_branch

    has_remote = len(state.remote_branches) > 0
    has_config = state.local_config is not None
    has_repo = state.local_repo is not None

    # Scenario C: Already setup (config + repo exist)
    # Note: Remote branch may or may not exist (user might not have pushed yet)
    if has_config and has_repo:
        branch_value = state.local_config.get("branch") if state.local_config else None
        # Validate type safety - branch must be a string
        branch = branch_value if isinstance(branch_value, str) else "unknown"
        warnings = []
        if not has_remote:
            warnings.append("Remote branch not found - you may want to push your local branch")
        return ActionPlan(
            scenario="already_setup",
            actions=[],
            warnings=warnings,
            target_branch=branch,
        )

    # Determine target branch
    if explicit_branch:
        target_branch = explicit_branch
    elif len(state.remote_branches) == 1:
        target_branch = state.remote_branches[0].name
    elif len(state.remote_branches) > 1:
        return ActionPlan(
            scenario="multiple_remotes",
            actions=["Prompt user to choose from multiple remote branches"],
            warnings=[],
            target_branch="",
        )
    else:
        target_branch = generate_branch_fn(config_name)

    # Scenario B: Remote exists, nothing local - clone existing
    if has_remote and not has_config and not has_repo:
        return ActionPlan(
            scenario="clone_existing",
            actions=[
                f"Clone meta-{config_name} from origin/{target_branch}",
                f"Checkout existing branch {target_branch}",
                "Pull latest changes",
                f"Create config at projects/{config_name}.toml",
            ],
            warnings=[],
            target_branch=target_branch,
        )

    # Scenario A: Nothing exists - create new
    if not has_remote and not has_config and not has_repo:
        return ActionPlan(
            scenario="create_new",
            actions=[
                f"Clone meta-{config_name} from remote",
                f"Create new branch {target_branch} from main",
                f"Create project folder proj/{target_branch}/",
                f"Create config at projects/{config_name}.toml",
            ],
            warnings=[],
            target_branch=target_branch,
        )

    # Edge case: Config exists but repo missing
    if has_config and not has_repo:
        branch_value = state.local_config.get("branch") if state.local_config else None
        # Validate type safety - branch must be a string
        branch = branch_value if isinstance(branch_value, str) else "unknown"
        if has_remote:
            # Remote exists - can offer to re-clone
            return ActionPlan(
                scenario="config_orphaned",
                actions=[
                    "Config exists but repo is missing",
                    f"Can re-clone from remote branch: {target_branch}",
                    "Or delete config and start fresh",
                ],
                warnings=["Config file exists but repository is missing"],
                target_branch=branch,
            )
        else:
            # No remote - can't recover easily
            return ActionPlan(
                scenario="config_orphaned",
                actions=[
                    "Config exists but repo is missing",
                    "No remote branch found - recommend deleting config",
                ],
                warnings=["Config file exists but repository and remote branch are missing"],
                target_branch=branch,
            )

    # Edge case: Repo exists but config missing
    if has_repo and not has_config:
        try:
            # We know state.local_repo is not None because has_repo is True
            assert state.local_repo is not None
            branch = get_current_branch(state.local_repo)
        except Exception:
            branch = "unknown"

        return ActionPlan(
            scenario="repo_orphaned",
            actions=[
                f"Found existing repo at {state.local_repo}",
                f"Create config for existing repo (branch: {branch})",
            ],
            warnings=["Repository exists without config"],
            target_branch=branch,
        )

    # Default fallback
    return ActionPlan(
        scenario="unknown",
        actions=["Unknown state - please report this as a bug"],
        warnings=["Unexpected state combination detected"],
        target_branch="",
    )


def show_discovery_state(state: DiscoveryState, config_name: str) -> None:
    """Display discovered project state with clear visual formatting.

    Args:
        state: Discovered project state
        config_name: Project config name
    """
    click.echo(f"\nProject: {config_name}")
    click.echo()

    # Remote branches
    if state.remote_branches:
        click.echo(f"  ✓ Remote branches: Found {len(state.remote_branches)}")
        for branch in state.remote_branches:
            click.echo(f"    • {branch.name} ({branch.last_commit[:8]})")
    else:
        click.echo("  ✗ Remote branches: Not found")

    # Local config
    if state.local_config:
        click.echo("  ✓ Local config: Found")
    else:
        click.echo("  ✗ Local config: Not found")

    # Local repo
    if state.local_repo:
        click.echo(f"  ✓ Local repo: Found at {state.local_repo}")
    else:
        click.echo("  ✗ Local repo: Not found")

    click.echo()


def show_action_plan(plan: ActionPlan) -> None:
    """Display action plan with clear visual formatting.

    Args:
        plan: Action plan to display
    """
    if plan.scenario == "already_setup":
        click.echo("Already configured:")
        click.echo(f"  Branch: {plan.target_branch}")
        click.echo()
        click.echo("Nothing to do. Project is ready to use.")
        click.echo()
        return

    if plan.warnings:
        click.echo("⚠️  Warnings:")
        for warning in plan.warnings:
            click.echo(f"  • {warning}")
        click.echo()

    click.echo("Actions to perform:")
    for action in plan.actions:
        click.echo(f"  • {action}")
    click.echo()


def prompt_branch_choice(branches: list[RemoteBranchInfo], config_name: str) -> str:
    """Prompt user to choose from multiple remote branches.

    Args:
        branches: List of remote branches to choose from
        config_name: Project config name

    Returns:
        Selected branch name
    """
    from ..project import generate_branch_name

    click.echo(f"\nFound multiple branches for project '{config_name}':")
    click.echo()

    for idx, branch in enumerate(branches, start=1):
        commit_short = branch.last_commit[:8] if branch.last_commit else "unknown"
        click.echo(f"  [{idx}] {branch.name} ({commit_short})")

    # Option to create new branch
    new_branch_idx = len(branches) + 1
    new_branch_name = generate_branch_name(config_name)
    click.echo(f"  [{new_branch_idx}] Create new branch ({new_branch_name})")
    click.echo()

    while True:
        choice_val = click.prompt(
            "Which branch should be used?",
            type=int,
            default=1,
            show_default=True,
        )
        choice: int = int(choice_val)  # Ensure it's an int

        if 1 <= choice <= len(branches):
            return branches[choice - 1].name
        elif choice == new_branch_idx:
            return new_branch_name
        else:
            click.echo(f"Invalid choice. Please enter a number between 1 and {new_branch_idx}.")


def extract_remote_and_org(meta_path: Path) -> tuple[str, str]:
    """Extract remote URL and organization from meta repository.

    Args:
        meta_path: Path to meta repository

    Returns:
        Tuple of (remote_url, org)

    Raises:
        GitError: If remote cannot be extracted
        AmbiguousOrgError: If multiple organizations detected
    """
    from ..git_utils import get_remote_url

    # Get remote URL
    remote_url = get_remote_url(meta_path)

    # Extract org
    org = extract_org_from_remotes(meta_path)

    return remote_url, org


def init_qen(
    ctx: RuntimeContext,
    verbose: bool = False,
) -> None:
    """Initialize qen tooling.

    Behavior:
    1. Search for meta repo (current dir -> parent dirs) or use override
    2. Extract org from git remote URL
    3. Create $XDG_CONFIG_HOME/qen/main/config.toml

    Args:
        ctx: RuntimeContext for config access and overrides
        verbose: Enable verbose output

    Raises:
        MetaRepoNotFoundError: If meta repository cannot be found
        NotAGitRepoError: If not in a git repository
        AmbiguousOrgError: If multiple organizations detected
        GitError: If git operations fail
        QenConfigError: If config operations fail
    """
    # Find meta repository
    # Use override if provided (for testing or explicit specification)
    if ctx.meta_path_override:
        meta_path = ctx.meta_path_override
        if verbose:
            click.echo(f"Using meta repository from override: {meta_path}")
    else:
        if verbose:
            click.echo("Searching for meta repository...")

        try:
            meta_path = find_meta_repo()
        except NotAGitRepoError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo(
                "Please ensure you are in or near a directory named 'meta',\n"
                "or specify the path with: qen --meta <path> init",
                err=True,
            )
            raise click.Abort() from e
        except MetaRepoNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo(
                "Please ensure you are in or near a directory named 'meta',\n"
                "or specify the path with: qen --meta <path> init",
                err=True,
            )
            raise click.Abort() from e

        if verbose:
            click.echo(f"Found meta repository: {meta_path}")

    # Resolve symlinks and validate meta_path
    if meta_path.is_symlink():
        meta_path = meta_path.resolve()

    if not meta_path.exists():
        click.echo(f"Error: Meta path does not exist: {meta_path}", err=True)
        raise click.Abort()

    # Extract remote URL and organization
    if verbose:
        click.echo("Extracting metadata from git remotes...")

    try:
        remote_url, org = extract_remote_and_org(meta_path)
    except AmbiguousOrgError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e
    except GitError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort() from e

    if verbose:
        click.echo(f"Remote URL: {remote_url}")
        click.echo(f"Organization: {org}")

    # Get parent directory for per-project meta clones
    import os

    meta_parent = meta_path.parent

    if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
        click.echo(f"Error: Parent directory not writable: {meta_parent}", err=True)
        raise click.Abort()

    if verbose:
        click.echo(f"Meta parent directory: {meta_parent}")

    # Detect default branch from remote
    from ..git_utils import get_default_branch_from_remote

    if verbose:
        click.echo("Detecting default branch from remote...")

    default_branch = get_default_branch_from_remote(remote_url)

    if verbose:
        click.echo(f"Default branch: {default_branch}")

    # Create configuration
    try:
        ctx.config_service.write_main_config(
            meta_path=str(meta_path),
            meta_remote=remote_url,
            meta_parent=str(meta_parent),
            meta_default_branch=default_branch,
            org=org,
            current_project=None,
        )
    except QenConfigError as e:
        click.echo(f"Error creating configuration: {e}", err=True)
        raise click.Abort() from e

    # Success message
    config_path = ctx.config_service.get_main_config_path()
    click.echo(f"Initialized qen configuration at: {config_path}")
    click.echo(f"  meta_path: {meta_path}")
    click.echo(f"  meta_remote: {remote_url}")
    click.echo(f"  meta_parent: {meta_parent}")
    click.echo(f"  meta_default_branch: {default_branch}")
    click.echo(f"  org: {org}")
    click.echo()
    click.echo("You can now create projects with: qen init <project-name>")


def init_project(
    ctx: RuntimeContext,
    project_name: str,
    verbose: bool = False,
    yes: bool = False,
    force: bool = False,
) -> None:
    """Setup a project (discover existing or create new) - discovery-first approach.

    This function implements the discovery-first philosophy:
    1. Parse project name to determine config name and explicit branch (if any)
    2. Discover existing state (remote branches, local config, local repo)
    3. Build action plan based on discovered state
    4. Show user what exists and what will happen
    5. Prompt for confirmation (unless --yes)
    6. Execute plan

    Args:
        ctx: RuntimeContext for config access and overrides
        project_name: Name of the project (short or fully-qualified with YYMMDD prefix)
        verbose: Enable verbose output
        yes: Auto-confirm prompts (skip all confirmation prompts)
        force: Force recreate if project already exists (delete and recreate)

    Raises:
        QenConfigError: If config operations fail
        ProjectError: If project creation fails
        GitError: If git operations fail
    """
    import shutil

    from ..project import generate_branch_name

    # Step 1: Parse project name
    config_name, explicit_branch = parse_project_name(project_name)

    MAX_PROJECT_NAME_LENGTH = 12
    # Warn if project name is too long
    if len(config_name) > MAX_PROJECT_NAME_LENGTH:
        click.echo(
            f"Warning: Project name '{config_name}' is {len(config_name)} characters long.",
            err=True,
        )
        click.echo(
            f"  Project names longer than {MAX_PROJECT_NAME_LENGTH} characters may break some services.",
            err=True,
        )
        click.echo()

    # Step 2: Ensure global config exists
    if not ctx.config_service.main_config_exists():
        if verbose:
            click.echo("Auto-initializing qen configuration...")
        init_qen(ctx, verbose=False)

    # Read main config
    try:
        main_config = ctx.config_service.read_main_config()
        meta_remote = main_config["meta_remote"]
        meta_parent = Path(main_config["meta_parent"])
        meta_default_branch = main_config["meta_default_branch"]
        github_org = main_config.get("org")
    except (QenConfigError, KeyError) as e:
        click.echo(f"Error reading configuration: {e}", err=True)
        click.echo("Please reinitialize with: qen init", err=True)
        raise click.Abort() from e

    # Step 3: Handle force mode (delete existing project)
    if force and ctx.config_service.project_config_exists(config_name):
        if verbose:
            click.echo(f"Force mode: Cleaning up existing project '{config_name}'")

        try:
            old_config = ctx.config_service.read_project_config(config_name)
            per_project_meta = Path(old_config["repo"])

            if per_project_meta.exists():
                # Delete repo directory
                shutil.rmtree(per_project_meta)
                if verbose:
                    click.echo(f"  Deleted: {per_project_meta}")

            # Delete config
            ctx.config_service.delete_project_config(config_name)
            if verbose:
                click.echo(f"  Deleted config for '{config_name}'")
        except (QenConfigError, KeyError):
            # Can't read config - just delete it
            ctx.config_service.delete_project_config(config_name)

    # Step 4: Discover existing state
    if verbose:
        click.echo("Discovering project state...")

    state = discover_project_state(ctx, config_name, meta_parent, meta_remote, explicit_branch)

    # Step 5: Build action plan
    def branch_generator(name: str) -> str:
        return generate_branch_name(name)

    plan = build_action_plan(state, config_name, explicit_branch, branch_generator)

    # Handle multiple remotes - prompt user
    if plan.scenario == "multiple_remotes":
        selected_branch = prompt_branch_choice(state.remote_branches, config_name)
        # Rebuild plan with selected branch
        plan = build_action_plan(state, config_name, selected_branch, branch_generator)

    # Step 6: Show discovery state and action plan
    show_discovery_state(state, config_name)
    show_action_plan(plan)

    # Step 7: Handle already_setup scenario
    if plan.scenario == "already_setup":
        click.echo(f"Use: qen config {config_name}")
        return

    # Step 8: Prompt for confirmation (unless --yes)
    if not yes:
        if not click.confirm("Continue?", default=True):
            click.echo("Aborted.")
            raise click.Abort()

    # Step 9: Execute plan based on scenario
    now = datetime.now(UTC)

    if plan.scenario in ["create_new", "clone_existing"]:
        # Clone per-project meta
        import os

        from ..git_utils import clone_per_project_meta

        # Validate meta_parent is writable before attempting clone
        if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
            click.echo(f"Error: Parent directory not writable: {meta_parent}", err=True)
            raise click.Abort()

        # For clone_existing, use the target branch (existing remote branch)
        # For create_new, use the default branch (will create new branch later)
        clone_branch = (
            plan.target_branch if plan.scenario == "clone_existing" else meta_default_branch
        )

        try:
            per_project_meta = clone_per_project_meta(
                meta_remote,
                config_name,
                meta_parent,
                clone_branch,
            )
            if verbose:
                click.echo(f"Cloned: {per_project_meta}")
        except GitError as e:
            click.echo(f"Error cloning: {e}", err=True)
            raise click.Abort() from e

        # For create_new: create project structure and commit
        if plan.scenario == "create_new":
            try:
                branch_name, folder_path = create_project(
                    per_project_meta,
                    config_name,
                    date=None,
                    github_org=github_org,
                )
                if verbose:
                    click.echo(f"Created branch: {branch_name}")
                    click.echo(f"Created directory: {folder_path}")
            except ProjectError as e:
                click.echo(f"Error creating project: {e}", err=True)
                if per_project_meta.exists():
                    shutil.rmtree(per_project_meta)
                raise click.Abort() from e
        else:
            # clone_existing: branch already exists, just use it
            branch_name = plan.target_branch
            folder_path = f"proj/{branch_name}"

        # Write config
        try:
            ctx.config_service.write_project_config(
                project_name=config_name,
                branch=branch_name,
                folder=folder_path,
                repo=str(per_project_meta),
                created=now.isoformat(),
            )
        except QenConfigError as e:
            click.echo(f"Error writing config: {e}", err=True)
            raise click.Abort() from e

        # Set as current project
        try:
            ctx.config_service.update_current_project(config_name)
        except QenConfigError:
            pass  # Non-critical

        # Success message
        click.echo(f"\nProject '{config_name}' ready at {per_project_meta}")
        click.echo(f"  Branch: {branch_name}")
        click.echo(f"  Directory: {per_project_meta / folder_path}")
        click.echo()
        click.echo("Next steps:")
        click.echo(f"  cd {per_project_meta / folder_path}")
        click.echo("  # Add repositories with: qen add <repo-url>")

    elif plan.scenario == "repo_orphaned":
        # Repo exists but config missing - create config
        from ..git_utils import get_current_branch

        try:
            # We know state.local_repo is not None in this scenario
            assert state.local_repo is not None
            branch = get_current_branch(state.local_repo)
        except Exception:
            branch = "unknown"

        folder_path = f"proj/{branch}"

        ctx.config_service.write_project_config(
            project_name=config_name,
            branch=branch,
            folder=folder_path,
            repo=str(state.local_repo),
            created=now.isoformat(),
        )

        ctx.config_service.update_current_project(config_name)

        click.echo(f"\nConfig created for existing repo at {state.local_repo}")

    elif plan.scenario == "config_orphaned":
        # Config exists but repo missing - offer to fix automatically
        click.echo("\nConfig exists but repository is missing.")

        # Check if remote exists for re-cloning
        has_remote = len(state.remote_branches) > 0

        if has_remote:
            # Can re-clone from remote
            click.echo(f"Remote branch found: {plan.target_branch}")
            click.echo()

            # Ask for confirmation (unless --yes)
            if yes or click.confirm("Delete config and re-clone from remote?", default=True):
                # Delete config
                ctx.config_service.delete_project_config(config_name)
                if verbose:
                    click.echo(f"Deleted config for '{config_name}'")

                # Re-clone from remote
                import os

                from ..git_utils import clone_per_project_meta

                # Validate meta_parent is writable
                if not meta_parent.is_dir() or not os.access(meta_parent, os.W_OK):
                    click.echo(f"Error: Parent directory not writable: {meta_parent}", err=True)
                    raise click.Abort()

                try:
                    per_project_meta = clone_per_project_meta(
                        meta_remote,
                        config_name,
                        meta_parent,
                        plan.target_branch,
                    )
                    if verbose:
                        click.echo(f"Cloned: {per_project_meta}")
                except GitError as e:
                    click.echo(f"Error cloning: {e}", err=True)
                    raise click.Abort() from e

                # Write new config
                branch_name = plan.target_branch
                folder_path = f"proj/{branch_name}"

                try:
                    ctx.config_service.write_project_config(
                        project_name=config_name,
                        branch=branch_name,
                        folder=folder_path,
                        repo=str(per_project_meta),
                        created=now.isoformat(),
                    )
                except QenConfigError as e:
                    click.echo(f"Error writing config: {e}", err=True)
                    raise click.Abort() from e

                # Set as current project
                try:
                    ctx.config_service.update_current_project(config_name)
                except QenConfigError:
                    pass  # Non-critical

                click.echo(f"\nProject '{config_name}' ready at {per_project_meta}")
                click.echo(f"  Branch: {branch_name}")
                click.echo(f"  Directory: {per_project_meta / folder_path}")
            else:
                click.echo("Aborted.")
                raise click.Abort()
        else:
            # No remote - can only delete config
            click.echo("No remote branch found.")
            click.echo()

            # Ask for confirmation (unless --yes)
            if yes or click.confirm("Delete orphaned config?", default=True):
                ctx.config_service.delete_project_config(config_name)
                click.echo(f"Deleted config for '{config_name}'")
                click.echo()
                click.echo("You can now run:")
                click.echo(f"  qen init {config_name}")
            else:
                click.echo("Aborted.")
                raise click.Abort()

    else:
        # Unknown scenario
        click.echo(f"Unexpected scenario: {plan.scenario}")
        raise click.Abort()
