"""Tests for the in-memory change tracker used as a test double."""

from __future__ import annotations

import unittest
from pathlib import Path

from kanban.tracking import (
    InMemoryChangeTracker,
    NothingToCommit,
    ChangeTracker,
)


class TestInMemoryInitialization(unittest.TestCase):
    """Initialization records the worktree settings and opens the history."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()

    def test_derives_from_change_tracker_service(self):
        """The double implements the same interface as GitChangeTracker."""
        self.assertIsInstance(self.service, ChangeTracker)

    def test_starts_uninitialized_and_empty(self):
        """Nothing is initialized and no commit exists until asked for."""
        self.assertFalse(self.service.is_initialized)
        self.assertEqual(self.service.commits, [])

    def test_initialize_records_settings(self):
        """`initialize()` keeps the worktree and branch it was given."""
        self.service.initialize(Path("/tmp/project"), worktree=".store", branch="tasks")

        self.assertTrue(self.service.is_initialized)
        self.assertEqual(self.service.worktree, ".store")
        self.assertEqual(self.service.branch, "tasks")

    def test_initialize_writes_first_commit(self):
        """`initialize()` opens the history the way the orphan branch does."""
        self.service.initialize(Path("/tmp/project"))

        self.assertEqual(self.service.messages, ["kanban: initialize"])


class TestInMemoryCommits(unittest.TestCase):
    """Commits are recorded in order and addressable by path."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()

    def test_add_commit_returns_the_recorded_commit(self):
        """The returned commit carries the message and an author."""
        commit = self.service.add_commit("feat(task): add", Path("main/todo"))

        self.assertEqual(commit.message, "feat(task): add")
        self.assertEqual(commit.author, "kanban")
        self.assertEqual(self.service.commits, [commit])

    def test_commits_are_recorded_oldest_first(self):
        """`commits` replays the order the commits were made in."""
        self.service.add_commit("first")
        self.service.add_commit("second")

        self.assertEqual(self.service.messages, ["first", "second"])

    def test_shas_are_distinct(self):
        """Two commits of the same message at different positions differ."""
        first = self.service.add_commit("same")
        second = self.service.add_commit("same")

        self.assertNotEqual(first.sha, second.sha)

    def test_shas_are_stable_across_instances(self):
        """The same sequence of commits yields the same shas, so tests can assert on them."""
        other = InMemoryChangeTracker()

        self.assertEqual(
            self.service.add_commit("feat(board): create").sha,
            other.add_commit("feat(board): create").sha,
        )


class TestInMemoryHistory(unittest.TestCase):
    """History reads back most recent first and honours path scope."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()
        self.service.add_commit("todo one", Path("main/todo"))
        self.service.add_commit("done one", Path("main/done"))
        self.service.add_commit("todo two", Path("main/todo/a-task.md"))

    def test_history_is_most_recent_first(self):
        """The newest commit leads the list."""
        history = self.service.get_history()

        self.assertEqual([c.message for c in history], ["todo two", "done one", "todo one"])

    def test_history_honours_limit(self):
        """Only `limit` commits are returned."""
        history = self.service.get_history(limit=2)

        self.assertEqual([c.message for c in history], ["todo two", "done one"])

    def test_history_scoped_to_a_path(self):
        """A path returns the commits made against it and below it."""
        history = self.service.get_history(Path("main/todo"))

        self.assertEqual([c.message for c in history], ["todo two", "todo one"])

    def test_history_scoped_to_a_file(self):
        """A task file returns only the commits that touched it."""
        history = self.service.get_history(Path("main/todo/a-task.md"))

        self.assertEqual([c.message for c in history], ["todo two"])

    def test_storewide_commit_answers_every_scope(self):
        """A commit made with no path touched the whole store."""
        self.service.add_commit("squash")

        self.assertIn("squash", [c.message for c in self.service.get_history(Path("main/done"))])


class TestInMemoryUncommittedChanges(unittest.TestCase):
    """Pending changes are what a test arranges, and a commit clears them."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()

    def test_clean_by_default(self):
        """Nothing is pending until a test says so."""
        self.assertFalse(self.service.has_uncommitted_changes())

    def test_recorded_change_is_pending(self):
        """`record_change()` is reported store-wide and within its own path."""
        self.service.record_change(Path("main/todo/a-task.md"))

        self.assertTrue(self.service.has_uncommitted_changes())
        self.assertTrue(self.service.has_uncommitted_changes(Path("main/todo")))

    def test_change_outside_the_scope_is_not_pending(self):
        """A change elsewhere leaves the queried path clean."""
        self.service.record_change(Path("main/todo/a-task.md"))

        self.assertFalse(self.service.has_uncommitted_changes(Path("main/done")))

    def test_commit_clears_what_it_covers(self):
        """A commit clears the pending changes within its path and no others."""
        self.service.record_change(Path("main/todo/a-task.md"))
        self.service.record_change(Path("main/done/other.md"))

        self.service.add_commit("feat(task): update", Path("main/todo"))

        self.assertFalse(self.service.has_uncommitted_changes(Path("main/todo")))
        self.assertTrue(self.service.has_uncommitted_changes(Path("main/done")))


class TestInMemorySquash(unittest.TestCase):
    """Squashing collapses the commits in scope into one."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()

    def test_squash_collapses_the_whole_history(self):
        """With no path every commit becomes one."""
        self.service.add_commit("first")
        self.service.add_commit("second")

        commit = self.service.squash_commits("squash: all")

        self.assertEqual(self.service.messages, ["squash: all"])
        self.assertEqual(commit.message, "squash: all")

    def test_squash_leaves_commits_outside_the_scope(self):
        """Commits on another path survive, and the squash takes the last one's place."""
        self.service.add_commit("todo one", Path("main/todo"))
        self.service.add_commit("done one", Path("main/done"))
        self.service.add_commit("todo two", Path("main/todo"))

        self.service.squash_commits("squash: todo", Path("main/todo"))

        self.assertEqual(self.service.messages, ["done one", "squash: todo"])

    def test_squash_with_nothing_in_scope_raises(self):
        """A path no commit touched has nothing to collapse."""
        self.service.add_commit("todo one", Path("main/todo"))

        with self.assertRaises(NothingToCommit):
            self.service.squash_commits("squash: done", Path("main/done"))


class TestInMemorySync(unittest.TestCase):
    """Sync counts the halves it ran, in order."""

    def setUp(self) -> None:
        self.service = InMemoryChangeTracker()

    def test_sync_pulls_then_pushes(self):
        """Both halves run once per sync."""
        self.service.sync()

        self.assertEqual(self.service.pulls, 1)
        self.assertEqual(self.service.pushes, 1)


if __name__ == "__main__":
    unittest.main()
