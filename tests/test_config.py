"""Tests for wt.config module."""

import json

from wt.config import CONFIG_SCHEMA_VERSION, WtConfig


class TestWtConfig:
    def test_defaults(self) -> None:
        config = WtConfig()
        assert config.branch_prefix == "feature/"
        assert config.version == CONFIG_SCHEMA_VERSION
        assert config.base_branch == "develop"
        assert config.remote == "origin"
        assert config.default_ai_tui == "opencode"

    def test_load_missing_file(self, tmp_path) -> None:
        config = WtConfig.load(tmp_path / "missing.json")
        assert config.branch_prefix == "feature/"

    def test_save_and_load(self, tmp_path) -> None:
        config_path = tmp_path / "wt.json"
        config = WtConfig(branch_prefix="feat/", base_branch="main")
        config.save(config_path)

        loaded = WtConfig.load(config_path)
        assert loaded.branch_prefix == "feat/"
        assert loaded.base_branch == "main"

    def test_load_ignores_old_worktrees_dir(self, tmp_path) -> None:
        config_path = tmp_path / "wt.json"
        config_path.write_text(
            json.dumps({"branch_prefix": "feat/", "worktrees_dir": ".wt/worktrees"}),
            encoding="utf-8",
        )

        loaded = WtConfig.load(config_path)

        assert loaded.branch_prefix == "feat/"
        assert not hasattr(loaded, "worktrees_dir")
