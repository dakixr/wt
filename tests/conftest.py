"""Pytest fixtures for wt tests."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository with a fake remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)

    remote_repo = tmp_path / "remote.git"
    remote_repo.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_repo, check=True)

    subprocess.run(["git", "remote", "add", "origin", str(remote_repo)], cwd=repo, check=True)

    (repo / "README.md").write_text("# Test", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-b", "develop"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)

    return repo
