# Plan: Make `wt path` Interactive in Command Substitution
Feature: wt-path-interactive-subst-x3k7
Date: 2026-01-03

## Summary
Remove the `stdin` TTY gate in `wt path` so interactive selection can be used in command substitution. Ensure all UI/prompt text goes to stderr and only the selected path is printed to stdout.

## Implementation Steps
1. Update `src/wt/cli.py` `path` command (around current `sys.stdin.isatty()` check):
   - Remove the block that raises `UsageError` when `stdin` is not a TTY.
   - Keep the existing `prompt_console = Console(stderr=True)` and list rendering to stderr.
   - Change `typer.prompt(...)` call to send the prompt to stderr (use Typer's `err=True` option).
   - Keep final `print(selected.path)` to stdout.

2. Tests
   - Add a new test in `tests/test_path.py` that asserts the selector UI does not pollute stdout.
     - Strategy: invoke `wt path` in a way that avoids interactive prompting during tests.
     - Because we are not supporting pipe-input and Typer prompts are hard to simulate in `CliRunner`, keep the test focused on stream routing:
       - Monkeypatch `typer.prompt` to return a known selection (e.g., `1`).
       - Ensure `result.stdout` equals exactly the selected path plus newline.
       - Optionally assert `result.stderr` contains "Available worktrees".

3. Validation
   - Run `pytest`.
   - Manually sanity-check in a shell: `cd $(wt path)` and confirm selection UI appears and `cd` succeeds.

## Risks / Notes
- `typer.prompt(..., err=True)` support depends on Typer version; repo pins `typer>=0.12.0`.
- Interactive behavior in command substitution depends on the user's shell/terminal; this change removes the explicit blocker in `wt`.

## Approval
Status: APPROVED
Approved by: user
Approved at: 2026-01-03
Notes: User requested `cd $(wt path)` to be interactive; no pipe support needed.

## Implementation Notes (2026-01-03 21:27)
- Changes Made:
  - src/wt/cli.py
  - tests/test_path.py
- Notes / Deviations:
  - None.
- Commands Run:
  - date "+%Y-%m-%d %H:%M"
  - python -m pytest "/Users/dakixr/dev/wt/.wt/worktrees/fix-wt-path" (failed: python not found)
  - python3 -m pytest "/Users/dakixr/dev/wt/.wt/worktrees/fix-wt-path" (failed: pytest module not installed)
- Validation Results:
  - Not run (pytest unavailable in environment).
- Follow-ups:
  - Install pytest and re-run test suite.
