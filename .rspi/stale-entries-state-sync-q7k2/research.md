## Research Run (2026-01-03 20:30)

### Topic
worktree delete + stale entries + state.json sync

### Relevant Areas

**Core modules:**
- `src/wt/cli.py` - CLI commands including `delete` command (lines 343-446)
- `src/wt/state.py` - State management for `state.json` (lines 1-84)
- `src/wt/git.py` - Git operations including `worktree_remove`, `delete_branch`, `worktree_list` (lines 1-242)
- `src/wt/errors.py` - Error definitions (lines 1-174)
- `src/wt/config.py` - Configuration management (lines 1-68)

**Test files:**
- `tests/test_delete.py` - Delete command tests (lines 1-239)
- `tests/test_state.py` - State module tests (lines 1-26)
- `tests/conftest.py` - Test fixtures (lines 1-33)

### Current Behavior

**State.json Read/Write in `delete` command:**

The `delete` command reads and writes `state.json` at the following points:

1. **Load state** (line 359): `state = WtState.load(get_state_path(repo_root))`
   - Reads from `.wt/state.json`
   - Returns empty `WtState` if file doesn't exist

2. **Remove worktree entry** (line 438): `state.remove_worktree(str(worktree_path))`
   - Filters out the entry where `entry.path` matches the worktree path

3. **Save state** (line 439): `state.save(get_state_path(repo_root))`
   - Writes to `.wt/state.json` with indented JSON formatting

**Stale Entry Detection:**

Stale entries are detected by checking if the worktree path exists on disk:

- **Line 396**: `path_missing = not worktree_path.exists()`
- **Lines 398-402**: If path is missing, prints warning and treats as stale entry
- **Lines 404-409**: Uncommitted/unpushed checks are skipped when path is missing (`if not force and not path_missing`)
- **Lines 412-422**: `worktree_remove` is attempted but gracefully handles missing path with a warning
- **Lines 441-446**: Success message differs based on whether path was missing

**Branch Deletion Logic:**

Branch deletion is performed unconditionally after worktree removal:

- **Line 425**: `delete_branch(branch, force=force, cwd=repo_root)`
  - Uses `-d` flag by default (safe delete - fails if unmerged changes)
  - Uses `-D` flag if `--force` is passed
- **Lines 427-436**: Optional remote branch deletion if `--remote` flag is passed
  - Attempts `git push origin --delete <branch>`
  - Gracefully handles failure with a warning message

**Worktree Removal Logic:**

- **Lines 412-422**: `worktree_remove` is called with `force` flag
  - Uses `git worktree remove <path>` command
  - Gracefully handles missing path by catching `subprocess.CalledProcessError`

### Key Dependencies

**Libraries (from pyproject.toml):**
- `typer>=0.12.0` - CLI framework
- `rich>=13.0.0` - Terminal output formatting

**State Data Structure (from state.py):**

```python
@dataclass
class WorktreeEntry:
    feat_name: str
    branch: str
    path: str
    base: str
    created_at: str

@dataclass
class WtState:
    worktrees: list[WorktreeEntry]
```

**Git Commands Used:**
- `git worktree remove [--force] <path>` - Removes worktree at path
- `git branch [-d|-D] <branch>` - Deletes local branch
- `git push <remote> --delete <branch>` - Deletes remote branch
- `git worktree list --porcelain` - Lists all worktrees (used by `worktree_list()`)

### Data Flow / Control Flow

**Delete Command Flow:**

```
delete(name=None, force=False, remote=False)
    ↓
WtState.load(.wt/state.json)
    ↓
Determine target entry:
  - If name provided: find_by_feat_name() → find_by_branch()
  - If in worktree: find_by_path() → find_by_branch()
  - If no name & in base: interactive selection
    ↓
Check path_exists: worktree_path.exists()
    ↓
if path_missing:
    print("Warning: path not found, treating as stale")
    skip uncommitted/unpushed checks
    ↓
os.chdir(repo_root)
    ↓
worktree_remove(worktree_path, force=force)
    ↓
delete_branch(branch, force=force)
    ↓
if remote:
    delete_remote_branch(remote, branch)
    ↓
state.remove_worktree(path)
    ↓
state.save(.wt/state.json)
    ↓
Print success message (different for stale vs normal)
```

### Constraints & Patterns

**State Synchronization Constraints:**

1. **No automatic sync on startup**: State is only loaded when a command runs
2. **No validation of state vs git**: State entries are not automatically reconciled with actual git worktree state
3. **Single source of truth for state**: `state.json` is the only tracking mechanism; no other metadata files are consulted

**Stale Entry Handling Patterns:**

1. **Stale detection**: Only detected when explicitly deleting a specific entry (path existence check)
2. **No bulk stale detection**: No command to list/identify all stale entries
3. **Graceful handling**: Missing path doesn't cause failure; worktree removal attempts continue with warnings

**Error Handling Patterns (from cli.py error_handler):**

- All WtError exceptions are caught and printed with suggestions
- subprocess.CalledProcessError from git commands is converted to CommandFailedError

**State Modification Methods (from state.py):**

- `add_worktree()` - Creates entry with `created_at=datetime.now().isoformat()`
- `remove_worktree()` - Filters by path
- `find_by_feat_name()` - Linear search by `feat_name`
- `find_by_branch()` - Linear search by `branch`
- `find_by_path()` - Linear search by `path`

### Test/Build Touchpoints

**Test Files for Delete Functionality:**

- `tests/test_delete.py` (239 lines):
  - `test_delete_by_name` - Basic delete by feature name
  - `test_delete_by_branch_name` - Delete by branch name
  - `test_delete_from_worktree` - Delete from within worktree
  - `test_delete_name_not_found` - Error on non-existent entry
  - `test_delete_non_tty_requires_name` - Non-interactive mode requirement
  - `test_delete_force_bypasses_checks` - Force flag bypasses uncommitted/unpushed
  - `test_delete_with_remote_flag` - Remote branch deletion
  - `test_delete_stale_worktree_missing_path` - Stale entry with missing path
  - `test_delete_stale_worktree_with_force` - Stale entry with force flag
  - `test_delete_stale_worktree_with_remote` - Stale entry with remote flag
  - `test_delete_no_worktrees_from_base` - Error when no worktrees exist

- `tests/test_state.py` (26 lines):
  - `TestWtStateFindByFeatName.test_find_existing`
  - `TestWtStateFindByFeatName.test_find_missing`

**Test Fixture (conftest.py):**

- `git_repo` fixture creates:
  - A temporary git repository with `main` and `develop` branches
  - A fake bare remote repository
  - Initial commit with README.md

**Test Assertions:**

- State is verified by reading `state.json` directly (JSON parsing)
- Worktree existence verified via `Path.exists()`
- Branch existence verified via `git branch --list`
- Remote branches verified via `git branch --remotes`

**No Existing Sync/Repair Utilities Found:**

- No `sync` command or function exists in codebase
- No `repair`, `fix`, or `clean` commands exist
- No utility to reconcile state.json with actual git worktree list
- No bulk stale entry detection or cleanup functionality
