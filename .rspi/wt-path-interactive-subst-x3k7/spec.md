# Make `wt path` Interactive in Command Substitution
Feature: wt-path-interactive-subst-x3k7
Date: 2026-01-03

## Context
Users want to use `wt path` in shell command substitution (e.g. `cd $(wt path)`) and still get the interactive selection UI when no argument is provided. Today `wt path` blocks this by requiring `sys.stdin.isatty()`.

## Requirements
- When invoked as `wt path` with no argument, show the interactive selector regardless of whether `stdin` is a TTY.
- The interactive selector UI (list of worktrees + prompt) must not pollute stdout, so command substitution receives only the selected path.
- The selected worktree path must be printed to stdout as a single line.
- `wt path <name>` behavior remains unchanged.
- Piped input support (e.g. `echo 2 | wt path`) is not required.

## Non-Goals
- Adding additional flags (e.g. `--select`, `--print0`) for this change.
- Supporting or guaranteeing behavior when stdin is intentionally piped or redirected from non-terminal sources.
- Changing error output stream conventions across the CLI.

## Acceptance Criteria
- Running `cd $(wt path)` in an interactive shell opens the selector UI and then `cd`s into the selected worktree.
- `wt path <name>` prints exactly the stored path plus a trailing newline.
- The selector UI prints to stderr (or otherwise does not appear in stdout).
- Existing tests continue to pass.

## Open Questions
