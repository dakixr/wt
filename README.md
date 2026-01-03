# wt - Git Worktree Toolkit

A powerful CLI tool for managing git worktrees in feature-branch workflows. Streamline your development process with intelligent worktree creation, checkout, and PR management.

[![GitHub Repo](https://img.shields.io/badge/github-dakixr/wt-blue?logo=github)](https://github.com/dakixr/wt)

## Features

- **Smart Worktree Creation**: Quickly spin up new worktrees for features with automatic naming conventions
- **Effortless Checkout**: Switch between feature branches with a single command
- **Integrated PR Workflow**: Create pull requests directly from your worktree
- **AI TUI Integration**: Launch your favorite AI coding assistant in each worktree
- **Safety First**: Validation checks for uncommitted and unpushed changes before destructive operations
- **State Tracking**: Automatically tracks your worktrees for easy management

## Installation

Install directly from GitHub using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/dakixr/wt.git
```

Or for development, clone and install in editable mode:

```bash
git clone https://github.com/dakixr/wt.git
cd wt
uv tool install -e .
```

## Quick Start

Initialize in your git repository:

```bash
cd your-git-repo
wt --version  # Verify installation
```

## Commands

### `wt new <feature-name>`

Create a new worktree for a feature branch.

```bash
wt new login-page
wt new payment-flow --base main
```

This creates:
- A worktree at `.wt/worktrees/login-page`
- A branch named `feature/login-page`
- Based on your configured base branch (default: `develop`)

### `wt checkout <branch>`

Checkout an existing branch into a worktree.

```bash
wt checkout feature/login-page
wt checkout feature/payment-flow --ai  # Launch AI TUI after checkout
```

### `wt pr`

Create a pull request from the current worktree.

```bash
wt pr
wt pr --base main --title "Add login page" --draft
```

### `wt delete`

Delete the current worktree and its branch.

```bash
wt delete
wt delete --force        # Skip safety checks
wt delete --remote       # Also delete remote branch
```

### `wt merge`

Merge the current worktree branch into its base branch (no PR), then delete the worktree.

```bash
wt merge
wt merge --no-push              # Don't push base branch after merge
wt merge --base main            # Override base branch
wt merge --no-ff                # Force a merge commit
wt merge --ff-only              # Only allow fast-forward merges
```

### `wt --version`

Show the installed version.

```bash
wt --version
```

## Configuration

wt stores configuration in `.wt/wt.json` within your repository. The default configuration:

```json
{
  "branch_prefix": "feature/",
  "base_branch": "develop",
  "remote": "origin",
  "worktrees_dir": ".wt/worktrees",
  "default_ai_tui": "opencode",
  "init_script": null
}
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `branch_prefix` | `feature/` | Prefix for feature branch names |
| `base_branch` | `develop` | Base branch for new worktrees |
| `remote` | `origin` | Remote name for push/fetch operations |
| `worktrees_dir` | `.wt/worktrees` | Directory for worktree isolation |
| `default_ai_tui` | `opencode` | Default AI TUI to launch |
| `init_script` | `null` | Script to run after creating a worktree |

Modify these values directly in `.wt/wt.json` or let wt create the file with defaults on first use.

## Initialization Scripts

wt can automatically run a script after creating a new worktree. This is useful for setting up the development environment (installing dependencies, copying config files, etc.).

### Configuration

Set `init_script` in `.wt/wt.json`:

```json
{
  "init_script": "uv sync"
}
```

Or use a custom script:

```json
{
  "init_script": ".wt/hooks/init.sh"
}
```

### Fallback Convention

If `init_script` is not set, wt automatically looks for `.wt/hooks/init.sh` and runs it if present.

### Environment Variables

The init script receives these environment variables:

| Variable | Description |
|----------|-------------|
| `WT_ROOT` | The `.wt` directory (absolute path) |
| `WT_REPO_ROOT` | The main repository root |
| `WT_WORKTREE_PATH` | The created worktree path |
| `WT_FEAT_NAME` | The normalized feature name |
| `WT_BRANCH` | The full branch name |
| `WT_BASE_BRANCH` | The base branch |

### Example Init Script

```bash
#!/bin/sh
# .wt/hooks/init.sh
set -e

echo "Setting up worktree: $WT_FEAT_NAME"

# Install dependencies
uv sync

# Copy environment template
if [ -f "$WT_REPO_ROOT/.env.template" ]; then
    cp "$WT_REPO_ROOT/.env.template" .env
fi

# Run additional project-specific setup
if [ -f "$WT_ROOT/hooks/post-setup.sh" ]; then
    . "$WT_ROOT/hooks/post-setup.sh"
fi
```

### CLI Flags

- `--no-init` — Skip the init script
- `--strict-init` — Fail and cleanup the worktree if the init script fails

```bash
wt new my-feature --no-init        # Skip init script
wt new my-feature --strict-init    # Fail if init script fails
```

## Project Structure

```
.wt/
├── worktrees/          # Isolated worktree directories
│   └── feature-name/   # Individual worktree
├── hooks/              # Optional hooks directory
│   └── init.sh         # Init script (fallback if not in config)
├── wt.json             # Configuration file
└── state.json          # Worktree state tracking
```

## Requirements

- Python 3.12+
- Git 2.0+
- [uv](https://docs.astral.sh/uv/) for installation

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open issues or pull requests at:
https://github.com/dakixr/wt
