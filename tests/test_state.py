"""Tests for wt.state module."""
from wt.state import WorktreeEntry, WtState


class TestWtStateFindByFeatName:
    def test_find_existing(self) -> None:
        state = WtState(
            worktrees=[
                WorktreeEntry(
                    feat_name="my-feature",
                    branch="feature/my-feature",
                    path="/repo/.wt/worktrees/my-feature",
                    base="develop",
                    created_at="2026-01-01T00:00:00",
                )
            ]
        )
        entry = state.find_by_feat_name("my-feature")
        assert entry is not None
        assert entry.path == "/repo/.wt/worktrees/my-feature"

    def test_find_missing(self) -> None:
        state = WtState(worktrees=[])
        entry = state.find_by_feat_name("nonexistent")
        assert entry is None
