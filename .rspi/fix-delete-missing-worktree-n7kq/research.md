# Research

## Research Run (2026-01-03 18:30)

### Topic
`wt delete` crash when selected worktree path missing.

### Relevant Areas

**Primary command handler:**
- `src/wt/cli.py:346-430` - `delete` command function

**Git operations:**
- `src/wt/git.py:103-108` - `worktree_remove()` function
- `src/wt/git.py:135-138` - `has_uncommitted_changes()` function
- `src/wt/git.py:141-146` - `has_unpushed_commits()` function

**State management:**
- `src/wt/state.py:10-18` - `WorktreeEntry` dataclass
- `src/wt/state.py:55-57` - `remove_worktree()` method
- `src/wt/state.py:66-71` - `find_by_path()` method

**Error types:**
- `src/wt/errors.py:152-161` - `WorktreeNotFoundError` class

**Tests:**
- `tests/test_delete.py:1-164` - All delete command tests

### Current Behavior

The `delete` command in `src/wt/cli.py:346-430` performs the following steps:

1. **Lines 370-398**: Look up worktree entry from state by name or branch (or interactive selection)
2. **Lines 399-404**: Run git checks on the worktree path:
   - `has_uncommitted_changes(cwd=worktree_cwd)` at line 401
   - `has_unpushed_commits(cwd=worktree_cwd)` at line 403
3. **Line 411**: Call `worktree_remove(worktree_path, force=force, cwd=repo_root)`
4. **Line 414**: Call `delete_branch(branch, force=force, cwd=repo_root)`
5. **Line 427**: Remove from state via `state.remove_worktree(str(worktree_path))`

**Crash point 1** (`src/wt/git.py:135-138`):
```python
def has_uncommitted_changes(cwd: Path | None = None) -> bool:
    """Check for uncommitted changes."""
    result = run_git("status", "--porcelain", cwd=cwd)
    return bool(result.stdout.strip())
```
This calls `run_git()` in a non-existent directory, raising `subprocess.CalledProcessError`.

**Crash point 2** (`src/wt/git.py:141-146`):
```python
def has_unpushed_commits(cwd: Path | None = None) -> bool:
    """Check for unpushed commits relative to upstream."""
    result = run_git("rev-list", "@{u}..HEAD", "--count", cwd=cwd, check=False)
    if result.returncode != 0:
        return True
    return int(result.stdout.strip()) > 0
```
Even with `check=False`, this may still fail in a non-existent directory.

**Crash point 3** (`src/wt/git.py:103-108`):
```python
def worktree_remove(path: Path, force: bool = False, cwd: Path | None = None) -> None:
    """Remove a worktree."""
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    run_git(*args, cwd=cwd)
```
This calls `git worktree remove` on a non-existent path, which fails.

### Key Dependencies

**External libraries:**
- `typer>=0.12.0` - CLI framework
- `rich>=13.0.0` - Terminal output

**Standard library:**
- `subprocess` - For running git commands

**Git operations used:**
- `git worktree remove [--force] <path>`
- `git status --porcelain`
- `git rev-list "@{u}..HEAD" --count`
- `git branch [-d|-D] <branch>`
- `git push <remote> --delete <branch>`

### Data Flow / Control Flow

```
delete command entry (cli.py:346)
         ↓
load state (cli.py:364)
         ↓
find worktree entry by name/branch (cli.py:370-397)
         ↓
check uncommitted changes (cli.py:399-404) ← CRASH HERE if path missing
         ↓
check unpushed commits (cli.py:399-404) ← CRASH HERE if path missing
         ↓
change to repo_root (cli.py:409)
         ↓
remove worktree via git (cli.py:411) ← CRASH HERE if path missing
         ↓
delete branch (cli.py:414)
         ↓
remove from state (cli.py:427)
         ↓
save state (cli.py:428)
```

### Constraints & Patterns

**State lookup pattern** (`src/wt/cli.py:370-397`):
```python
if name is not None:
    entry = state.find_by_feat_name(name)
    if entry is None:
        entry = state.find_by_branch(name)
    if entry is None:
        raise WorktreeNotFoundError(name)
```
The lookup checks state, not filesystem. The state may contain entries for worktrees that were manually deleted.

**Error handling pattern** (`src/wt/cli.py:70-91`):
```python
def error_handler(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except WtError as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(exc.exit_code)
        except subprocess.CalledProcessError as exc:
            command = " ".join(str(arg) for arg in exc.cmd)
            stderr = exc.stderr or ""
            error = CommandFailedError(command, stderr)
            console.print(f"[red]Error:[/red] {error}")
            raise typer.Exit(error.exit_code)
```
The decorator catches `CalledProcessError` and displays it as a generic command failure.

**Existing error types** (`src/wt/errors.py`):
- `WorktreeNotFoundError` - Raised when name is not in state (lines 152-161)
- No specific error for "worktree path missing from filesystem but exists in state"

### Test/Build Touchpoints

**Test file location:** `tests/test_delete.py`

**Existing tests relevant to this issue:**
- `test_delete_by_name` (lines 17-44): Creates worktree, then deletes it - path exists
- `test_delete_by_branch_name` (lines 47-60): Same pattern
- `test_delete_from_worktree` (lines 63-87): Deletes from within worktree - path exists
- `test_delete_name_not_found` (lines 89-95): Tests error when name not in state
- `test_delete_force_bypasses_checks` (lines 110-129): Path exists, uncommitted changes present

**No existing test** for deleting a worktree where the path is missing from the filesystem but the entry exists in state.

**Test fixtures** (`tests/conftest.py`):
- `git_repo` fixture provides a temporary git repository for testing
- Tests use `monkeypatch.chdir()` to change directories

**Build configuration** (`pyproject.toml`):
- Python >=3.12 required
- Uses `pytest>=8.0.0` for testing
