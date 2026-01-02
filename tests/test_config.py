"""Tests for wt.config module."""
from wt.config import WtConfig


class TestWtConfig:
    def test_defaults(self) -> None:
        config = WtConfig()
        assert config.branch_prefix == "feature/"
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
