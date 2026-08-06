"""Tests for git change tracker scaffolding contracts."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from kanban.tracking import Commit, GitChangeTracker, ChangeTracker


class TestGitChangeTracker(unittest.TestCase):
    """Contract tests for git change tracker scaffold behavior."""

    def setUp(self) -> None:
        self.service = GitChangeTracker()

    def test_derives_from_change_tracker_service(self):
        """`GitChangeTracker` is one implementation of the change tracking interface."""
        self.assertIsInstance(self.service, ChangeTracker)

    def test_initialize_raises_not_implemented(self):
        """`initialize()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.initialize(Path("/tmp/project"))

    def test_is_initialized_raises_not_implemented(self):
        """`is_initialized` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            _ = self.service.is_initialized

    def test_add_commit_raises_not_implemented(self):
        """`add_commit()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.add_commit("feat(task): add", Path("main/todo"))

    def test_squash_commits_raises_not_implemented(self):
        """`squash_commits()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.squash_commits("squash: main", Path("main"))

    def test_get_history_raises_not_implemented(self):
        """`get_history()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.get_history(Path("main/todo"), limit=5)

    def test_has_uncommitted_changes_raises_not_implemented(self):
        """`has_uncommitted_changes()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service.has_uncommitted_changes()

    def test_private_pull_rebase_raises_not_implemented(self):
        """`_pull_rebase()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service._pull_rebase(Path("main"))

    def test_private_push_raises_not_implemented(self):
        """`_push()` raises until git backend wiring is implemented."""
        with self.assertRaises(NotImplementedError):
            self.service._push(Path("main"))

    def test_sync_calls_pull_rebase_then_push(self):
        """`sync()` orchestrates `_pull_rebase()` before `_push()`."""
        calls: list[str] = []
        path = Path("main")

        with patch.object(self.service, "_pull_rebase", side_effect=lambda *, path=None: calls.append(f"pull:{path}")) as pull:
            with patch.object(self.service, "_push", side_effect=lambda *, path=None: calls.append(f"push:{path}")) as push:
                self.service.sync(path)

        pull.assert_called_once_with(path=path)
        push.assert_called_once_with(path=path)
        self.assertEqual(calls, ["pull:main", "push:main"])

    def test_git_commit_dataclass_shape(self):
        """`Commit` carries sha/message fields used by service interfaces."""
        commit = Commit(sha="111aaa", message="feat(board): create")
        self.assertEqual(commit.sha, "111aaa")
        self.assertEqual(commit.message, "feat(board): create")


if __name__ == "__main__":
    unittest.main()
