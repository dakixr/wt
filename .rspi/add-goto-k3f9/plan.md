# Plan: Add path Command

## Plan Run (2026-01-03 09:35)

### Goal / Non-Goals

**Goal:**
- Add a `path` CLI subcommand that outputs the absolute filesystem path of a wt-managed worktree, enabling shell integration via `cd "$(wt path <name>)"`.

**Non-Goals:**
- Changing the caller shell's directory (impossible from subprocess).
- Discovering non-wt-managed worktrees (git worktree list is not used).
- Fuzzy matching or search.

---

### Assumptions

1. `WtState` in `src/wt/state.py` is the authoritative source for wt-managed worktrees (per spec).
2. The `WorktreeEntry.feat_name` field is the lookup key for the `<name>` argument.
3. Interactive selection requires a TTY; if stdin is not a TTY and no name is provided, the command should fail gracefully.
4. The command should follow existing patterns: `@app.command()` + `@error_handler`, `Annotated[]` for arguments, `WtError` subclasses for errors.

---

### Implementation Steps

#### Step 1: Add new error class for worktree-not-found

**Where:** `src/wt/errors.py`  
**What:** Add `WorktreeNotFoundError(WtError)` for when a requested worktree name is not in state.  
**Why:** Follows existing error pattern; provides clear message and suggestion.

```python
class WorktreeNotFoundError(WtError):
    """Raised when a worktree name is not found in state."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Worktree '{name}' not found.",
            suggestion="Run 'wt path' without arguments to see available worktrees.",
        )
```

#### Step 2: Add new error class for no-worktrees

**Where:** `src/wt/errors.py`  
**What:** Add `NoWorktreesError(WtError)` for when state has no worktrees.  
**Why:** Distinct error for empty state; clear message.

```python
class NoWorktreesError(WtError):
    """Raised when no worktrees exist in state."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "No worktrees found.",
            suggestion="Create a worktree with 'wt new <feature>'.",
        )
```

#### Step 3: Add `find_by_feat_name` method to `WtState`

**Where:** `src/wt/state.py`  
**What:** Add a method to look up a `WorktreeEntry` by `feat_name`.  
**Why:** Spec requires lookup by name; existing methods only support branch/path lookup.

```python
def find_by_feat_name(self, feat_name: str) -> WorktreeEntry | None:
    """Find a worktree entry by feature name."""
    for item in self.worktrees:
        if item.feat_name == feat_name:
            return item
    return None
```

#### Step 4: Add `path` command to CLI

**Where:** `src/wt/cli.py`  
**What:** Add new `@app.command("path")` function with optional `name` argument.  
**Why:** Core feature implementation.

**Logic:**
1. Get repo root, load state.
2. If `name` is provided:
   - Look up by `feat_name` in state.
   - If not found, raise `WorktreeNotFoundError`.
   - Print absolute path to stdout (using `print()`, not `console.print()`, for clean output).
3. If `name` is not provided:
   - If no worktrees in state, raise `NoWorktreesError`.
   - Use `typer.prompt` with `choices` or `questionary`/`InquirerPy` for interactive selection.
   - Print selected worktree's path.

**Note on interactive selection:** Typer does not have built-in list selection. Options:
- Use `typer.prompt()` with a numbered list (simple, no extra deps).
- Use `rich.prompt.Prompt` with choices (already a dependency).

Recommend: Use a simple numbered prompt with `rich.prompt.IntPrompt` or `typer.prompt` for minimal complexity.

```python
@app.command("path")
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

    # Interactive mode
    if not state.worktrees:
        raise NoWorktreesError()

    console.print("[bold]Available worktrees:[/bold]")
    for idx, wt in enumerate(state.worktrees, start=1):
        console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")

    choice = typer.prompt("Select worktree", type=int)
    if choice < 1 or choice > len(state.worktrees):
        raise UsageError("Invalid selection.")

    selected = state.worktrees[choice - 1]
    print(selected.path)
```

#### Step 5: Import new errors in `cli.py`

**Where:** `src/wt/cli.py` (imports section)  
**What:** Add `WorktreeNotFoundError`, `NoWorktreesError` to imports from `wt.errors`.  
**Why:** Required for the new command to raise these errors.

```python
from wt.errors import (
    ...
    NoWorktreesError,
    WorktreeNotFoundError,
    ...
)
```

---

### File-Level Checklist

| File | Action |
|------|--------|
| `src/wt/errors.py` | Add `WorktreeNotFoundError`, `NoWorktreesError` classes |
| `src/wt/state.py` | Add `find_by_feat_name()` method to `WtState` |
| `src/wt/cli.py` | Add `path` command, import new errors |
| `tests/test_state.py` | Add tests for `find_by_feat_name()` (new file) |
| `tests/test_path.py` | Add tests for `path` command (new file) |

---

### Code Blocks for Key Changes

#### `src/wt/errors.py` additions (after `BranchNotFoundError`):

```python
class WorktreeNotFoundError(WtError):
    """Raised when a worktree name is not found in state."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Worktree '{name}' not found.",
            suggestion="Run 'wt path' without arguments to see available worktrees.",
        )


class NoWorktreesError(WtError):
    """Raised when no worktrees exist in state."""

    exit_code = ExitCode.USAGE_ERROR

    def __init__(self) -> None:
        super().__init__(
            "No worktrees found.",
            suggestion="Create a worktree with 'wt new <feature>'.",
        )
```

#### `src/wt/state.py` addition (after `find_by_path`):

```python
def find_by_feat_name(self, feat_name: str) -> WorktreeEntry | None:
    """Find a worktree entry by feature name."""
    for item in self.worktrees:
        if item.feat_name == feat_name:
            return item
    return None
```

