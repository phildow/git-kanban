"""Tests that ChangeTrackingService forwards to its change tracker."""

from __future__ import annotations

import unittest
from pathlib import Path

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker


class TestChangeTrackingForwarding(unittest.TestCase):
    """Every call reaches the injected implementation unchanged."""

    def setUp(self) -> None:
        self.change_tracker = InMemoryChangeTracker()
        self.service = ChangeTrackingService(change_tracker=self.change_tracker)

    def test_initialize_forwards_worktree_settings(self):
        """`initialize()` hands the root, worktree, and branch straight down."""
        self.service.initialize(Path("/tmp/project"), worktree=".store", branch="tasks")

        self.assertTrue(self.change_tracker.is_initialized)
        self.assertEqual(self.change_tracker.worktree, ".store")
        self.assertEqual(self.change_tracker.branch, "tasks")

    def test_is_initialized_reports_the_implementation(self):
        """The property reads through rather than tracking state of its own."""
        self.assertFalse(self.service.is_initialized)

        self.change_tracker.initialize(Path("/tmp/project"))

        self.assertTrue(self.service.is_initialized)

    def test_add_commit_forwards_message_and_path(self):
        """A commit made through the facade is recorded by the implementation."""
        commit = self.service.add_commit("feat(task): add", Path("main/todo"))

        self.assertEqual(self.change_tracker.commits, [commit])
        self.assertEqual(self.change_tracker.messages, ["feat(task): add"])

    def test_squash_commits_forwards(self):
        """The squash collapses the implementation's history."""
        self.service.add_commit("first")
        self.service.add_commit("second")

        self.service.squash_commits("squash: all")

        self.assertEqual(self.change_tracker.messages, ["squash: all"])

    def test_get_history_forwards_path_and_limit(self):
        """History comes back scoped and limited as the implementation returns it."""
        self.service.add_commit("todo one", Path("main/todo"))
        self.service.add_commit("done one", Path("main/done"))

        history = self.service.get_history(Path("main/todo"), limit=5)

        self.assertEqual([c.message for c in history], ["todo one"])

    def test_has_uncommitted_changes_forwards(self):
        """What the implementation holds pending is what the facade reports."""
        self.assertFalse(self.service.has_uncommitted_changes())

        self.change_tracker.record_change(Path("main/todo/a-task.md"))

        self.assertTrue(self.service.has_uncommitted_changes(Path("main/todo")))

    def test_sync_forwards(self):
        """A sync runs both halves on the implementation."""
        self.service.sync()

        self.assertEqual(self.change_tracker.pulls, 1)
        self.assertEqual(self.change_tracker.pushes, 1)


if __name__ == "__main__":
    unittest.main()
