# Plan

## Plan Run (2026-01-03 18:45)

### Goal / Non-Goals

**Goal:**
- Make `wt delete` handle stale worktree entries gracefully when the worktree directory has been manually deleted from disk but still exists in `wt` state.
- Skip safety checks (uncommitted/unpushed) when the path is missing.
- Tolerate `git worktree remove` failure for missing paths.
- Still delete the associated branch and clean up state.
- Provide clear user feedback when operating on a stale entry.

**Non-Goals:**
- Recovering or reconstructing missing worktree directories.
- Changing default safety behavior when the worktree path exists.
- Altering the state file format.
- Adding a "sync" or "prune" command (out of scope).

---

### Assumptions

1. The worktree entry in state contains a valid `path` field (string) that can be converted to a `Path` object.
2. `Path.exists()` is a reliable check for whether the worktree directory is present on disk.
3. `git worktree remove` on a missing path will fail with a non-zero exit code (this is expected and should be tolerated).
4. Branch deletion via `delete_branch()` does not require the worktree directory to exist (it runs from `repo_root`).
5. State removal via `state.remove_worktree()` does not require the worktree directory to exist.

---

### Implementation Steps

#### Step 1: Add path existence check in `delete` command

**Where:** `src/wt/cli.py`, lines 399-404 (safety checks block)

**What:** Before running `has_uncommitted_changes()` and `has_unpushed_commits()`, check if `worktree_path.exists()`. If the path is missing, set a flag `path_missing = True` and skip the safety checks entirely.

**Why:** These git commands require running inside the worktree directory. If the directory doesn't exist, they will raise `FileNotFoundError` or `subprocess.CalledProcessError`.

```python
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
```

#### Step 2: Tolerate `worktree_remove` failure for missing paths

**Where:** `src/wt/cli.py`, line 411 (worktree removal)

**What:** Wrap the `worktree_remove()` call in a try/except block. If `path_missing` is True, catch `subprocess.CalledProcessError` and log a warning instead of crashing.

**Why:** `git worktree remove <path>` will fail if the path doesn't exist. For stale entries, we want to continue with branch deletion and state cleanup.

```python
os.chdir(repo_root)
console.print(f"[dim]Removing worktree at {worktree_path}...[/dim]")
try:
    worktree_remove(worktree_path, force=force, cwd=repo_root)
except subprocess.CalledProcessError as exc:
    if path_missing:
        console.print(
            f"[yellow]Warning:[/yellow] Could not remove worktree (path missing): "
            f"{exc.stderr or 'unknown error'}"
        )
    else:
        raise
```

#### Step 3: Update user-facing output for stale entries

**Where:** `src/wt/cli.py`, line 430 (success message)

**What:** Modify the success message to indicate when a stale entry was cleaned up.

**Why:** Users should understand that the operation handled a stale entry differently than a normal deletion.

```python
if path_missing:
    console.print(f"[green]Cleaned up stale worktree entry and deleted branch:[/green] {branch}")
else:
    console.print(f"[green]Deleted worktree and branch:[/green] {branch}")
```

#### Step 4: Reorder variable assignments for clarity

**Where:** `src/wt/cli.py`, lines 406-407

**What:** Move `worktree_path = Path(entry.path)` and `branch = entry.branch` to before the safety checks block, so `path_missing` can be computed early.

**Why:** The `path_missing` flag needs to be set before the safety checks to skip them appropriately.

#### Step 5: Add test for deleting stale worktree entry

**Where:** `tests/test_delete.py`

**What:** Add a new test `test_delete_stale_worktree_missing_path()` that:
1. Creates a worktree via `wt new`.
2. Manually deletes the worktree directory from disk (simulating external deletion).
3. Runs `wt delete <name>` (without `--force`).
4. Asserts exit code is 0.
5. Asserts the state no longer contains the entry.
6. Asserts the branch is deleted.
7. Asserts output contains "stale" or warning message.

**Why:** This directly tests the new behavior for the crash scenario described in the spec.

```python
def test_delete_stale_worktree_missing_path(git_repo: Path, monkeypatch) -> None:
    """Delete worktree when path has been manually removed from disk."""
    monkeypatch.chdir(git_repo)

    # Create worktree
    result = runner.invoke(app, ["new", "stale-feature", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-feature"
    assert worktree_path.exists()

    # Manually delete the worktree directory (simulating external deletion)
    import shutil
    shutil.rmtree(worktree_path)
    assert not worktree_path.exists()

    # Delete should succeed without --force (safety checks skipped)
    result = runner.invoke(app, ["delete", "stale-feature"])
    assert result.exit_code == 0
    assert "stale" in result.stdout.lower() or "warning" in result.stdout.lower()

    # Verify state is cleaned up
    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []

    # Verify branch is deleted
    branch_list = subprocess.run(
        ["git", "branch", "--list", "feature/stale-feature"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert branch_list.stdout.strip() == ""
```

#### Step 6: Add test for stale worktree with `--force` flag

**Where:** `tests/test_delete.py`

**What:** Add a test `test_delete_stale_worktree_with_force()` to ensure `--force` also works correctly for stale entries.

