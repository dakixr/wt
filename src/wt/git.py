"""Git command wrappers."""
from __future__ import annotations

import subprocess
from pathlib import Path

from wt.errors import NotInGitRepoError


def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the result."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def get_repo_root(cwd: Path | None = None) -> Path:
    """Get the root of the main git repository."""
    try:
        result = run_git("rev-parse", "--git-common-dir", cwd=cwd)
    except subprocess.CalledProcessError as exc:
        raise NotInGitRepoError() from exc
    common_dir = result.stdout.strip()
    common_path = Path(common_dir)
    if not common_path.is_absolute():
        base = cwd or Path.cwd()
        common_path = (base / common_path).resolve()
    if common_path.name == ".git":
        return common_path.parent
    return common_path


def get_worktree_root(cwd: Path | None = None) -> Path:
    """Get the root of the current worktree."""
    try:
        result = run_git("rev-parse", "--show-toplevel", cwd=cwd)
    except subprocess.CalledProcessError as exc:
        raise NotInGitRepoError() from exc
    return Path(result.stdout.strip())


def is_bare_repo(cwd: Path | None = None) -> bool:
    """Check if the current repo is bare."""
    result = run_git("rev-parse", "--is-bare-repository", cwd=cwd, check=False)
    return result.stdout.strip() == "true"


def branch_exists(branch: str, cwd: Path | None = None) -> bool:
    """Check if a branch exists locally."""
    result = run_git(
        "rev-parse",
        "--verify",
        f"refs/heads/{branch}",
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def fetch_branch(remote: str, branch: str, cwd: Path | None = None) -> bool:
    """Fetch a branch from remote. Returns True if successful."""
    result = run_git("fetch", remote, f"{branch}:{branch}", cwd=cwd, check=False)
    return result.returncode == 0


def remote_exists(remote: str = "origin", cwd: Path | None = None) -> bool:
    """Check if a remote exists."""
    result = run_git("remote", "get-url", remote, cwd=cwd, check=False)
    return result.returncode == 0


def get_current_branch(cwd: Path | None = None) -> str:
    """Get the current branch name."""
    result = run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return result.stdout.strip()


def worktree_add(path: Path, branch: str, base: str, cwd: Path | None = None) -> None:
    """Create a new worktree with a new branch."""
    run_git("worktree", "add", "-b", branch, str(path), base, cwd=cwd)


def worktree_add_existing(path: Path, branch: str, cwd: Path | None = None) -> None:
    """Create a new worktree with an existing branch."""
    run_git("worktree", "add", str(path), branch, cwd=cwd)


def worktree_remove(path: Path, force: bool = False, cwd: Path | None = None) -> None:
    """Remove a worktree."""
    args = ["worktree", "remove", str(path)]
    if force:
        args.append("--force")
    run_git(*args, cwd=cwd)


def worktree_list(cwd: Path | None = None) -> list[dict[str, str]]:
    """List all worktrees with porcelain output."""
    result = run_git("worktree", "list", "--porcelain", cwd=cwd)
    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            if current:
                worktrees.append(current)
                current = {}
            continue
        if line.startswith("worktree "):
            current["path"] = line[9:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "bare":
            current["bare"] = "true"
        elif line == "detached":
            current["detached"] = "true"
    if current:
        worktrees.append(current)
    return worktrees


def has_uncommitted_changes(cwd: Path | None = None) -> bool:
    """Check for uncommitted changes."""
    result = run_git("status", "--porcelain", cwd=cwd)
    return bool(result.stdout.strip())


def has_unpushed_commits(cwd: Path | None = None) -> bool:
    """Check for unpushed commits relative to upstream."""
    result = run_git("rev-list", "@{u}..HEAD", "--count", cwd=cwd, check=False)
    if result.returncode != 0:
        return True
    return int(result.stdout.strip()) > 0


def delete_branch(branch: str, force: bool = False, cwd: Path | None = None) -> None:
    """Delete a local branch."""
    flag = "-D" if force else "-d"
    run_git("branch", flag, branch, cwd=cwd)


def delete_remote_branch(remote: str, branch: str, cwd: Path | None = None) -> None:
    """Delete a remote branch."""
    run_git("push", remote, "--delete", branch, cwd=cwd)


def push_branch(
    branch: str,
    set_upstream: bool = False,
    remote: str = "origin",
    cwd: Path | None = None,
) -> None:
    """Push a branch to a remote."""
    args = ["push"]
    if set_upstream:
        args.extend(["-u", remote, branch])
    else:
        args.append(remote)
    run_git(*args, cwd=cwd)


def get_upstream_branch(cwd: Path | None = None) -> str | None:
    """Get the upstream branch for the current branch."""
    result = run_git(
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def checkout_branch(branch: str, cwd: Path | None = None) -> None:
    """Checkout a branch."""
    run_git("checkout", branch, cwd=cwd)


def merge_branch(
    branch: str,
    *,
    no_ff: bool = False,
    ff_only: bool = False,
    cwd: Path | None = None,
) -> None:
    """Merge the given branch into the current branch."""
    args = ["merge"]
    if no_ff:
        args.append("--no-ff")
    if ff_only:
        args.append("--ff-only")
    args.append(branch)
    run_git(*args, cwd=cwd)
