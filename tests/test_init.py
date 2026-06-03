"""Tests for wt.init module."""

from pathlib import Path
from unittest.mock import MagicMock

import subprocess

from wt.init import InitContext, build_init_env, resolve_init_script, run_init_script


class TestBuildInitEnv:
    def test_builds_env_with_context(self) -> None:
        ctx = InitContext(
            wt_root=Path("/repo/.wt"),
            repo_root=Path("/repo"),
            worktree_path=Path("/repo/.wt/worktrees/feat"),
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        env = build_init_env(ctx)

        assert env["WT_ROOT"] == "/repo/.wt"
        assert env["WT_REPO_ROOT"] == "/repo"
        assert env["WT_WORKTREE_PATH"] == "/repo/.wt/worktrees/feat"
        assert env["WT_FEAT_NAME"] == "feat"
        assert env["WT_BRANCH"] == "feature/feat"
        assert env["WT_BASE_BRANCH"] == "develop"

    def test_preserves_existing_env(self, monkeypatch) -> None:
        monkeypatch.setenv("MY_VAR", "my_value")
        ctx = InitContext(
            wt_root=Path("/repo/.wt"),
            repo_root=Path("/repo"),
            worktree_path=Path("/repo/.wt/worktrees/feat"),
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        env = build_init_env(ctx)

        assert env["MY_VAR"] == "my_value"
        assert env["WT_FEAT_NAME"] == "feat"


class TestResolveInitScript:
    def test_explicit_config_takes_priority(self, tmp_path) -> None:
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        # Even if fallback exists, explicit config wins
        hooks_dir = wt_root / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "init.sh").write_text("#!/bin/sh\necho fallback")

        result = resolve_init_script("uv sync", wt_root)
        assert result == "uv sync"

    def test_explicit_config_resolves_user_hook_reference(
        self, tmp_path, monkeypatch
    ) -> None:
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        user_hooks = home / ".wt" / "hooks"
        user_hooks.mkdir(parents=True)
        hook = user_hooks / "python-init.py"
        hook.write_text("print('hello')")
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script("python-init.py", wt_root)

        assert result == f"python {hook}"

    def test_explicit_interpreter_resolves_user_hook_reference(
        self, tmp_path, monkeypatch
    ) -> None:
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        user_hooks = home / ".wt" / "hooks"
        user_hooks.mkdir(parents=True)
        hook = user_hooks / "python-init.py"
        hook.write_text("print('hello')")
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script("python python-init.py", wt_root)

        assert result == f"python {hook}"

    def test_python_hook_reference_quotes_spaces(self, tmp_path, monkeypatch) -> None:
        home = tmp_path / "home with spaces"
        monkeypatch.setenv("HOME", str(home))
        user_hooks = home / ".wt" / "hooks"
        user_hooks.mkdir(parents=True)
        hook = user_hooks / "python-init.py"
        hook.write_text("print('hello')")
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script("python-init.py", wt_root)

        assert result == f"python '{hook}'"

    def test_python_hook_reference_uses_windows_safe_quoting(
        self, tmp_path, monkeypatch
    ) -> None:
        home = tmp_path / "home with spaces"
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.setattr("wt.init._is_windows", lambda: True)
        user_hooks = home / ".wt" / "hooks"
        user_hooks.mkdir(parents=True)
        hook = user_hooks / "python-init.py"
        hook.write_text("print('hello')")
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script("python-init.py", wt_root)

        assert result == subprocess.list2cmdline(["python", str(hook)])

    def test_fallback_to_hooks_init_sh(self, tmp_path) -> None:
        wt_root = tmp_path / ".wt"
        hooks_dir = wt_root / "hooks"
        hooks_dir.mkdir(parents=True)
        init_script = hooks_dir / "init.sh"
        init_script.write_text("#!/bin/sh\necho hello")

        result = resolve_init_script(None, wt_root)
        assert result == str(init_script)

    def test_fallback_to_repo_hooks_init_py(self, tmp_path) -> None:
        wt_root = tmp_path / ".wt"
        hooks_dir = wt_root / "hooks"
        hooks_dir.mkdir(parents=True)
        init_script = hooks_dir / "init.py"
        init_script.write_text("print('hello')")

        result = resolve_init_script(None, wt_root)

        assert result == f"python {init_script}"

    def test_fallback_to_user_hooks_init_sh(self, tmp_path, monkeypatch) -> None:
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        hooks_dir = home / ".wt" / "hooks"
        hooks_dir.mkdir(parents=True)
        init_script = hooks_dir / "init.sh"
        init_script.write_text("#!/bin/sh\necho hello")
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script(None, wt_root)

        assert result == str(init_script)

    def test_repo_hook_takes_priority_over_user_hook(
        self, tmp_path, monkeypatch
    ) -> None:
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        user_hooks = home / ".wt" / "hooks"
        user_hooks.mkdir(parents=True)
        (user_hooks / "init.sh").write_text("#!/bin/sh\necho user")
        wt_root = tmp_path / ".wt"
        repo_hooks = wt_root / "hooks"
        repo_hooks.mkdir(parents=True)
        repo_hook = repo_hooks / "init.sh"
        repo_hook.write_text("#!/bin/sh\necho repo")

        result = resolve_init_script(None, wt_root)

        assert result == str(repo_hook)

    def test_no_fallback_if_missing(self, tmp_path) -> None:
        wt_root = tmp_path / ".wt"
        wt_root.mkdir(parents=True)

        result = resolve_init_script(None, wt_root)
        assert result is None

    def test_no_fallback_if_hooks_dir_missing(self, tmp_path) -> None:
        wt_root = tmp_path / ".wt"
        wt_root.mkdir()

        result = resolve_init_script(None, wt_root)
        assert result is None


class TestRunInitScript:
    def test_successful_script(self, tmp_path) -> None:
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        ctx = InitContext(
            wt_root=tmp_path / ".wt",
            repo_root=tmp_path,
            worktree_path=worktree_path,
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        console = MagicMock()

        result = run_init_script("true", ctx, console, strict=False)
        assert result is True

    def test_failing_script_non_strict(self, tmp_path) -> None:
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        ctx = InitContext(
            wt_root=tmp_path / ".wt",
            repo_root=tmp_path,
            worktree_path=worktree_path,
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        console = MagicMock()

        # Non-strict mode should return True even on failure
        result = run_init_script("false", ctx, console, strict=False)
        assert result is True

    def test_failing_script_strict(self, tmp_path) -> None:
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        ctx = InitContext(
            wt_root=tmp_path / ".wt",
            repo_root=tmp_path,
            worktree_path=worktree_path,
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        console = MagicMock()

        # Strict mode should return False on failure
        result = run_init_script("false", ctx, console, strict=True)
        assert result is False

    def test_script_receives_env_vars(self, tmp_path) -> None:
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        output_file = worktree_path / "output.txt"

        ctx = InitContext(
            wt_root=tmp_path / ".wt",
            repo_root=tmp_path,
            worktree_path=worktree_path,
            feat_name="my-feature",
            branch="feature/my-feature",
            base_branch="main",
        )
        console = MagicMock()

        # Script that writes env vars to a file
        script = f'echo "$WT_FEAT_NAME:$WT_BASE_BRANCH" > {output_file}'
        result = run_init_script(script, ctx, console, strict=False)

        assert result is True
        assert output_file.read_text().strip() == "my-feature:main"

    def test_script_runs_in_worktree_dir(self, tmp_path) -> None:
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()
        output_file = tmp_path / "pwd_output.txt"

        ctx = InitContext(
            wt_root=tmp_path / ".wt",
            repo_root=tmp_path,
            worktree_path=worktree_path,
            feat_name="feat",
            branch="feature/feat",
            base_branch="develop",
        )
        console = MagicMock()

        script = f"pwd > {output_file}"
        result = run_init_script(script, ctx, console, strict=False)

        assert result is True
        assert output_file.read_text().strip() == str(worktree_path)
