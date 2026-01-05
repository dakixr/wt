# Agent Guide for `wt`

This guide provides instructions for AI agents working on the `wt` codebase.

## Project Overview
`wt` (WorkTree) is a Git worktree toolkit designed for feature-branch workflows. It automates the creation of worktrees, branch management, and integration with AI coding assistants.

## Technical Stack
- **Language:** Python 3.12+
- **Dependency Management:** `uv`
- **CLI Framework:** `typer`
- **Output/UI:** `rich`
- **Testing:** `pytest`

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_git.py

# Run a specific test
uv run pytest tests/test_git.py::test_worktree_list_parses_porcelain

# Run with verbose output and print statements
uv run pytest -sv
```

### Linting & Type Checking
The project uses standard Python typing. While no explicit linter is configured in the repo, you should follow PEP 8 and use type hints.

```bash
# Check types (if mypy is installed)
uv run mypy src/wt
```

## Code Style & Guidelines

### 1. Imports
- Use `from __future__ import annotations` in all modules for forward-reference type hints.
- Prefer absolute imports from the `wt` package.
- Group imports: Standard library, third-party, then local `wt` modules.

```python
from __future__ import annotations

import os
from pathlib import Path

import typer

from wt.git import run_git
```

### 2. Typing
- Use type hints for all function arguments and return values.
- Use `Annotated` with `typer.Option` or `typer.Argument` for CLI parameters.
- Use `Path` from `pathlib` for all file paths.

### 3. Naming Conventions
- **Functions/Variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`

### 4. Error Handling
- Use custom exceptions defined in `src/wt/errors.py`.
- Most CLI commands should use the `@error_handler` decorator from `src/wt/cli.py`.
- Exceptions should inherit from `WtError` or its subclasses (e.g., `UsageError`).
- Provide helpful suggestions in exceptions using the `suggestion` attribute.

### 5. Git Operations
- Do NOT call `git` via `subprocess` directly in business logic.
- Use the wrappers in `src/wt/git.py`.
- If a new wrapper is needed, add it to `src/wt/git.py` using `run_git`.

### 6. Configuration & State
- Configuration is handled by `wt.config.WtConfig`.
- Persistent state (e.g., list of active worktrees) is handled by `wt.state.WtState`.
- Both use JSON serialization and are stored in the `.wt/` directory of the target repository.

### 7. CLI Design
- Use `typer` for command definitions.
- Use `rich.console.Console` for all user-facing output.
- Follow the existing pattern for command options and arguments.

## Project Structure
- `src/wt/`: Core package.
    - `cli.py`: Main entry point and CLI command definitions.
    - `git.py`: Git command wrappers.
    - `config.py`: Configuration management.
    - `state.py`: Local state management.
    - `errors.py`: Custom exception classes.
    - `init.py`: Logic for `wt init` and hooks.
- `tests/`: Pytest suite, organized by module.

## Rules of Engagement
- **Stability First:** Never break the Git state. Ensure operations that modify the filesystem or git repository are safe.
- **Conventions:** Match the existing style for docstrings and comments.
- **Verification:** Always run relevant tests after modifying code. Create new tests for new features.
