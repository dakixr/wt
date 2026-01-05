"""wt CLI - Git worktree toolkit."""

from __future__ import annotations

import os
import subprocess
import sys
from functools import wraps
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from wt import __version__
from wt.config import (
    WtConfig,
    ensure_config,
    ensure_worktrees_gitignore,
    get_config_path,
    get_wt_dir,
)
from wt.errors import (
    BaseBranchNotFoundError,
    BranchExistsError,
    BranchNotFoundError,
    CommandFailedError,
    ExitCode,
    NotInGitRepoError,
    NotInWorktreeError,
    NoWorktreesError,
    UncommittedChangesError,
    UnpushedCommitsError,
    UsageError,
    WorktreeNotFoundError,
    WtError,
)
from wt.gh import check_gh_installed, create_pr
from wt.git import (
    branch_exists,
    checkout_branch,
    delete_branch,
    delete_remote_branch,
    fetch_branch,
    get_ahead_behind,
    get_branch_merged_status,
    get_current_branch,
    get_last_commit_time,
    get_repo_root,
    get_upstream_branch,
    get_worktree_root,
    git_add_all,
    git_commit,
    has_uncommitted_changes,
    has_unpushed_commits,
    is_bare_repo,
    list_remote_branches,
    merge_branch,
    push_branch,
    worktree_add,
    worktree_add_existing,
    worktree_list,
    worktree_remove,
)
from wt.init import InitContext, resolve_init_script, run_init_script
from wt.state import WtState, get_state_path, prune_stale_entries
from wt.utils import derive_feat_name_from_branch, launch_ai_tui, normalize_feat_name

app = typer.Typer(
    name="wt",
    help="Git worktree toolkit for feature-branch workflows.",
    invoke_without_command=True,
)
console = Console()


def error_handler(func):
    """Decorator to handle wt errors."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except WtError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            if exc.suggestion:
                console.print(f"[dim]Suggestion:[/dim] {exc.suggestion}")
            raise typer.Exit(exc.exit_code)
        except subprocess.CalledProcessError as exc:
            command = " ".join(str(arg) for arg in exc.cmd)
            stderr = exc.stderr or ""
            error = CommandFailedError(command, stderr)
            console.print(f"[red]Error:[/red] {error}")
            if error.suggestion:
                console.print(f"[dim]Suggestion:[/dim] {error.suggestion}")
            raise typer.Exit(error.exit_code)

    return wrapper


def get_validated_repo_root() -> Path:
    """Get repo root, validating it's a non-bare git repo."""
    root = get_repo_root()
    if is_bare_repo(cwd=root):
        raise NotInGitRepoError()
    return root


def sync_state(repo_root: Path) -> None:
    """Best-effort sync of state.json against git worktrees."""
    state_path = get_state_path(repo_root)
    state = WtState.load(state_path)
    worktrees = worktree_list(cwd=repo_root)
    valid_paths = {entry["path"] for entry in worktrees if entry.get("path")}
    if prune_stale_entries(state, valid_paths):
        state.save(state_path)


