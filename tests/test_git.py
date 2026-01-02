"""Tests for wt.git module."""
from subprocess import CompletedProcess

import wt.git as git


def test_worktree_list_parses_porcelain(monkeypatch) -> None:
    output = (
        "worktree /repo/.wt/worktrees/feature-a\n"
        "branch refs/heads/feature/a\n"
        "\n"
        "worktree /repo\n"
        "branch refs/heads/main\n"
    )

    def fake_run_git(*args, **kwargs):
        return CompletedProcess(args=["git", *args], returncode=0, stdout=output, stderr="")

    monkeypatch.setattr(git, "run_git", fake_run_git)

    worktrees = git.worktree_list()
    assert worktrees[0]["path"] == "/repo/.wt/worktrees/feature-a"
    assert worktrees[0]["branch"] == "feature/a"
    assert worktrees[1]["path"] == "/repo"
    assert worktrees[1]["branch"] == "main"
