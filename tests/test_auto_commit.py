"""Tests for auto-commit feature in merge and pr commands."""
from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def create_worktree_manually(repo: Path, feat_name: str, base_branch: str = "develop") -> Path:
    """Create a worktree manually without using wt new."""
    branch = f"feature/{feat_name}"
    worktree_path = repo / ".wt" / "worktrees" / feat_name
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(["git", "worktree", "add", "-b", branch, str(worktree_path), base_branch], cwd=repo, check=True)
    return worktree_path


def setup_state(repo: Path, worktrees: list[dict]) -> None:
    """Create .wt/state.json with provided worktrees."""
    wt_dir = repo / ".wt"
    wt_dir.mkdir(parents=True, exist_ok=True)
    state_path = wt_dir / "state.json"
    import json
    state_path.write_text(json.dumps({"worktrees": worktrees}), encoding="utf-8")


class TestMergeAutoCommit:
    def test_merge_auto_commits_uncommitted_changes(self, git_repo: Path, monkeypatch) -> None:
        """When branch has uncommitted changes, auto-commit before merge."""
        monkeypatch.chdir(git_repo)

        worktree_path = create_worktree_manually(git_repo, "my-feature")
        setup_state(git_repo, [{
            "feat_name": "my-feature",
            "branch": "feature/my-feature",
            "path": str(worktree_path),
            "base": "develop",
            "created_at": "2026-01-01T00:00:00",
        }])

        (worktree_path / "feature.txt").write_text("hello\n", encoding="utf-8")

        monkeypatch.chdir(worktree_path)
        result = runner.invoke(app, ["merge", "--no-push"])
        assert result.exit_code == 0, result.output

        assert not worktree_path.exists()

        branch_list = subprocess.run(
            ["git", "branch", "--list", "feature/my-feature"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        assert branch_list.stdout.strip() == ""

        subprocess.run(["git", "checkout", "develop"], cwd=git_repo, check=True)
        assert (git_repo / "feature.txt").exists()

    def test_merge_force_bypasses_auto_commit(self, git_repo: Path, monkeypatch) -> None:
        """When --force is used, uncommitted changes are merged without auto-commit."""
        monkeypatch.chdir(git_repo)

        worktree_path = create_worktree_manually(git_repo, "my-feature")
        setup_state(git_repo, [{
            "feat_name": "my-feature",
            "branch": "feature/my-feature",
            "path": str(worktree_path),
            "base": "develop",
            "created_at": "2026-01-01T00:00:00",
        }])

        (worktree_path / "feature.txt").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "feature.txt"], cwd=worktree_path, check=True)
        subprocess.run(["git", "commit", "-m", "First commit"], cwd=worktree_path, check=True)

        (worktree_path / "uncommitted.txt").write_text("uncommitted\n", encoding="utf-8")

        monkeypatch.chdir(worktree_path)
        result = runner.invoke(app, ["merge", "--no-push", "--force"])
        assert result.exit_code == 0, result.output

        assert not worktree_path.exists()


class TestPrAutoCommit:
    def test_pr_auto_commits_uncommitted_changes(self, git_repo: Path, monkeypatch) -> None:
        """When branch has uncommitted changes, auto-commit before PR."""
        monkeypatch.chdir(git_repo)

        worktree_path = create_worktree_manually(git_repo, "my-feature")
        setup_state(git_repo, [{
            "feat_name": "my-feature",
            "branch": "feature/my-feature",
            "path": str(worktree_path),
            "base": "develop",
            "created_at": "2026-01-01T00:00:00",
        }])

        (worktree_path / "feature.txt").write_text("hello\n", encoding="utf-8")

        monkeypatch.chdir(worktree_path)

        result = runner.invoke(app, ["pr", "--no-push"])
        assert "Auto-committing uncommitted changes" in result.output
        assert "Created commit" in result.output
        assert "no upstream set" in result.output