@app.command()
@error_handler
def init(
    branch_prefix: Annotated[
        str | None,
        typer.Option("--branch-prefix", help="Branch prefix for feature branches"),
    ] = None,
    base: Annotated[
        str | None, typer.Option("--base", "-b", help="Base branch for new worktrees")
    ] = None,
    remote: Annotated[
        str | None, typer.Option("--remote", help="Remote name for push/fetch")
    ] = None,
    worktrees_dir: Annotated[
        str | None,
        typer.Option(
            "--worktrees-dir", help="Directory (relative to repo) for worktrees"
        ),
    ] = None,
    default_ai_tui: Annotated[
        str | None, typer.Option("--default-ai-tui", help="Default AI TUI to launch")
    ] = None,
    init_script: Annotated[
        str | None,
        typer.Option(
            "--init-script",
            help="Command/path to run after creating/checking out a worktree",
        ),
    ] = None,
    hook: Annotated[
        bool,
        typer.Option(
            "--hook",
            help="Create a starter .wt/hooks/init.sh (used if init_script is unset)",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing wt config (and hook)"),
    ] = False,
) -> None:
    """Initialize wt in the current git repository."""
    repo_root = get_validated_repo_root()
    wt_root = get_wt_dir(repo_root)
    config_path = get_config_path(repo_root)

    has_any_overrides = any(
        opt is not None
        for opt in (
            branch_prefix,
            base,
            remote,
            worktrees_dir,
            default_ai_tui,
            init_script,
        )
    )

    if config_path.exists() and not force and not has_any_overrides and not hook:
        ensure_worktrees_gitignore(repo_root)
        console.print(f"[green]Already initialized:[/green] {wt_root}")
        return

    if config_path.exists() and not force:
        config = WtConfig.load(config_path)
    else:
        config = WtConfig()

    if branch_prefix is not None:
        config.branch_prefix = branch_prefix
    if base is not None:
        config.base_branch = base
    if remote is not None:
        config.remote = remote
    if worktrees_dir is not None:
        config.worktrees_dir = worktrees_dir
    if default_ai_tui is not None:
        config.default_ai_tui = default_ai_tui
    if init_script is not None:
        config.init_script = init_script

    config.save(config_path)
    ensure_worktrees_gitignore(repo_root)

    worktrees_path = Path(config.worktrees_dir)
    if not worktrees_path.is_absolute():
        worktrees_path = repo_root / worktrees_path
    worktrees_path.mkdir(parents=True, exist_ok=True)

    if hook:
        hooks_dir = wt_root / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        init_sh = hooks_dir / "init.sh"
        if not init_sh.exists() or force:
            init_sh.write_text(
                "#!/bin/sh\n"
                "# wt init hook\n"
                "set -e\n\n"
                'echo "wt: setting up $WT_FEAT_NAME in $WT_WORKTREE_PATH (base=$WT_BASE_BRANCH)" \n\n'
                "# Example: install deps\n"
                "# uv sync\n",
                encoding="utf-8",
            )
            try:
                init_sh.chmod(0o755)
            except OSError:
                # Best-effort; some filesystems may not support chmod.
                pass

    console.print(f"[green]Initialized wt:[/green] {wt_root}")


@app.command()
@error_handler
def new(
    feat_name: Annotated[str, typer.Argument(help="Feature name for the new worktree")],
    base: Annotated[
        str | None, typer.Option("--base", "-b", help="Base branch")
    ] = None,
    no_ai: Annotated[bool, typer.Option("--no-ai", help="Don't launch AI TUI")] = False,
    no_push: Annotated[
        bool,
        typer.Option("--no-push", help="Don't push branch to remote"),
    ] = False,
    no_init: Annotated[
        bool, typer.Option("--no-init", help="Skip init script")
    ] = False,
    strict_init: Annotated[
        bool, typer.Option("--strict-init", help="Fail if init script fails")
    ] = False,
) -> None:
    """Create a new worktree for a feature."""
    repo_root = get_validated_repo_root()
    config = ensure_config(repo_root)
    ensure_worktrees_gitignore(repo_root)

    normalized = normalize_feat_name(feat_name)
    branch = f"{config.branch_prefix}{normalized}"
    worktree_path = repo_root / config.worktrees_dir / normalized
    base_branch = base or config.base_branch

    if branch_exists(branch, cwd=repo_root):
        raise BranchExistsError(branch)

    if not branch_exists(base_branch, cwd=repo_root):
        console.print(
            f"[dim]Fetching base branch '{base_branch}' from {config.remote}...[/dim]"
        )
        if not fetch_branch(config.remote, base_branch, cwd=repo_root):
            raise BaseBranchNotFoundError(base_branch)

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    console.print(f"Creating worktree at [cyan]{worktree_path}[/cyan]...")
    worktree_add(worktree_path, branch, base_branch, cwd=repo_root)

    # Note: Branch is created locally only. It will be pushed to remote
    # when creating a pull request with `wt pr`.

    state = WtState.load(get_state_path(repo_root))
    state.add_worktree(normalized, branch, str(worktree_path), base_branch)
    state.save(get_state_path(repo_root))

    console.print(f"[green]Created worktree:[/green] {worktree_path}")
    console.print(f"[green]Branch:[/green] {branch}")

    # Run init script if configured
    if not no_init:
        wt_root = get_wt_dir(repo_root)
        script = resolve_init_script(config.init_script, wt_root)
        if script:
            ctx = InitContext(
                wt_root=wt_root,
                repo_root=repo_root,
                worktree_path=worktree_path,
                feat_name=normalized,
                branch=branch,
                base_branch=base_branch,
            )
            success = run_init_script(script, ctx, console, strict=strict_init)
            if not success and strict_init:
                # Cleanup: remove worktree and state
                console.print("[dim]Cleaning up failed worktree...[/dim]")
                worktree_remove(worktree_path, force=True, cwd=repo_root)
                delete_branch(branch, force=True, cwd=repo_root)
                state.remove_worktree(str(worktree_path))
                state.save(get_state_path(repo_root))
                raise typer.Exit(1)

    if not no_ai:
        launch_ai_tui(config.default_ai_tui, worktree_path)


@app.command()
@error_handler
def checkout(
    branch: Annotated[str, typer.Argument(help="Branch name to checkout")],
    print_path: Annotated[
        bool, typer.Option("--print-path", "-p", help="Print path only")
    ] = False,
    ai: Annotated[
        bool, typer.Option("--ai", help="Launch AI TUI after checkout")
    ] = False,
    no_init: Annotated[
        bool, typer.Option("--no-init", help="Skip init script")
    ] = False,
    strict_init: Annotated[
        bool, typer.Option("--strict-init", help="Fail if init script fails")
    ] = False,
) -> None:
    """Checkout an existing branch into a worktree."""
    repo_root = get_validated_repo_root()
    config = ensure_config(repo_root)
    ensure_worktrees_gitignore(repo_root)

    worktrees = worktree_list(cwd=repo_root)
    for worktree in worktrees:
        if worktree.get("branch") == branch:
            path = Path(worktree["path"])
            if print_path:
                print(path)
            else:
                console.print(f"Branch already in worktree: [cyan]{path}[/cyan]")
            if ai:
                launch_ai_tui(config.default_ai_tui, path)
            return

    if not branch_exists(branch, cwd=repo_root):
        if not print_path:
            console.print(
                f"[dim]Fetching branch '{branch}' from {config.remote}...[/dim]"
            )
        if not fetch_branch(config.remote, branch, cwd=repo_root):
            raise BranchNotFoundError(branch)

    feat_name = derive_feat_name_from_branch(branch, config.branch_prefix)
    worktree_path = repo_root / config.worktrees_dir / feat_name
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    worktree_add_existing(worktree_path, branch, cwd=repo_root)

    state = WtState.load(get_state_path(repo_root))
    state.add_worktree(feat_name, branch, str(worktree_path), config.base_branch)
    state.save(get_state_path(repo_root))

    if print_path:
        print(worktree_path)
    else:
        console.print(f"[green]Created worktree:[/green] {worktree_path}")

    # Run init script if configured
    if not no_init:
        wt_root = get_wt_dir(repo_root)
        script = resolve_init_script(config.init_script, wt_root)
        if script:
            ctx = InitContext(
                wt_root=wt_root,
                repo_root=repo_root,
                worktree_path=worktree_path,
                feat_name=feat_name,
                branch=branch,
                base_branch=config.base_branch,
            )
            success = run_init_script(script, ctx, console, strict=strict_init)
            if not success and strict_init:
                # Cleanup: remove worktree and state
                if not print_path:
                    console.print("[dim]Cleaning up failed worktree...[/dim]")
                worktree_remove(worktree_path, force=True, cwd=repo_root)
                state.remove_worktree(str(worktree_path))
                state.save(get_state_path(repo_root))
                raise typer.Exit(1)

    if ai:
        launch_ai_tui(config.default_ai_tui, worktree_path)


@app.command()
@error_handler
def pr(
    base: Annotated[
        str | None, typer.Option("--base", "-b", help="Base branch for PR")
    ] = None,
    title: Annotated[str | None, typer.Option("--title", "-t", help="PR title")] = None,
    body: Annotated[str | None, typer.Option("--body", help="PR body")] = None,
    draft: Annotated[
        bool, typer.Option("--draft", "-d", help="Create as draft PR")
    ] = False,
    no_push: Annotated[
        bool,
        typer.Option("--no-push", help="Don't push, require already pushed"),
    ] = False,
) -> None:
    """Create a pull request for the current worktree."""
    repo_root = get_validated_repo_root()
    worktree_root = get_worktree_root(cwd=Path.cwd())
    if worktree_root == repo_root:
        raise NotInWorktreeError()

    config = ensure_config(repo_root)
    check_gh_installed()

    cwd = Path.cwd()
    current_branch = get_current_branch(cwd=cwd)

    state = WtState.load(get_state_path(repo_root))
    entry = state.find_by_branch(current_branch)
    base_branch = base or (entry.base if entry else config.base_branch)

    if has_uncommitted_changes(cwd=cwd):
        console.print("[yellow]Auto-committing uncommitted changes...[/yellow]")
        git_add_all(cwd=cwd)
        git_commit(cwd=cwd, message=f"implement: {current_branch}")
        console.print(f"[green]Created commit:[/green] {current_branch}")

    if no_push:
        upstream = get_upstream_branch(cwd=cwd)
        if upstream is None:
            raise UsageError(
                "Branch has no upstream set.",
                suggestion="Run without --no-push to set the upstream.",
            )
    else:
        upstream = get_upstream_branch(cwd=cwd)
        if upstream is None:
            console.print(
                f"[dim]Pushing branch '{current_branch}' to {config.remote}...[/dim]"
            )
            push_branch(
                current_branch, set_upstream=True, remote=config.remote, cwd=cwd
            )

    console.print("[dim]Creating pull request...[/dim]")
    pr_url = create_pr(
        base=base_branch,
        head=current_branch,
        title=title,
        body=body,
        draft=draft,
        cwd=cwd,
    )

    console.print(f"[green]Pull request created:[/green] {pr_url}")


@app.command()
@error_handler
def delete(
    name: Annotated[str | None, typer.Argument(help="Worktree name to delete")] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force delete even with uncommitted/unpushed changes"
        ),
    ] = False,
    remote: Annotated[
        bool, typer.Option("--remote", "-r", help="Also delete remote branch")
    ] = False,
) -> None:
    """Delete a worktree and its branch."""
    repo_root = get_validated_repo_root()
    state = WtState.load(get_state_path(repo_root))
    cwd = Path.cwd()
    worktree_root = get_worktree_root(cwd=cwd)
    in_worktree = worktree_root != repo_root
    current_branch = get_current_branch(cwd=cwd)

    if name is not None:
        entry = state.find_by_feat_name(name)
        if entry is None:
            entry = state.find_by_branch(name)
        if entry is None:
            raise WorktreeNotFoundError(name)
    elif in_worktree:
        entry = state.find_by_path(str(worktree_root)) or state.find_by_branch(
            current_branch
        )
        if entry is None:
            raise NotInWorktreeError()
    else:
        if not state.worktrees:
            raise NoWorktreesError()
        if not sys.stdin.isatty():
            raise UsageError(
                "Worktree name required when not in interactive mode.",
                suggestion="Run 'wt delete <name>' or use a TTY.",
            )
        prompt_console = Console(stderr=True)
        prompt_console.print("[bold]Available worktrees:[/bold]")
        for idx, wt in enumerate(state.worktrees, start=1):
            prompt_console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")
        choice = typer.prompt("Select worktree to delete", type=int)
        if choice < 1 or choice > len(state.worktrees):
            raise UsageError("Invalid selection.")
        entry = state.worktrees[choice - 1]

    worktree_path = Path(entry.path)
    branch = entry.branch
    path_missing = not worktree_path.exists()

    if path_missing:
        console.print(
            f"[yellow]Warning:[/yellow] Worktree path '{worktree_path}' not found on disk. "
            "Treating as stale entry."
        )

    if not force and not path_missing:
        worktree_cwd = worktree_path
        if has_uncommitted_changes(cwd=worktree_cwd):
            raise UncommittedChangesError()
        if has_unpushed_commits(cwd=worktree_cwd):
            raise UnpushedCommitsError()

    os.chdir(repo_root)
    console.print(f"[dim]Removing worktree at {worktree_path}...[/dim]")
    try:
        worktree_remove(worktree_path, force=force, cwd=repo_root)
    except subprocess.CalledProcessError as exc:
        if path_missing:
            console.print(
                "[yellow]Warning:[/yellow] Could not remove worktree (path missing): "
                f"{exc.stderr or 'unknown error'}"
            )
        else:
            raise

    console.print(f"[dim]Deleting branch '{branch}'...[/dim]")
    delete_branch(branch, force=force, cwd=repo_root)

    if remote:
        config = ensure_config(repo_root)
        console.print(f"[dim]Deleting remote branch '{branch}'...[/dim]")
        try:
            delete_remote_branch(config.remote, branch, cwd=repo_root)
        except subprocess.CalledProcessError as exc:
            console.print(
                "[yellow]Warning:[/yellow] Failed to delete remote branch: "
                f"{exc.stderr or exc}"
            )

    state.remove_worktree(str(worktree_path))
    state.save(get_state_path(repo_root))

    if path_missing:
        console.print(
            f"[green]Cleaned up stale worktree entry and deleted branch:[/green] {branch}"
        )
    else:
        console.print(f"[green]Deleted worktree and branch:[/green] {branch}")


