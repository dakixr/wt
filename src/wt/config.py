"""Configuration management for wt."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class WtConfig:
    """Configuration schema for .wt/wt.json."""

    branch_prefix: str = "feature/"
    base_branch: str = "develop"
    remote: str = "origin"
    worktrees_dir: str = ".wt/worktrees"
    default_ai_tui: str = "opencode"

    @classmethod
    def load(cls, config_path: Path) -> "WtConfig":
        """Load config from file, or return defaults if missing."""
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            filtered = {
                key: value
                for key, value in data.items()
                if key in cls.__dataclass_fields__
            }
            return cls(**filtered)
        return cls()

    def save(self, config_path: Path) -> None:
        """Save config to file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, indent=2)


def get_wt_dir(repo_root: Path) -> Path:
    """Get the .wt directory path."""
    return repo_root / ".wt"


def get_config_path(repo_root: Path) -> Path:
    """Get the config file path."""
    return get_wt_dir(repo_root) / "wt.json"


def ensure_config(repo_root: Path) -> WtConfig:
    """Ensure config exists, creating with defaults if needed."""
    config_path = get_config_path(repo_root)
    config = WtConfig.load(config_path)
    if not config_path.exists():
        config.save(config_path)
    return config
