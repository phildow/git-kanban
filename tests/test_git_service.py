"""Tests for git service scaffolding contracts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KANBAN_SRC = PROJECT_ROOT / "kanban"
if str(KANBAN_SRC) not in sys.path:
    sys.path.insert(0, str(KANBAN_SRC))

from services.git_service import GitCommit, GitService


class TestGitService(unittest.TestCase):
    """Contract tests for git service scaffold behavior."""

    def setUp(self) -> None:
        self.service = GitService()

    def test_add_commit_raises_not_implemented(self):
        """`add_commit()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.add_commit(message="feat(task): add", scope="main/todo")

    def test_squash_commits_raises_not_implemented(self):
        """`squash_commits()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.squash_commits(message="squash: main", scope="main")

    def test_get_history_raises_not_implemented(self):
        """`get_history()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.get_history(limit=5, scope="main/todo")

    def test_private_pull_rebase_raises_not_implemented(self):
        """`_pull_rebase()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service._pull_rebase(scope="main")

    def test_private_push_raises_not_implemented(self):
        """`_push()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service._push(scope="main")

    def test_sync_calls_pull_rebase_then_push(self):
        """`sync()` orchestrates `_pull_rebase()` before `_push()`."""
        calls: list[str] = []

        with patch.object(self.service, "_pull_rebase", side_effect=lambda *, scope=None: calls.append(f"pull:{scope}")) as pull:
            with patch.object(self.service, "_push", side_effect=lambda *, scope=None: calls.append(f"push:{scope}")) as push:
                self.service.sync(scope="main")

        pull.assert_called_once_with(scope="main")
        push.assert_called_once_with(scope="main")
        self.assertEqual(calls, ["pull:main", "push:main"])

    def test_git_commit_dataclass_shape(self):
        """`GitCommit` carries sha/message fields used by service interfaces."""
        commit = GitCommit(sha="111aaa", message="feat(board): create")
        self.assertEqual(commit.sha, "111aaa")
        self.assertEqual(commit.message, "feat(board): create")


if __name__ == "__main__":
    unittest.main()
