## Research Run (2026-01-03 20:45)

### Topic
How to run automatic sync before any wt CLI command

### Relevant Areas

**CLI Core:**
- `src/wt/cli.py` - Typer app definition, error handler, main callback (lines 1-627)
- `src/wt/state.py` - State management (lines 1-84)
- `src/wt/git.py` - Git operations including `worktree_list` (lines 1-242)
- `src/wt/config.py` - Config and directory functions (lines 1-68)
- `pyproject.toml` - Entry point definition (lines 1-26)

### Current Behavior

**Typer App Structure (cli.py:61-65):**

```python
app = typer.Typer(
    name="wt",
    help="Git worktree toolkit for feature-branch workflows.",
    no_args_is_help=True,
)
```

**Main Callback (cli.py:613-622):**

```python
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
```

The `@app.callback()` decorator is invoked before any subcommand. It currently only handles the `--version` flag.

**Error Handler Decorator (cli.py:69-90):**

```python
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
```

Each command is decorated with `@error_handler`, wrapping individual command functions.

**Command Decorators Pattern:**

All commands use the pattern:
```python
@app.command()
@error_handler
def command_name(...):
    ...
```

**State Loading in Commands:**

Commands that use state call `WtState.load(get_state_path(repo_root))` at runtime:
- `new`: line 158
- `checkout`: line 239
- `pr`: line 303
- `delete`: line 359
- `merge`: line 489
- `path`: line 547
- `list_cmd`: line 586

**Worktree List Function (git.py:111-132):**

```python
def worktree_list(cwd: Path | None = None) -> list[dict[str, str]]:
    """List all worktrees with porcelain output."""
    result = run_git("worktree", "list", "--porcelain", cwd=cwd)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line[9:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = "true"
        elif line == "detached":
            current["detached"] = "true"
    if current:
        worktrees.append(current)
    return worktrees
```

**State Path (state.py:81-83):**

```python
def get_state_path(repo_root: Path) -> Path:
    """Get the state file path."""
    return repo_root / ".wt" / "state.json"
```

**Entry Point (pyproject.toml:15-16):**

```toml
[project.scripts]
wt = "wt.cli:app"
```

### Key Dependencies

**Libraries:**
- `typer>=0.12.0` - CLI framework
- `rich>=13.0.0` - Terminal output

**Data Structures:**
- `WtState` with `worktrees: list[WorktreeEntry]`
- `WorktreeEntry` with fields: `feat_name`, `branch`, `path`, `base`, `created_at`

**Git Commands:**
- `git worktree list --porcelain` - Returns all worktrees with path and branch info

### Data Flow / Control Flow

**Current Command Execution Flow:**

```
User runs: wt <command> <args>
    ↓
Typer instantiates app and dispatches to command
    ↓
If --version flag in callback: exit early
    ↓
Command decorator calls function with @error_handler
    ↓
Command function executes:
    - get_validated_repo_root() → Path
    - ensure_config(repo_root) → WtConfig
    - WtState.load(get_state_path(repo_root)) → WtState
    - Perform command action
    - state.save() if modified
```

**Potential Pre-Command Hook Points:**

1. **Callback (main function)**: Runs before any subcommand, but can't easily access `repo_root` without duplicating validation logic. Currently exits early on `--version`.

2. **Custom Command Class**: Typer supports subclassing `typer.Command` to override `invoke()` method for pre/post hooks.

3. **Wrapper Around app()**: Modify entry point to call sync before `app()`.

4. **Middleware/Callback Pattern**: Typer's callback is designed for this purpose but has limited context.

### Constraints & Patterns

**Typer Pre-Command Hook Options:**

1. **Callback Approach**: Use `@app.callback()` with early return removed. Requires:
   - Get repo root first (needs `get_validated_repo_root()`)
   - Call sync function
   - Must not interfere with `--version` handling

2. **Custom Command Class**:
   ```python
   class PreCommand(typer.Command):
       def invoke(self, ctx: Context, **kwargs) -> Any:
           # Pre-hook: sync state
           # Then call parent invoke
           return super().invoke(ctx, **kwargs)
   ```
   - More complex, requires refactoring each command

3. **Entrypoint Wrapper**:
   ```python
   def main():
       sync_state_if_needed()
       app()
   ```
   - Simple, but wraps entire app including `--version`

**Current State Synchronization:**

- State is loaded on-demand per command
- No automatic reconciliation with `git worktree list`
- Stale entries only detected during `delete` (line 396: `path_missing = not worktree_path.exists()`)

**Error Handling Constraint:**

- `error_handler` wraps command execution, not callback
- Callback errors won't be handled by `error_handler`

### Test/Build Touchpoints

**Test Infrastructure:**

- `tests/conftest.py` - `git_repo` fixture for creating test repos
- No existing tests for pre-command hooks
- No existing tests for state synchronization

**Build Entry Point:**

- `pyproject.toml:16`: `wt = "wt.cli:app"`
- Can be modified to wrap app with sync function

**Files That Would Need Modification:**

For callback approach:
- `src/wt/cli.py` - Modify `main()` callback function

For entry point wrapper approach:
- `pyproject.toml` - Change entry point to wrapper function
- Or create new function in `cli.py` as new entry point

**Sync Logic Would Need:**

1. Get repo root: `get_repo_root()` or `get_validated_repo_root()`
2. Get git worktree list: `worktree_list(cwd=repo_root)`
3. Load current state: `WtState.load(get_state_path(repo_root))`
4. Reconcile:
   - Add entries for worktrees in git but not in state
   - Remove entries from state that are not in git (stale)
5. Save state: `state.save(get_state_path(repo_root))`

**Existing Reconciliation Logic in `delete` Command:**

- Stale detection: line 396 `path_missing = not worktree_path.exists()`
- State removal: line 438 `state.remove_worktree(str(worktree_path))`
- Similar pattern would apply for sync
