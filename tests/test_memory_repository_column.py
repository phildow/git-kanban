"""Tests for column-related behavior in `InMemoryRepository`.

The suite documents validation, ordering, rename/move side effects, and
column-scoped task cleanup.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from uuid import uuid4

from models import Column, Task
from storage.kanban_repository import BoardNotFound, ColumnAlreadyExists, ColumnNotFound
from storage.memory_repository import InMemoryRepository


class TestInMemoryRepositoryColumnOps(unittest.TestCase):
    """Column operation contract tests for the in-memory repository."""

    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.repo.create_board("alpha")

    def test_list_columns_and_create_column(self):
        """Creates a column and verifies list output and default position."""
        self.assertEqual(self.repo.list_columns("alpha"), [])

        created = self.repo.create_column("alpha", "todo")

        self.assertEqual(created, Column(name="todo", board="alpha", position=0))
        self.assertEqual(self.repo.list_columns("alpha"), [created])

    def test_column_methods_raise_when_board_missing(self):
        """Column APIs raise `BoardNotFound` when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.list_columns("missing")
        with self.assertRaises(BoardNotFound):
            self.repo.get_column("missing", "todo")
        with self.assertRaises(BoardNotFound):
            self.repo.column_exists("missing", "todo")
        with self.assertRaises(BoardNotFound):
            self.repo.create_column("missing", "todo")

    def test_get_and_exists(self):
        """Verifies column existence checks and direct lookup behavior."""
        self.repo.create_column("alpha", "todo")

        self.assertTrue(self.repo.column_exists("alpha", "todo"))
        self.assertFalse(self.repo.column_exists("alpha", "done"))
        self.assertEqual(self.repo.get_column("alpha", "todo").name, "todo")

        with self.assertRaises(ColumnNotFound):
            self.repo.get_column("alpha", "missing")

    def test_create_column_duplicate_raises(self):
        """Creating a duplicate column name raises `ColumnAlreadyExists`."""
        self.repo.create_column("alpha", "todo")
        with self.assertRaises(ColumnAlreadyExists):
            self.repo.create_column("alpha", "todo")

    def test_rename_column_updates_tasks_locations_and_context(self):
        """Renaming a column updates tasks, location index, and active context."""
        self.repo.create_column("alpha", "todo")
        task = Task(id=uuid4(), title="task-1", board="alpha", column="todo")
        self.repo._tasks_by_id[task.id] = task
        self.repo._task_locations[task.id] = ("alpha", "todo")
        self.repo.set_user_context(board="alpha", column="todo")

        renamed = self.repo.rename_column("alpha", "todo", "doing")

        self.assertEqual(renamed.name, "doing")
        self.assertEqual(self.repo.get_column("alpha", "doing").position, 0)
        self.assertEqual(self.repo._task_locations[task.id], ("alpha", "doing"))
        self.assertEqual(self.repo._tasks_by_id[task.id].column, "doing")
        self.assertEqual(self.repo.get_user_context().column, "doing")

    def test_rename_column_raises_for_missing_or_duplicate(self):
        """Rename rejects missing sources and duplicate destination names."""
        self.repo.create_column("alpha", "todo")
        self.repo.create_column("alpha", "done")

        with self.assertRaises(ColumnNotFound):
            self.repo.rename_column("alpha", "missing", "x")

        with self.assertRaises(ColumnAlreadyExists):
            self.repo.rename_column("alpha", "todo", "done")

    def test_reorder_column_and_positions(self):
        """Reordering columns updates order and normalized position values."""
        self.repo.create_column("alpha", "todo")
        self.repo.create_column("alpha", "doing")
        self.repo.create_column("alpha", "done")

        ordered = self.repo.reorder_column("alpha", "done", 0)
        self.assertEqual([c.name for c in ordered], ["done", "todo", "doing"])
        self.assertEqual([c.position for c in ordered], [0, 1, 2])

        ordered = self.repo.reorder_column("alpha", "done", 99)
        self.assertEqual([c.name for c in ordered], ["todo", "doing", "done"])
        self.assertEqual([c.position for c in ordered], [0, 1, 2])

        with self.assertRaises(ColumnNotFound):
            self.repo.reorder_column("alpha", "missing", 0)

    def test_delete_column_removes_tasks_and_updates_context_and_positions(self):
        """Deleting a column removes scoped tasks and clears active column context."""
        self.repo.create_column("alpha", "todo")
        self.repo.create_column("alpha", "doing")

        todo_task = Task(id=uuid4(), title="t1", board="alpha", column="todo")
        doing_task = Task(id=uuid4(), title="t2", board="alpha", column="doing")
        self.repo._tasks_by_id[todo_task.id] = todo_task
        self.repo._tasks_by_id[doing_task.id] = doing_task
        self.repo._task_locations[todo_task.id] = ("alpha", "todo")
        self.repo._task_locations[doing_task.id] = ("alpha", "doing")
        self.repo.set_user_context(board="alpha", column="todo")

        self.repo.delete_column("alpha", "todo")

        self.assertEqual([c.name for c in self.repo.list_columns("alpha")], ["doing"])
        self.assertEqual(self.repo.get_column("alpha", "doing").position, 0)
        self.assertNotIn(todo_task.id, self.repo._tasks_by_id)
        self.assertIn(doing_task.id, self.repo._tasks_by_id)
        self.assertNotIn(todo_task.id, self.repo._task_locations)
        self.assertIn(doing_task.id, self.repo._task_locations)
        self.assertEqual(self.repo.get_user_context().board, "alpha")
        self.assertIsNone(self.repo.get_user_context().column)

        with self.assertRaises(ColumnNotFound):
            self.repo.delete_column("alpha", "todo")


if __name__ == "__main__":
    unittest.main()
