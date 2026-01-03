# Skip Push When Remote Missing
Feature: skip-push-missing-remote-j4p2
Date: 2026-01-03

## Context
`wt new` pushes the created branch to the configured remote (default `origin`) unless `--no-push` is passed. In repos without a configured remote (common in tests and some local workflows), this fails with a git error and aborts `wt new`.

## Requirements
- `wt new` should not fail solely because the configured remote does not exist.
- If the configured remote is missing, `wt new` should skip pushing and continue creating the worktree and updating state.
- When push is skipped due to missing remote, print a warning and a suggestion to set up a remote or use `--no-push`.
- Existing behavior remains unchanged when the remote exists.

## Non-Goals
- Supporting push in repos with no network access.
- Changing default config values (e.g. remote name).
- Modifying other commands (`pr`, `merge`, etc.) unless needed for test stability.

## Acceptance Criteria
- `tests/test_merge.py::test_merge_merges_into_base_and_deletes_worktree` passes in a repo without remotes.
- Running `wt new <feat>` in a repo without `origin` succeeds and prints a warning instead of failing.
- Running `wt new <feat>` in a repo with a valid remote still pushes as before.

## Open Questions
