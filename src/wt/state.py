"""State management for wt-managed worktrees."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class WorktreeEntry:
    """Metadata for a wt-managed worktree."""

    feat_name: str
    branch: str
    path: str
    base: str
    created_at: str


@dataclass
class WtState:
    """State schema for .wt/state.json."""

    worktrees: list[WorktreeEntry] = field(default_factory=list)

    @classmethod
    def load(cls, state_path: Path) -> "WtState":
        """Load state from file, or return empty state if missing."""
        if state_path.exists():
            with state_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            worktrees = [WorktreeEntry(**item) for item in data.get("worktrees", [])]
            return cls(worktrees=worktrees)
        return cls()

    def save(self, state_path: Path) -> None:
        """Save state to file."""
        state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"worktrees": [asdict(item) for item in self.worktrees]}
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def add_worktree(self, feat_name: str, branch: str, path: str, base: str) -> None:
        """Add a worktree entry."""
        entry = WorktreeEntry(
            feat_name=feat_name,
            branch=branch,
            path=path,
            base=base,
            created_at=datetime.now().isoformat(),
        )
        self.worktrees.append(entry)

    def remove_worktree(self, path: str) -> None:
        """Remove a worktree entry by path."""
        self.worktrees = [item for item in self.worktrees if item.path != path]

    def find_by_branch(self, branch: str) -> WorktreeEntry | None:
        """Find a worktree entry by branch name."""
        for item in self.worktrees:
            if item.branch == branch:
                return item
        return None

    def find_by_path(self, path: str) -> WorktreeEntry | None:
        """Find a worktree entry by path."""
        for item in self.worktrees:
            if item.path == path:
                return item
        return None

    def find_by_feat_name(self, feat_name: str) -> WorktreeEntry | None:
        """Find a worktree entry by feature name."""
        for item in self.worktrees:
            if item.feat_name == feat_name:
                return item
        return None


def prune_stale_entries(state: WtState, valid_paths: set[str]) -> bool:
    """Remove worktree entries whose paths are not in valid_paths.

    Path comparisons are normalized to avoid issues with symlinked paths
    (e.g. macOS `/var` vs `/private/var`).
    """

    def normalize(path: str) -> str:
        return str(Path(path).resolve(strict=False))

    normalized_valid = {normalize(path) for path in valid_paths}
    original_count = len(state.worktrees)
    state.worktrees = [
        item for item in state.worktrees if normalize(item.path) in normalized_valid
    ]
    return len(state.worktrees) != original_count



def get_state_path(repo_root: Path) -> Path:
    """Get the state file path."""
    return repo_root / ".wt" / "state.json"

