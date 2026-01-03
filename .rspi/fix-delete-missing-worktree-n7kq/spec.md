# Fix `wt delete` for missing worktree paths
Feature: fix-delete-missing-worktree-n7kq
Date: 2026-01-03

## Context
`wt delete` currently runs git commands with `cwd=<worktree_path>` (e.g. `git status --porcelain`) before removal. If the worktree directory has already been deleted/moved on disk but is still present in `wt` state, the command crashes with a `FileNotFoundError`.

## Requirements
- If the selected worktree `path` does not exist on disk, `wt delete` must not crash.
- In the missing-path case, treat the entry as stale and:
  - Skip dirty/unpushed safety checks that require running inside the worktree.
  - Attempt to remove the worktree via `git worktree remove <path>` from `repo_root`, but tolerate failure due to the missing path.
  - Proceed to delete the associated branch (local, and remote if `--remote` is used) using the existing delete behavior.
  - Remove the stale entry from `wt` state.
- In the normal case (path exists), preserve existing behavior and safety checks.
- User-facing output should clearly indicate when the path is missing and which safety checks were skipped.

## Non-Goals
- Recovering or reconstructing missing worktree directories.
- Changing default safety behavior when the worktree path exists.
- Altering the state file format.

## Acceptance Criteria
- `wt delete` on an entry whose `path` does not exist:
  - Exits successfully without a traceback.
  - Removes the entry from state.
  - Attempts branch deletion using the existing logic.
- `wt delete` on an entry whose `path` exists retains current behavior:
  - Still blocks when uncommitted changes exist unless `--force` is used.
  - Still blocks when unpushed commits exist unless `--force` is used.
- Test coverage includes at least one case for deleting a stale (missing-path) entry.

## Open Questions