**Why:** Ensures the `--force` flag doesn't break the stale entry handling.

```python
def test_delete_stale_worktree_with_force(git_repo: Path, monkeypatch) -> None:
    """Delete stale worktree with --force flag."""
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["new", "stale-force", "--no-ai", "--no-push"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-force"
    import shutil
    shutil.rmtree(worktree_path)

    result = runner.invoke(app, ["delete", "stale-force", "--force"])
    assert result.exit_code == 0

    state_path = git_repo / ".wt" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["worktrees"] == []
```

#### Step 7: Add test for stale worktree with `--remote` flag

**Where:** `tests/test_delete.py`

**What:** Add a test `test_delete_stale_worktree_with_remote()` to ensure remote branch deletion still works for stale entries.

**Why:** The `--remote` flag should still attempt to delete the remote branch even when the local path is missing.

```python
def test_delete_stale_worktree_with_remote(git_repo: Path, monkeypatch) -> None:
    """Delete stale worktree with --remote flag."""
    monkeypatch.chdir(git_repo)

    # Create worktree with push (so remote branch exists)
    result = runner.invoke(app, ["new", "stale-remote", "--no-ai"])
    assert result.exit_code == 0

    worktree_path = git_repo / ".wt" / "worktrees" / "stale-remote"
    import shutil
    shutil.rmtree(worktree_path)

    result = runner.invoke(app, ["delete", "stale-remote", "--remote", "--force"])
    assert result.exit_code == 0

    # Verify remote branch is deleted
    remote_branches = subprocess.run(
        ["git", "branch", "--remotes"],
        cwd=git_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "feature/stale-remote" not in remote_branches.stdout
```

---

### File-Level Checklist

| File | Action | Description |
|------|--------|-------------|
| `src/wt/cli.py` | Modify | Add path existence check, skip safety checks for missing paths, tolerate `worktree_remove` failure, update success message |
| `tests/test_delete.py` | Modify | Add 3 new tests for stale worktree deletion scenarios |

---

### Code Blocks

#### Full modified `delete` command (lines 346-430 in `src/wt/cli.py`)

```python
@app.command()
@error_handler
def delete(
    name: Annotated[
        str | None, typer.Argument(help="Worktree name to delete")
    ] = None,
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
                f"[yellow]Warning:[/yellow] Could not remove worktree (path missing): "
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
        console.print(f"[green]Cleaned up stale worktree entry and deleted branch:[/green] {branch}")
    else:
        console.print(f"[green]Deleted worktree and branch:[/green] {branch}")
```

---

### Testing Plan

1. **Run existing tests** to ensure no regressions:
   ```bash
   pytest tests/test_delete.py -v
   ```

2. **Run new stale worktree tests**:
   ```bash
   pytest tests/test_delete.py::test_delete_stale_worktree_missing_path -v
   pytest tests/test_delete.py::test_delete_stale_worktree_with_force -v
   pytest tests/test_delete.py::test_delete_stale_worktree_with_remote -v
   ```

3. **Manual testing scenarios**:
   - Create a worktree with `wt new test-stale --no-ai --no-push`
   - Manually delete the worktree directory: `rm -rf .wt/worktrees/test-stale`
   - Run `wt delete test-stale` and verify:
     - No traceback/crash
     - Warning message about stale entry
     - State is cleaned up (`wt list` shows no entry)
     - Branch is deleted (`git branch --list feature/test-stale` returns empty)

4. **Edge case testing**:
   - Delete stale entry by branch name: `wt delete feature/test-stale`
   - Delete stale entry with `--remote` flag
   - Delete stale entry with `--force` flag
   - Ensure normal deletion (path exists) still works with safety checks

---

### Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | `wt delete` on a stale entry (path missing) exits successfully without traceback | Run `wt delete <stale-name>`, check exit code is 0 |
| 2 | Stale entry is removed from state | Check `wt list` or `state.json` |
| 3 | Branch is deleted for stale entry | Run `git branch --list <branch>`, expect empty |
| 4 | Warning message is displayed for stale entry | Check stdout contains "stale" or "Warning" |
| 5 | Safety checks are skipped for stale entry | No "uncommitted" or "unpushed" error when path missing |
| 6 | Normal deletion (path exists) retains safety checks | Create worktree with uncommitted changes, `wt delete` without `--force` should fail |
| 7 | `--force` flag works for both normal and stale entries | Test both scenarios |
| 8 | `--remote` flag works for stale entries | Remote branch is deleted |
| 9 | All existing tests pass | `pytest tests/test_delete.py` passes |
| 10 | New tests for stale worktree scenarios pass | 3 new tests pass |

---

## Approval

Status: APPROVED
Approved by: user
Approved at: 2026-01-03
Notes: Implement option 1 (stale entry cleanup): when worktree path missing, skip checks, tolerate worktree remove failure, delete branch, clean state.

## Implementation Notes
- Updated `src/wt/cli.py` `delete` command to detect missing worktree paths, skip safety checks, and tolerate `git worktree remove` failure when stale.
- Added stale-entry tests in `tests/test_delete.py`.
- Validated with `uv run -m pytest -q` (all tests pass).
