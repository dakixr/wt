# Add worktree path command

Feature: add-goto-k3f9
Date: 2026-01-03

## Context
Users want a CLI command to quickly locate a `wt`-managed worktree. Because a CLI subprocess cannot change the parent shell’s working directory, the command should output the worktree path so callers can `cd "$(wt …)"` or otherwise use the path.

## Requirements
- Add a new CLI subcommand named `path`.
- When invoked with a worktree name argument, print the absolute filesystem path for that worktree to stdout.
- When invoked with no arguments, present an interactive Typer list/prompt to select from available worktrees, then print the selected worktree’s path.
- Source of available worktrees is `.wt/state.json` (the `WtState` persisted state), not `git worktree list`.
- If the requested name is not found in state, exit with a non-zero status and a clear error message.

## Non-Goals
- Actually changing the caller shell’s directory.
- Discovering non-`wt`-managed worktrees.
- Fuzzy matching/search.

## Acceptance Criteria
- `wt path <feat_name>` prints exactly one absolute path line for a worktree tracked in `.wt/state.json`.
- `wt path` prompts with a selectable list and prints the chosen worktree’s absolute path.
- If `.wt/state.json` has no worktrees, `wt path` exits non-zero with a clear message.
- If the name does not exist, `wt path <name>` exits non-zero with a clear message.
- Tests cover:
  - Successful lookup by name from state
  - Not-found behavior
  - No-worktrees behavior (non-interactive path)

## Open Questions
- None.