#### `src/wt/cli.py` command (after `delete` command, before `main` callback):

```python
@app.command("path")
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

    # Interactive mode
    if not state.worktrees:
        raise NoWorktreesError()

    console.print("[bold]Available worktrees:[/bold]")
    for idx, wt in enumerate(state.worktrees, start=1):
        console.print(f"  {idx}. {wt.feat_name} [dim]({wt.path})[/dim]")

    choice = typer.prompt("Select worktree", type=int)
    if choice < 1 or choice > len(state.worktrees):
        raise UsageError("Invalid selection.")

    selected = state.worktrees[choice - 1]
    print(selected.path)
```

---

### Testing Plan

#### Test File: `tests/test_state.py` (new)

```python
"""Tests for wt.state module."""
from wt.state import WtState, WorktreeEntry


class TestWtStateFindByFeatName:
    def test_find_existing(self) -> None:
        state = WtState(worktrees=[
            WorktreeEntry(
                feat_name="my-feature",
                branch="feature/my-feature",
                path="/repo/.wt/worktrees/my-feature",
                base="develop",
                created_at="2026-01-01T00:00:00",
            )
        ])
        entry = state.find_by_feat_name("my-feature")
        assert entry is not None
        assert entry.path == "/repo/.wt/worktrees/my-feature"

    def test_find_missing(self) -> None:
        state = WtState(worktrees=[])
        entry = state.find_by_feat_name("nonexistent")
        assert entry is None
```

#### Test File: `tests/test_path.py` (new)

Use `typer.testing.CliRunner` to invoke the CLI.

```python
"""Tests for wt path command."""
import json
from pathlib import Path

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def setup_state(repo: Path, worktrees: list[dict]) -> None:
    """Helper to create .wt/state.json."""
    wt_dir = repo / ".wt"
    wt_dir.mkdir(parents=True, exist_ok=True)
    state_path = wt_dir / "state.json"
    state_path.write_text(json.dumps({"worktrees": worktrees}), encoding="utf-8")


class TestGotoPathByName:
    def test_success(self, git_repo: Path) -> None:
        setup_state(git_repo, [
            {
                "feat_name": "my-feature",
                "branch": "feature/my-feature",
                "path": str(git_repo / ".wt/worktrees/my-feature"),
                "base": "develop",
                "created_at": "2026-01-01T00:00:00",
            }
        ])
        result = runner.invoke(app, ["path", "my-feature"], env={"PWD": str(git_repo)})
        # Note: CliRunner may need cwd handling; adjust as needed
        assert result.exit_code == 0
        assert "my-feature" in result.stdout

    def test_not_found(self, git_repo: Path) -> None:
        setup_state(git_repo, [])
        result = runner.invoke(app, ["path", "nonexistent"], env={"PWD": str(git_repo)})
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower() if result.stderr else "not found" in result.stdout.lower()


class TestGotoPathNoArgs:
    def test_no_worktrees(self, git_repo: Path) -> None:
        setup_state(git_repo, [])
        result = runner.invoke(app, ["path"], env={"PWD": str(git_repo)})
        assert result.exit_code != 0
        assert "no worktrees" in result.stdout.lower()
```

**Note:** The `CliRunner` from Typer may require `monkeypatch` or `chdir` to set the working directory. Adjust test setup to ensure `get_repo_root()` returns the test repo.

#### Commands to Run

```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_state.py tests/test_path.py -v

# Run with coverage
pytest tests/ --cov=wt --cov-report=term-missing
```

---

### Acceptance Criteria Mapping

| Acceptance Criterion | Implementation | Test |
|---------------------|----------------|------|
| `wt path <feat_name>` prints exactly one absolute path line | `path` command with `name` arg, uses `print(entry.path)` | `TestGotoPathByName.test_success` |
| `wt path` prompts with selectable list and prints chosen path | Interactive mode with numbered list + `typer.prompt` | Manual testing (interactive) |
| If `.wt/state.json` has no worktrees, exits non-zero with clear message | `NoWorktreesError` raised | `TestGotoPathNoArgs.test_no_worktrees` |
| If name does not exist, exits non-zero with clear message | `WorktreeNotFoundError` raised | `TestGotoPathByName.test_not_found` |
| Tests cover successful lookup by name | `find_by_feat_name` + CLI test | `TestWtStateFindByFeatName.test_find_existing`, `TestGotoPathByName.test_success` |
| Tests cover not-found behavior | CLI test | `TestGotoPathByName.test_not_found` |
| Tests cover no-worktrees behavior (non-interactive) | CLI test | `TestGotoPathNoArgs.test_no_worktrees` |

---

### Open Questions

None. All requirements are clear and implementation path is well-defined.

---

## Approval

**Status:** APPROVED  
**Approved by:** user  
**Approved at:** 2026-01-03  
**Notes:** Approved after renaming command to `wt path`.

## Implementation Notes (2026-01-03 09:29)

### Changes Made
- src/wt/errors.py
- src/wt/state.py
- src/wt/cli.py
- tests/test_state.py
- tests/test_path.py

### Notes / Deviations
- Added a TTY guard for interactive selection; no deviations from plan.
- Printed interactive list to stderr to keep stdout path output clean.

### Commands Run
- `pytest tests -v` (failed: pytest not found)
- `python -m pytest tests -v` (failed: python not found)
- `python3 -m pytest tests -v` (failed: pytest not installed)

### Validation Results
- Not run (pytest not installed).

### Follow-ups
- Install pytest in the environment and rerun the test suite.