@app.command()
@error_handler
def merge(
    base: Annotated[
        str | None, typer.Option("--base", "-b", help="Base branch to merge into")
    ] = None,
    no_push: Annotated[
        bool,
        typer.Option("--no-push", help="Don't push the base branch after merge"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Proceed even with uncommitted changes (may lose local changes)",
        ),
    ] = False,
    no_ff: Annotated[
        bool,
        typer.Option("--no-ff", help="Create a merge commit (disable fast-forward)"),
    ] = False,
    ff_only: Annotated[
        bool,
        typer.Option("--ff-only", help="Refuse merge unless fast-forward is possible"),
    ] = False,
) -> None:
    """Merge the current worktree branch into the base branch, then delete the worktree."""
    repo_root = get_validated_repo_root()
    worktree_root = get_worktree_root(cwd=Path.cwd())
    if worktree_root == repo_root:
        raise NotInWorktreeError()

    if no_ff and ff_only:
        raise UsageError("Cannot use --no-ff and --ff-only together.")

    config = ensure_config(repo_root)
    cwd = Path.cwd()
    current_branch = get_current_branch(cwd=cwd)

    state = WtState.load(get_state_path(repo_root))
    entry = state.find_by_path(str(worktree_root)) or state.find_by_branch(
        current_branch
    )
    if entry is None:
        raise NotInWorktreeError()

    base_branch = base or entry.base or config.base_branch
    branch = entry.branch
    worktree_path = Path(entry.path)

    if not force and has_uncommitted_changes(cwd=cwd):
        console.print("[yellow]Auto-committing uncommitted changes...[/yellow]")
        git_add_all(cwd=cwd)
        git_commit(cwd=cwd, message=f"implement: {branch}")
        console.print(f"[green]Created commit:[/green] {branch}")

    if not branch_exists(base_branch, cwd=repo_root):
        console.print(
            f"[dim]Fetching base branch '{base_branch}' from {config.remote}...[/dim]"
        )
        if not fetch_branch(config.remote, base_branch, cwd=repo_root):
            raise BaseBranchNotFoundError(base_branch)

    os.chdir(repo_root)
    console.print(f"[dim]Checking out '{base_branch}'...[/dim]")
    checkout_branch(base_branch, cwd=repo_root)

    console.print(f"[dim]Merging '{branch}' into '{base_branch}'...[/dim]")
    merge_branch(branch, no_ff=no_ff, ff_only=ff_only, cwd=repo_root)

    # Note: Base branch is merged locally only. Push manually if needed.

    console.print(f"[dim]Removing worktree at {worktree_path}...[/dim]")
    worktree_remove(worktree_path, force=force, cwd=repo_root)

    console.print(f"[dim]Deleting branch '{branch}'...[/dim]")
    delete_branch(branch, force=force, cwd=repo_root)

    state.remove_worktree(str(worktree_path))
    state.save(get_state_path(repo_root))

    console.print(
        f"[green]Merged and deleted worktree:[/green] {branch} -> {base_branch}"
    )


