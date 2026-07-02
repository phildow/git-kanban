"""Tests for InMemoryIndexService write-through operations."""

from __future__ import annotations

import unittest

from kanban.index.memory import InMemoryIndexService
from kanban.storage.memory import InMemoryRepository
from tests.index.helpers import make_task


class TestUpsert(unittest.TestCase):
    """upsert_task adds a record; a second upsert for the same id replaces it."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService(repository=InMemoryRepository())

    def test_upserted_task_is_reachable_by_path(self) -> None:
        """get_path returns the task's path immediately after upsert."""
        task = make_task()
        self.index.upsert_task(task)
        self.assertEqual(self.index.get_path(task.id), task.path)

    def test_second_upsert_replaces_record(self) -> None:
        """A second upsert for the same id overwrites the previous record."""
        original = make_task(title="Original")
        self.index.upsert_task(original)
        updated = make_task(title="Updated", id=original.id)
        self.index.upsert_task(updated)
        self.assertEqual(self.index.get_path(original.id), updated.path)


class TestRemove(unittest.TestCase):
    """remove_task deletes a record; is a no-op when the id is absent."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService(repository=InMemoryRepository())

    def test_removed_task_is_unreachable(self) -> None:
        """get_path returns None after the task is removed."""
        task = make_task()
        self.index.upsert_task(task)
        self.index.remove_task(task)
        self.assertIsNone(self.index.get_path(task.id))

    def test_remove_absent_id_is_noop(self) -> None:
        """Removing an id that was never indexed does not raise."""
        self.index.remove_task(make_task())


class TestClear(unittest.TestCase):
    """clear() removes all records; clear(board=) removes only that board."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService(repository=InMemoryRepository())
        self.alpha = make_task(title="Alpha task", board="alpha")
        self.beta = make_task(title="Beta task", board="beta")
        self.index.upsert_task(self.alpha)
        self.index.upsert_task(self.beta)

    def test_clear_all_empties_index(self) -> None:
        """clear() with no argument drops every record."""
        self.index.clear()
        self.assertEqual(self.index.known_paths(), set())

    def test_clear_board_leaves_other_boards_intact(self) -> None:
        """clear(board=x) removes only records for that board."""
        self.index.clear(board="alpha")
        self.assertNotIn(self.alpha.path, self.index.known_paths())
        self.assertIn(self.beta.path, self.index.known_paths())
