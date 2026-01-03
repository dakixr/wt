## Research Run (2026-01-03 14:30)

### Topic
`wt new` command's push to remote and handling of missing git remote configuration.

---

### Relevant Areas

- **`src/wt/cli.py`**: Contains the `new` command (lines 97-175) and `error_handler` decorator (lines 65-86)
- **`src/wt/git.py`**: Contains `push_branch` (lines 154-166) and `run_git` (lines 10-29)
- **`src/wt/config.py`**: Contains `WtConfig` dataclass with `remote` field defaulting to `"origin"` (line 16)
- **`src/wt/errors.py`**: Contains `CommandFailedError` (lines 25-35) and error handling patterns
- **`tests/conftest.py`**: Contains `git_repo` fixture that creates repos without remotes (lines 10-26)
- **`tests/test_config.py`**: Tests `WtConfig` defaults including `remote == "origin"` (line 10)

---

### Current Behavior

**`new` command push flow (`src/wt/cli.py` lines 140-142):**
```python
if not no_push:
    console.print(f"[dim]Pushing branch '{branch}' to {config.remote}...[/dim]")
    push_branch(branch, set_upstream=True, remote=config.remote, cwd=repo_root)
```

The push is conditional on the `--no-push` flag. When pushing, it uses `config.remote` (default `"origin"`).

**`push_branch` function (`src/wt/git.py` lines 154-166):**
```python
def push_branch(
    branch: str,
    set_upstream: bool = False,
    remote: str = "origin",
    cwd: Path | None = None,
) -> None:
    """Push a branch to a remote."""
    args = ["push"]
    if set_upstream:
        args.extend(["-u", remote, branch])
    else:
        args.append(remote)
    run_git(*args, cwd=cwd)
```

The function constructs a git push command and delegates to `run_git`.

**`run_git` function (`src/wt/git.py` lines 10-29):**
```python
def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result
```

`run_git` raises `subprocess.CalledProcessError` when `check=True` (default) and the git command fails.

**Error propagation (`src/wt/cli.py` lines 65-86):**
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

The `CalledProcessError` from `push_branch` is caught by `error_handler`, wrapped in `CommandFailedError`, and causes a generic failure message.

---

### Key Dependencies

- **`subprocess`** module: Used for running git commands
- **`WtConfig.remote`** (`src/wt/config.py` line 16): Defaults to `"origin"`, used for all remote operations
- **`error_handler` decorator**: Catches subprocess errors and converts to user-facing errors

---

### Data Flow / Control Flow

1. User runs `wt new <feat_name>` (optionally with `--no-push`)
2. `new` function in `cli.py` validates repo, config, and base branch
3. Worktree is created via `worktree_add()` (line 138)
4. If `--no-push` is false:
   - `push_branch()` is called with `branch`, `set_upstream=True`, `remote=config.remote`
   - `push_branch` calls `run_git("push", "-u", "origin", branch)`
   - If remote `"origin"` doesn't exist, git fails with error
   - `run_git` raises `CalledProcessError`
   - `error_handler` catches it and prints generic error message
5. State is saved, worktree info is displayed

---

### Constraints & Patterns

**No remote detection helper exists in `src/wt/git.py`.** The codebase does not have functions like:
- `remote_exists(remote: str, cwd: Path | None = None) -> bool`
- `get_remotes(cwd: Path | None = None) -> list[str]`

**`fetch_branch` pattern for error handling (`src/wt/git.py` lines 75-78):**
```python
def fetch_branch(remote: str, branch: str, cwd: Path | None = None) -> bool:
    """Fetch a branch from remote. Returns True if successful."""
    result = run_git("fetch", remote, f"{branch}:{branch}", cwd=cwd, check=False)
    return result.returncode == 0
```

This function uses `check=False` to avoid raising exceptions, returning a boolean instead. This pattern could be applied to push operations.

**Remote operations in codebase:**
- `push_branch`: Uses `check=True` (default), raises on failure
- `delete_remote_branch`: Uses `check=True` (default), raises on failure
- `fetch_branch`: Uses `check=False`, returns bool

**Config default (`src/wt/config.py` line 16):**
```python
remote: str = "origin"
```

The remote name is configurable but defaults to `"origin"`.

---

### Test/Build Touchpoints

**Test fixture `git_repo` (`tests/conftest.py` lines 10-26):**
```python
@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

    (repo / "README.md").write_text("# Test", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-b", "develop"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)

    return repo
```

The test fixture creates repositories **without remotes**. Tests using this fixture will fail if they attempt to push to origin.

**Test config defaults (`tests/test_config.py` line 10):**
```python
assert config.remote == "origin"
```

Config tests confirm the default remote name is `"origin"`.

**No existing tests for `wt new` command push behavior with missing remote.** The `tests/test_init.py` file exists but only tests init script functionality, not the `new` command itself.

---

### Missing / Not Found in Codebase

- **No remote existence check**: No `remote_exists()` or `get_remotes()` function in `git.py`
- **No tests for `wt new` command**: No `test_new.py` file or tests for the `new` command
- **No tests for push failure scenarios**: No tests covering what happens when remote doesn't exist
- **No graceful handling of missing remote**: `push_branch` raises on failure, no boolean-returning alternative