@app.command()
@error_handler
def path(
    name: Annotated[
        str | None, typer.Argument(help="Feature name of the worktree")
    ] = None,
) -> None:
    """Print the path of a wt-managed worktree."""
    repo_root = get_validated_repo_root()
    state = WtState.load(get_state_path(repo_root))

    if name is not None:
        entry = state.find_by_feat_name(name)
        if entry is None:
            raise WorktreeNotFoundError(name)
        print(entry.path)
        return

    if not state.worktrees:
        raise NoWorktreesError()

    prompt_console = Console(stderr=True)
    prompt_console.print("[bold]Available worktrees:[/bold]")
    for idx, wt in enumerate(state.worktrees, start=1):
        prompt_console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")

    choice = typer.prompt("Select worktree", type=int, err=True)
    if choice < 1 or choice > len(state.worktrees):
        raise UsageError("Invalid selection.")

    selected = state.worktrees[choice - 1]
    print(selected.path)


@app.command(name="list")
@error_handler
def list_cmd(
    all_flag: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Also show remote branches not tracked locally"
        ),
    ] = False,
) -> None:
    """List all wt-managed worktrees and optionally remote branches."""
    from datetime import datetime

    from rich.table import Table

    repo_root = get_validated_repo_root()
    state = WtState.load(get_state_path(repo_root))

    local_branches = {wt.branch for wt in state.worktrees}

    if not state.worktrees and not all_flag:
        raise NoWorktreesError()

    def format_relative_time(iso_time: str | None) -> str:
        """Format ISO timestamp as relative time."""
        if not iso_time:
            return "[dim]-[/dim]"
        try:
            # Parse ISO format, handle timezone
            time_str = iso_time.replace("Z", "+00:00")
            if "+" in time_str or time_str.endswith("Z"):
                # Has timezone info
                dt = datetime.fromisoformat(time_str)
            else:
                dt = datetime.fromisoformat(time_str)
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            seconds = diff.total_seconds()
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                mins = int(seconds // 60)
                return f"{mins}m ago"
            elif seconds < 86400:
                hours = int(seconds // 3600)
                return f"{hours}h ago"
            elif seconds < 604800:
                days = int(seconds // 86400)
                return f"{days}d ago"
            elif seconds < 2592000:
                weeks = int(seconds // 604800)
                return f"{weeks}w ago"
            else:
                months = int(seconds // 2592000)
                return f"{months}mo ago"
        except Exception:
            return "[dim]-[/dim]"

    def format_ahead_behind(ahead: int, behind: int) -> str:
        """Format ahead/behind as a compact string."""
        if ahead == 0 and behind == 0:
            return "[dim]-[/dim]"
        parts = []
        if ahead > 0:
            parts.append(f"[green]+{ahead}[/green]")
        if behind > 0:
            parts.append(f"[red]-{behind}[/red]")
        return " ".join(parts)

    table = Table(title="Worktrees")
    table.add_column("name", style="cyan")
    table.add_column("branch")
    table.add_column("status")
    table.add_column("sync")
    table.add_column("activity", style="dim")

    for wt in state.worktrees:
        wt_path = Path(wt.path)
        if wt_path.exists():
            is_dirty = has_uncommitted_changes(cwd=wt_path)
            status = "[yellow]dirty[/yellow]" if is_dirty else "[green]clean[/green]"
            ahead, behind = get_ahead_behind(cwd=wt_path)
            sync_status = format_ahead_behind(ahead, behind)
            last_commit = get_last_commit_time(cwd=wt_path)
            activity = format_relative_time(last_commit)
        else:
            status = "[red]missing[/red]"
            sync_status = "[dim]-[/dim]"
            activity = "[dim]-[/dim]"

        table.add_row(wt.feat_name, wt.branch, status, sync_status, activity)

    if all_flag:
        remote_branches = list_remote_branches(cwd=repo_root)
        for branch in remote_branches:
            if branch not in local_branches:
                table.add_row(
                    "[dim]-[/dim]",
                    f"[yellow]{branch}[/yellow]",
                    "[dim]remote[/dim]",
                    "[dim]-[/dim]",
                    "[dim]-[/dim]",
                )

    console.print(table)


@app.command()
@error_handler
def status(
    name: Annotated[str | None, typer.Argument(help="Worktree name")] = None,
) -> None:
    """Show detailed status for a worktree (or current worktree)."""
    from datetime import datetime

    from rich.panel import Panel
    from rich.table import Table

    repo_root = get_validated_repo_root()
    state = WtState.load(get_state_path(repo_root))
    cwd = Path.cwd()
    worktree_root = get_worktree_root(cwd=cwd)

    if name is not None:
        entry = state.find_by_feat_name(name)
        if entry is None:
            entry = state.find_by_branch(name)
        if entry is None:
            raise WorktreeNotFoundError(name)
    elif worktree_root != repo_root:
        current_branch = get_current_branch(cwd=cwd)
        entry = state.find_by_path(str(worktree_root)) or state.find_by_branch(
            current_branch
        )
        if entry is None:
            raise NotInWorktreeError()
    else:
        if not state.worktrees:
            raise NoWorktreesError()
        if not sys.stdin.isatty():
            raise UsageError(
                "Worktree name required when not in interactive mode.",
                suggestion="Run 'wt status <name>'.",
            )
        prompt_console = Console(stderr=True)
        prompt_console.print("[bold]Available worktrees:[/bold]")
        for idx, wt in enumerate(state.worktrees, start=1):
            prompt_console.print(f"  {idx}. {wt.feat_name} [dim]({wt.branch})[/dim]")
        choice = typer.prompt("Select worktree", type=int)
        if choice < 1 or choice > len(state.worktrees):
            raise UsageError("Invalid selection.")
        entry = state.worktrees[choice - 1]

    wt_path = Path(entry.path)
    path_exists = wt_path.exists()

    # Collect status info
    info_table = Table.grid(padding=(0, 2))
    info_table.add_column(style="bold")
    info_table.add_column()

    info_table.add_row("Feature:", entry.feat_name)
    info_table.add_row("Branch:", entry.branch)
    info_table.add_row("Base:", entry.base)
    info_table.add_row("Path:", entry.path)
    info_table.add_row("Created:", entry.created_at[:19] if entry.created_at else "-")

    if path_exists:
        is_dirty = has_uncommitted_changes(cwd=wt_path)
        status_str = "[yellow]dirty[/yellow]" if is_dirty else "[green]clean[/green]"
        info_table.add_row("Status:", status_str)

        ahead, behind = get_ahead_behind(cwd=wt_path)
        if ahead == 0 and behind == 0:
            sync_str = "[green]in sync[/green]"
        else:
            parts = []
            if ahead > 0:
                parts.append(f"[green]{ahead} ahead[/green]")
            if behind > 0:
                parts.append(f"[red]{behind} behind[/red]")
            sync_str = ", ".join(parts)
        info_table.add_row("Sync:", sync_str)

        last_commit = get_last_commit_time(cwd=wt_path)
        if last_commit:
            try:
                dt = datetime.fromisoformat(last_commit.replace("Z", "+00:00"))
                info_table.add_row("Last commit:", dt.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                info_table.add_row("Last commit:", last_commit[:19])
        else:
            info_table.add_row("Last commit:", "-")

        # Check merge status
        merged = get_branch_merged_status(entry.branch, entry.base, cwd=repo_root)
        merge_str = "[green]merged[/green]" if merged else "[yellow]not merged[/yellow]"
        info_table.add_row("Merged to base:", merge_str)
    else:
        info_table.add_row("Status:", "[red]path missing[/red]")

    # Per-worktree config (if any)
    wt_config_path = wt_path / ".wt.json" if path_exists else None
    if wt_config_path and wt_config_path.exists():
        import json

        try:
            with wt_config_path.open("r", encoding="utf-8") as f:
                wt_config = json.load(f)
            info_table.add_row("", "")
            info_table.add_row("[bold]Worktree Config:[/bold]", "")
            for key, value in wt_config.items():
                info_table.add_row(f"  {key}:", str(value))
        except Exception:
            pass

    console.print(
        Panel(info_table, title=f"[bold]{entry.feat_name}[/bold]", expand=False)
    )


@app.command()
@error_handler
def clean(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n", help="Show what would be deleted without doing it"
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Skip confirmation prompt"),
    ] = False,
    merged: Annotated[
        bool,
        typer.Option(
            "--merged", "-m", help="Only clean worktrees merged into their base"
        ),
    ] = False,
) -> None:
    """Clean up worktrees that are fully merged or stale.

    By default, only shows candidates for cleanup. Use --force to skip confirmation.
    """
    from rich.table import Table

    repo_root = get_validated_repo_root()
    state = WtState.load(get_state_path(repo_root))

    if not state.worktrees:
        console.print("[dim]No worktrees to clean.[/dim]")
        return

    candidates: list[
        tuple[str, str, str, str]
    ] = []  # (feat_name, branch, path, reason)

    for wt in state.worktrees:
        wt_path = Path(wt.path)

        # Check if path exists
        if not wt_path.exists():
            candidates.append((wt.feat_name, wt.branch, wt.path, "path missing"))
            continue

        # Only clean merged branches if --merged is set or checking all
        if merged:
            is_merged = get_branch_merged_status(wt.branch, wt.base, cwd=repo_root)
            if is_merged:
                # Extra safety: check for uncommitted changes
                if has_uncommitted_changes(cwd=wt_path):
                    candidates.append(
                        (wt.feat_name, wt.branch, wt.path, "merged (has uncommitted)")
                    )
                else:
                    candidates.append((wt.feat_name, wt.branch, wt.path, "merged"))

    if not candidates:
        console.print("[green]No worktrees eligible for cleanup.[/green]")
        return

    # Show what would be cleaned
    table = Table(
        title="Worktrees to clean" if not dry_run else "Would clean (dry run)"
    )
    table.add_column("name", style="cyan")
    table.add_column("branch")
    table.add_column("reason", style="yellow")

    for feat_name, branch, path, reason in candidates:
        table.add_row(feat_name, branch, reason)

    console.print(table)

    if dry_run:
        console.print(
            f"\n[dim]Run without --dry-run to clean {len(candidates)} worktree(s).[/dim]"
        )
        return

    # Confirm unless --force
    if not force:
        if not sys.stdin.isatty():
            console.print(
                "[yellow]Use --force to clean without confirmation in non-interactive mode.[/yellow]"
            )
            raise typer.Exit(1)
        confirm = typer.confirm(
            f"Delete {len(candidates)} worktree(s)?", default=False, err=True
        )
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Perform cleanup
    deleted = 0
    for feat_name, branch, path, reason in candidates:
        wt_path = Path(path)
        try:
            console.print(f"[dim]Removing {feat_name}...[/dim]")

            # Remove worktree if path exists
            if wt_path.exists():
                worktree_remove(wt_path, force=True, cwd=repo_root)
            else:
                # Try to prune if path is missing
                try:
                    from wt.git import run_git

                    run_git("worktree", "prune", cwd=repo_root)
                except Exception:
                    pass

            # Delete branch
            try:
                delete_branch(branch, force=True, cwd=repo_root)
            except subprocess.CalledProcessError:
                console.print(
                    f"[yellow]Warning:[/yellow] Could not delete branch '{branch}'"
                )

            # Update state
            state.remove_worktree(path)
            deleted += 1
        except Exception as exc:
            console.print(
                f"[yellow]Warning:[/yellow] Failed to clean {feat_name}: {exc}"
            )

    state.save(get_state_path(repo_root))
    console.print(f"[green]Cleaned {deleted} worktree(s).[/green]")


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", "-v", help="Show version")
    ] = False,
) -> None:
    """wt - Git worktree toolkit for feature-branch workflows."""
    if version:
        console.print(f"wt version {__version__}")
        raise typer.Exit(ExitCode.SUCCESS)

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(ExitCode.SUCCESS)

    try:
        repo_root = get_validated_repo_root()
    except WtError:
        return

    try:
        sync_state(repo_root)
    except subprocess.CalledProcessError as exc:
        console.print(
            "[yellow]Warning:[/yellow] Failed to sync state: "
            f"{exc.stderr or 'unknown error'}"
        )
    except Exception as exc:
        console.print(f"[yellow]Warning:[/yellow] Failed to sync state: {exc}")


if __name__ == "__main__":
    app()
