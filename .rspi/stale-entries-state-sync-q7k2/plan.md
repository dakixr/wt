# Plan: Automatic State Sync For Worktrees
Feature: stale-entries-state-sync-q7k2
Date: 2026-01-03

## Approval
Status: APPROVED
Approved by: user
Approved at: 2026-01-03
Notes: "sync should be transparent for the usr, run it automatically before running any cmd"; user requested implementation.

## Summary
Introduce a lightweight, transparent pre-command sync that reconciles `.wt/state.json` against `git worktree list --porcelain` before running any `wt` subcommand (except `--version`). This prevents stale entries from persisting and causing repeated weird behavior.

## Implementation Steps
1. Add state reconciliation helper
   - Add a function (likely in `src/wt/state.py` or a new small module) that:
     - Loads current state via `WtState.load(get_state_path(repo_root))`
     - Gets git worktrees via `worktree_list(cwd=repo_root)`
     - Builds the set of known worktree paths from git output
     - Removes any state entries whose `path` is not in that set
     - Saves state back only if it changed
   - Keep scope minimal: prune stale entries only (no auto-add).

2. Wire sync to run before every command
   Preferred approach: use `@app.callback()` in `src/wt/cli.py` as a pre-command hook.
   - In `main()` callback:
     - If `--version` is set, keep current early-exit behavior.
     - Otherwise, validate repo root (reuse existing repo-root validation utilities)
     - Run sync with best-effort behavior:
       - If sync fails due to git command error, print a warning and proceed.
       - If repo root cannot be validated, allow existing command behavior to surface the correct error.
   - Ensure the sync does not change the user’s CWD in a surprising way.

   Alternate fallback (if callback gets too awkward): switch script entrypoint in `pyproject.toml` to a wrapper function that calls sync then dispatches to `app`.

3. Adjust delete to be consistent (only if needed)
   - If pre-command sync is sufficient, leave `wt delete` semantics unchanged.
   - If there’s still a path where delete can re-introduce stale state, ensure delete’s state mutation still happens deterministically.

4. Add tests
   - Add tests that:
     - Create a state entry not present in `git worktree list` and assert it is pruned when running another command (e.g., `wt list`).
     - Confirm `wt --version` does not attempt sync/repo validation.
   - Prefer using existing `tests/conftest.py` repo fixture and `typer.testing.CliRunner` patterns.

5. Run test suite
   - Run `pytest` and ensure existing tests pass.

## Risks / Notes
- Callback is not wrapped by `error_handler`; any new errors must be handled carefully (warn-and-continue for sync failures).
- `git worktree list --porcelain` output may include the bare repo and detached worktrees; reconciliation should only compare by `path` and ignore entries without a `path`.

## Files Expected To Change
- `src/wt/cli.py`
- `src/wt/state.py` and/or `src/wt/git.py`
- `tests/test_state.py` and/or new tests near existing delete/list tests

## Validation
- `pytest`
- Manual repro: create bogus `state.json` entry, run `wt list`, verify it disappears.

## Implementation Notes (2026-01-03)
- Changes Made: `src/wt/state.py`, `src/wt/cli.py`, `tests/test_list.py`, `tests/test_path.py`, `.rspi/stale-entries-state-sync-q7k2/plan.md`
- Notes / Deviations:
  - Implemented pre-command sync via Typer `@app.callback()`.
  - Normalized paths during pruning to avoid macOS `/var` vs `/private/var` mismatches.
  - Updated tests to create real git worktrees where needed, since state-only entries are now pruned.
- Commands Run: `uv run pytest -q`
- Validation Results: 52 passed.
