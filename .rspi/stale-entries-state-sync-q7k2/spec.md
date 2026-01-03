# Automatic State Sync For Worktrees
Feature: stale-entries-state-sync-q7k2
Date: 2026-01-03

## Context
`wt` tracks worktrees in `.wt/state.json`. Users can end up with stale entries (e.g., worktree directories deleted manually). Today, stale entries may persist because commands like `wt delete` can exit early (e.g., failing `git branch -d`) before updating/saving state. The user wants sync to be transparent: `state.json` should be reconciled automatically before running any command to avoid weird issues.

## Requirements
- Automatically reconcile `.wt/state.json` before executing any `wt` subcommand.
- Reconciliation uses `git worktree list --porcelain` as the source of truth for which worktree paths/branches are currently registered with git.
- Remove entries from `state.json` that are not present in `git worktree list` (stale entries), regardless of whether their paths exist on disk.
- Do not prompt the user for sync; it runs transparently.
- Do not break `wt --version` behavior.
- Sync must not require network access.
- Sync must be resilient: failures to sync should not prevent the command from running, but should emit a warning (unless the repo cannot be validated).

## Non-Goals
- Changing branch-deletion semantics of `wt delete` beyond what is required to keep state synced.
- Adding a new public `wt sync` command (unless needed for testing/debugging).
- Automatically deleting git branches or remote branches during sync.

## Acceptance Criteria
- Running any `wt <command>` updates `.wt/state.json` to remove worktree entries that are no longer present in `git worktree list`.
- Repro: create an entry in `state.json` for a non-existent/non-registered worktree; run a harmless command (e.g., `wt list`); stale entry is removed.
- `wt delete` no longer repeatedly shows the same missing-path entries after a failed branch deletion, because the next command execution prunes the stale entry.
- `wt --version` still prints version and exits without attempting repo validation.
- Tests cover sync behavior and are deterministic.

## Open Questions
- Should sync also attempt to add missing entries for git-registered worktrees not in `state.json`? (Current requirement only mandates stale removal; adding could be a follow-up.)
