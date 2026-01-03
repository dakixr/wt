## Research Run (2026-01-03 17:31)

### Topic
wt `path` command interactive behavior and TTY handling.

### Relevant Areas
- `src/wt/cli.py:473-510` - `path` command implementation
- `src/wt/errors.py:136-140` - `UsageError` class
- `tests/test_path.py:54-62` - `TestPathNoArgs` test class
- `pyproject.toml:10-13` - Dependencies (typer>=0.12.0, rich>=13.0.0)

### Current Behavior

#### Path Command Structure (`src/wt/cli.py:473-510`)
The `path` command has two execution paths:

1. **Named argument path** (lines 484-489): When `name` argument is provided, it looks up the worktree by feature name and prints the path directly to stdout.

2. **Interactive selection path** (lines 491-510): When no name is provided:
   - Checks if worktrees exist (line 491)
   - Checks if stdin is a TTY (line 494)
   - If not a TTY, raises `UsageError` (lines 495-498)
   - If TTY, prints available worktrees to stderr (lines 500-503)
   - Prompts for user input using `typer.prompt()` (line 505)
   - Prints selected path to stdout (line 510)

#### TTY Check Implementation (`src/wt/cli.py:494-498`)
```python
if not sys.stdin.isatty():
    raise UsageError(
        "Interactive selection requires a TTY.",
        suggestion="Run 'wt path <name>' or use a TTY.",
    )
```
- Uses `sys.stdin.isatty()` from Python standard library
- Raises `UsageError` with exit code `ExitCode.USAGE_ERROR` (2)
- Provides user-friendly suggestion

#### Prompt Output Streams
- **Prompt header and list**: Uses `Console(stderr=True)` to print to stderr (lines 500-503)
  ```python
  prompt_console = Console(stderr=True)
  prompt_console.print("[bold]Available worktrees:[/bold]")
  for idx, wt in enumerate(state.worktrees, start=1):
      prompt_console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")
  ```
- **Selected path output**: Uses `print()` to stdout (line 510)

#### Typer Prompt Behavior (`src/wt/cli.py:505`)
```python
choice = typer.prompt("Select worktree", type=int)
```
- `typer.prompt()` is used for interactive input
- No explicit TTY check before calling; relies on the earlier `sys.stdin.isatty()` check
- Type conversion to `int` is applied

### Key Dependencies
- **typer>=0.12.0** - CLI framework providing `typer.Typer`, `typer.prompt()`, `typer.Exit`
- **rich>=13.0.0** - Console output library providing `Console` class with `stderr=True` option

### Data Flow / Control Flow

#### Interactive Path Command Flow
```
wt path [name?]
  ├─ name is provided?
  │   ├─ Yes: state.find_by_feat_name(name) -> print(path) to stdout
  │   │
  │   └─ No: state.worktrees exists?
  │       ├─ No: raise NoWorktreesError
  │       │
  │       └─ Yes: sys.stdin.isatty()?
  │           ├─ No: raise UsageError("Interactive selection requires a TTY.")
  │           │
  │           └─ Yes:
  │               ├─ print "Available worktrees" to stderr (Console(stderr=True))
  │               ├─ typer.prompt("Select worktree", type=int)
  │               ├─ validate selection (1 <= choice <= len)
  │               ├─ invalid: raise UsageError("Invalid selection.")
  │               └─ valid: print(path) to stdout
```

#### Error Handling Flow
- All exceptions caught by `@error_handler` decorator (lines 65-86)
- `WtError` subclasses result in colored error message via `console.print()`
- `typer.Exit` raised with appropriate exit code

### Constraints & Patterns

#### Stdout vs Stderr Pattern
The codebase uses a consistent pattern for output streams:
- **Regular output** (paths, success messages): Uses `print()` or `console.print()` (stdout)
- **Prompts/interactive selection UI**: Uses `Console(stderr=True)` (stderr)
- **Error messages**: Uses `console.print()` with `[red]` and `[dim]` markup (stdout)

#### TTY Detection Pattern
The `path` command is the **only command** in `cli.py` that explicitly checks for TTY:
```python
if not sys.stdin.isatty():
    raise UsageError(...)
```
No other commands perform interactive prompting or TTY checks.

#### Rich Console Usage Pattern
- Default `Console()` for regular output (stdout)
- `Console(stderr=True)` for interactive prompts to avoid mixing with program output

### Test/Build Touchpoints

#### Test File: `tests/test_path.py`
- `TestPathByName` class (lines 22-51):
  - `test_success`: Tests `wt path <name>` with valid worktree (line 39)
  - `test_not_found`: Tests `wt path <name>` with missing worktree (line 48)
- `TestPathNoArgs` class (lines 54-62):
  - `test_no_worktrees`: Tests `wt path` without arguments when no worktrees exist (line 59)

#### Missing Test Coverage
- Interactive path selection (no name argument, with worktrees) is **not tested**
- `TyperRunner` in tests uses `result = runner.invoke(app, ["path"])` which does not simulate TTY
- No tests for `sys.stdin.isatty()` behavior or stderr output verification
- No tests for `typer.prompt()` interaction

#### Test Infrastructure
- `tests/conftest.py:10-26`: `git_repo` fixture creates temporary git repository
- `tests/test_path.py:14-19`: `setup_state()` helper creates `.wt/state.json`
- `typer.testing.CliRunner` used for command invocation

#### Typer Version and Behavior
- Typer >= 0.12.0 - `typer.prompt()` behavior with non-TTY stdin is not explicitly guarded in code
- The TTY check in `path` command prevents `typer.prompt()` from being called in non-TTY contexts
