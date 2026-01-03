## Research Run (2026-01-03 09:22)

### Topic

CLI command structure + how worktrees are listed/created.

### Relevant Areas

- `src/wt/cli.py` - Main CLI entry point using Typer
- `src/wt/config.py` - Configuration management (WtConfig dataclass)
- `src/wt/state.py` - State management for wt-managed worktrees (WtState dataclass)
- `src/wt/git.py` - Git command wrappers including `worktree_list()`
- `pyproject.toml` - Project dependencies (typer, rich)

### Current Behavior

**CLI Framework (Typer)**:
- CLI uses **Typer** as the command parsing library (see `src/wt/cli.py:11`: `import typer`)
- Main app instance created at `src/wt/cli.py:51-55`:
  ```python
  app = typer.Typer(
      name="wt",
      help="Git worktree toolkit for feature-branch workflows.",
      no_args_is_help=True,
  )
  ```
- Commands registered using `@app.command()` decorator on functions
- Type annotations with `Annotated[]` used for CLI arguments and options (e.g., `src/wt/cli.py:94`: `Annotated[str, typer.Argument(...)]`)
- Rich `Console` used for output (`src/wt/cli.py:12`, `src/wt/cli.py:56`)
- Error handler decorator `@error_handler` wraps commands to catch `WtError` and `CalledProcessError` (`src/wt/cli.py:59-80`)

**Existing Commands**:
1. **`new`** (`src/wt/cli.py:91-132`) - Creates new worktree for a feature
2. **`checkout`** (`src/wt/cli.py:135-186`) - Checks out existing branch into worktree
3. **`pr`** (`src/wt/cli.py:189-246`) - Creates pull request for current worktree
4. **`delete`** (`src/wt/cli.py:249-310`) - Deletes current worktree and its branch
5. **`main`** callback (`src/wt/cli.py:313-322`) - Version flag handler

**No `list` command exists** - There is no `@app.command()` for listing worktrees in the CLI.

**Worktree Listing**:
- `worktree_list()` in `src/wt/git.py:105-126` uses `git worktree list --porcelain`
- Parses porcelain output into dicts with `path`, `branch`, `bare`, `detached` keys
- Used in `checkout` command (`src/wt/cli.py:151`) to find existing worktrees by branch

**Worktree Creation Path Determination**:
- Config stores `worktrees_dir` default `.wt/worktrees` (`src/wt/config.py:17`)
- Path built as `repo_root / config.worktrees_dir / feat_name` (`src/wt/cli.py:107`, `src/wt/cli.py:172`)
- Worktrees directory created via `mkdir(parents=True, exist_ok=True)` (`src/wt/cli.py:120`, `src/wt/cli.py:173`)

**Config/State Dual Tracking**:
- **Config** (`src/wt/config.py`): `.wt/wt.json` stores persistent settings (branch_prefix, base_branch, remote, worktrees_dir)
- **State** (`src/wt/state.py`): `.wt/state.json` tracks wt-managed worktrees with metadata (feat_name, branch, path, base, created_at)
- Both use JSON serialization with dataclasses
- `add_worktree()` and `remove_worktree()` methods on `WtState` (`src/wt/state.py:44-57`)

### Key Dependencies

- **typer>=0.12.0** - CLI framework (`pyproject.toml:11`)
- **rich>=13.0.0** - Terminal output (`pyproject.toml:12`)
- **Git CLI** - Invoked via subprocess for all git operations (`src/wt/git.py:16-29`: `run_git`)

### Data Flow / Control Flow

**New Worktree Flow** (`new` command):
1. Validate repo root, load config, ensure gitignore
2. Normalize feature name, derive branch name from prefix
3. Check branch doesn't exist, fetch base branch if needed
4. Call `worktree_add()` git wrapper to create worktree
5. Load state, call `state.add_worktree()`, save state
6. Optionally launch AI TUI

**Checkout Worktree Flow** (`checkout` command):
1. Call `worktree_list()` to find existing worktrees
2. If found, print path and optionally launch AI TUI
3. If not found, derive feature name from branch, create new worktree
4. Call `worktree_add_existing()` git wrapper
5. Load state, call `state.add_worktree()`, save state

**Worktree List Flow** (via `git.worktree_list()`):
1. Execute `git worktree list --porcelain`
2. Parse each line: `worktree <path>`, `branch <ref>`, `bare`, `detached`
3. Return list of dicts

### Constraints & Patterns

- All commands use `@app.command()` + `@error_handler` decorator pattern
- Arguments use `Annotated[T, typer.Argument/Option]` pattern
- Output uses `rich.console.Console.print()` with markup tags like `[cyan]`, `[green]`, `[dim]`
- Config/state files stored in `.wt/` subdirectory of repo root
- Worktrees path derived from config's `worktrees_dir` relative to repo root
- State acts as secondary index; git's `worktree list` is source of truth for actual worktrees

### Test/Build Touchpoints

- `tests/test_git.py:7-25` - Test for `worktree_list()` parsing porcelain output
- `tests/conftest.py` - Test fixtures (not provided in reads)
- `tests/test_config.py` - Config tests (not provided in reads)
- Entry point defined in `pyproject.toml:16`: `wt = "wt.cli:app"`
