# wt - Git Worktree Toolkit

A powerful CLI tool for managing git worktrees in feature-branch workflows.

## Installation

```bash
uv tool install git+https://github.com/dakixr/wt.git
```

## Typical Workflow

### 1. Start a New Feature
Create a new worktree and branch for your feature.

```bash
wt new login-page
```
This single command:
1.  **Creates a worktree** in `.wt/worktrees/login-page` and switches to the `feature/login-page` branch.
2.  **Runs initialization hooks** (if configured) to set up your environment.
3.  **Launches your AI coding assistant** (defaults to `opencode`) so you can start working immediately.

### 2. Develop

Develop your feature inside the worktree.

To easily navigate to the worktree, you can use the `wt path` command.
The `wt path` command returns the absolute path of the worktree, making it easy to jump in.

And combined with `cd`:
```bash
cd $(wt path)
```

### 3. Share or Submit
When ready, either merge directly or create a pull request.

#### Option A: Merge directly
Merge the feature branch into the base branch and delete the worktree.
```bash
wt merge
```

#### Option B: Create a Pull Request
Submit your changes for review.
```bash
wt pr
```

### 4. Cleanup
Once finished, delete the worktree and branch.
```bash
wt delete
```

## Key Commands

- `wt init`: Initialize `wt` in a git repository.
- `wt list`: List all managed worktrees.
- `wt status`: Show detailed status for the current worktree.
- `wt checkout <branch>`: Checkout an existing branch into a worktree.
- `wt clean`: Remove stale or merged worktrees.

## Initialization Hooks

`wt` can automatically run a script after creating a new worktree. This is useful for setting up the environment (installing dependencies, copying `.env` files, etc.).

### 1. Simple Configuration
Set `init_script` in `.wt/wt.json`:
```json
{
  ...
  "init_script": "uv sync",
  ...
}
```

### 2. Hook Script (Recommended)
If `init_script` is not set, `wt` automatically looks for `.wt/hooks/init.sh` and runs it if present.

Example `.wt/hooks/init.sh`:
```bash
#!/bin/bash
set -e
echo "Setting up $WT_FEAT_NAME..."
uv sync
cp "$WT_BASE_BRANCH_PATH/.env" .env
```

### Available Environment Variables
The following variables are available to your init scripts:

| Variable | Description |
|----------|-------------|
| `WT_ROOT` | The `.wt` directory path |
| `WT_REPO_ROOT` | The main repository root path |
| `WT_WORKTREE_PATH` | The path to the newly created worktree |
| `WT_FEAT_NAME` | The normalized feature name |
| `WT_BRANCH` | The full branch name |
| `WT_BASE_BRANCH` | The base branch used for creation |
| `WT_BASE_BRANCH_PATH` | Path to the main checkout (non-wt path), useful for copying `.env` files |

## Configuration

Configuration is stored in `.wt/wt.json`.

| Option | Default | Description |
|--------|---------|-------------|
| `branch_prefix` | `feature/` | Prefix for feature branches |
| `base_branch` | `develop` | Base branch for new worktrees |
| `worktrees_dir` | `.wt/worktrees` | Directory for worktree isolation |
| `init_script` | `null` | Script to run after creating a worktree |