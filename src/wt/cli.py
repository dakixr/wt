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
from wt.config import ensure_config, ensure_worktrees_gitignore, get_wt_dir
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
    get_current_branch,
    get_repo_root,
    get_upstream_branch,
    get_worktree_root,
    has_uncommitted_changes,
    has_unpushed_commits,
    is_bare_repo,
    merge_branch,
    push_branch,
    worktree_add,
    worktree_add_existing,
    worktree_list,
    worktree_remove,
)
from wt.init import InitContext, resolve_init_script, run_init_script
from wt.state import WtState, get_state_path
from wt.utils import derive_feat_name_from_branch, launch_ai_tui, normalize_feat_name

app = typer.Typer(
    name="wt",
    help="Git worktree toolkit for feature-branch workflows.",
    no_args_is_help=True,
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

    if not no_push:
        console.print(f"[dim]Pushing branch '{branch}' to {config.remote}...[/dim]")
        push_branch(branch, set_upstream=True, remote=config.remote, cwd=repo_root)

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
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f", help="Force delete even with uncommitted/unpushed changes"
        ),
    ] = False,
    remote: Annotated[
        bool,
        typer.Option("--remote", "-r", help="Also delete remote branch"),
    ] = False,
) -> None:
    """Delete the current worktree and its branch."""
    repo_root = get_validated_repo_root()
    worktree_root = get_worktree_root(cwd=Path.cwd())
    if worktree_root == repo_root:
        raise NotInWorktreeError()

    config = ensure_config(repo_root)
    cwd = Path.cwd()
    current_branch = get_current_branch(cwd=cwd)

    state = WtState.load(get_state_path(repo_root))
    entry = state.find_by_path(str(worktree_root)) or state.find_by_branch(
        current_branch
    )

    if entry is None:
        raise NotInWorktreeError()

    if not force:
        if has_uncommitted_changes(cwd=cwd):
            raise UncommittedChangesError()
        if has_unpushed_commits(cwd=cwd):
            raise UnpushedCommitsError()

    worktree_path = Path(entry.path)
    branch = entry.branch

    os.chdir(repo_root)
    console.print(f"[dim]Removing worktree at {worktree_path}...[/dim]")
    worktree_remove(worktree_path, force=force, cwd=repo_root)

    console.print(f"[dim]Deleting branch '{branch}'...[/dim]")
    delete_branch(branch, force=force, cwd=repo_root)

    if remote:
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
        raise UncommittedChangesError()

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

    if not no_push:
        console.print(f"[dim]Pushing '{base_branch}' to {config.remote}...[/dim]")
        push_branch(base_branch, remote=config.remote, cwd=repo_root)

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

    if not sys.stdin.isatty():
        raise UsageError(
            "Interactive selection requires a TTY.",
            suggestion="Run 'wt path <name>' or use a TTY.",
        )

    prompt_console = Console(stderr=True)
    prompt_console.print("[bold]Available worktrees:[/bold]")
    for idx, wt in enumerate(state.worktrees, start=1):
        prompt_console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")

    choice = typer.prompt("Select worktree", type=int)
    if choice < 1 or choice > len(state.worktrees):
        raise UsageError("Invalid selection.")

    selected = state.worktrees[choice - 1]
    print(selected.path)


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", "-v", help="Show version")
    ] = False,
) -> None:
    """wt - Git worktree toolkit for feature-branch workflows."""
    if version:
        console.print(f"wt version {__version__}")
        raise typer.Exit(ExitCode.SUCCESS)


if __name__ == "__main__":
    app()
