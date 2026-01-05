"""Tests for wt init command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wt.cli import app

runner = CliRunner()


def read_config(repo: Path) -> dict:
    return json.loads((repo / ".wt" / "wt.json").read_text(encoding="utf-8"))


def test_init_creates_config_gitignore_and_worktrees_dir(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (git_repo / ".wt" / "wt.json").exists()
    assert (git_repo / ".wt" / ".gitignore").exists()
    assert (git_repo / ".wt" / "worktrees").exists()


def test_init_applies_overrides(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(
        app,
        [
            "init",
            "--branch-prefix",
            "feat/",
            "--base",
            "main",
            "--remote",
            "upstream",
            "--worktrees-dir",
            ".wt/worktrees",
            "--default-ai-tui",
            "cursor",
            "--init-script",
            "uv sync",
        ],
    )

    assert result.exit_code == 0
    cfg = read_config(git_repo)
    assert cfg["branch_prefix"] == "feat/"
    assert cfg["base_branch"] == "main"
    assert cfg["remote"] == "upstream"
    assert cfg["worktrees_dir"] == ".wt/worktrees"
    assert cfg["default_ai_tui"] == "cursor"
    assert cfg["init_script"] == "uv sync"


def test_init_is_noop_when_already_initialized(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["init", "--base", "main"])
    assert result.exit_code == 0
    before = (git_repo / ".wt" / "wt.json").read_text(encoding="utf-8")

    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    after = (git_repo / ".wt" / "wt.json").read_text(encoding="utf-8")

    assert before == after


def test_init_force_overwrites_to_defaults(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["init", "--base", "main"])
    assert result.exit_code == 0
    assert read_config(git_repo)["base_branch"] == "main"

    result = runner.invoke(app, ["init", "--force"])
    assert result.exit_code == 0
    # With --force, it resets to current branch (main) instead of hard-coded "develop"
    assert read_config(git_repo)["base_branch"] == "main"


def test_init_hook_creates_template(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    result = runner.invoke(app, ["init", "--hook"])

    assert result.exit_code == 0
    hook_path = git_repo / ".wt" / "hooks" / "init.sh"
    assert hook_path.exists()
    contents = hook_path.read_text(encoding="utf-8")
    assert "WT_FEAT_NAME" in contents
    assert "WT_WORKTREE_PATH" in contents

