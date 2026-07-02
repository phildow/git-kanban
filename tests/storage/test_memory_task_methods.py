"""Tests for task-related behavior in `InMemoryRepository`.

These tests document task CRUD, filtering, lookup semantics, uniqueness
constraints, and move behavior.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from kanban.models import Task
from kanban.storage.kanban import (
    BoardNotFound,
    ColumnNotFound,
    TaskAlreadyExists,
    TaskNotFound,
)
from kanban.storage.memory import InMemoryRepository


class TestInMemoryRepositoryTaskOps(unittest.TestCase):
    """Task operation contract tests for the in-memory repository."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_board("beta", slug="beta")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "doing", slug="doing")
        self.repo.create_column("beta", "todo", slug="todo")

    def _task(self, title: str, board: str = "alpha", column: str = "todo", **kwargs) -> Task:
        now = datetime.now(UTC)
        return Task(id=uuid4(), title=title, slug=self._filename(title), board=board, column=column, created_at=now, updated_at=now, **kwargs)

    def _filename(self, title: str) -> str:
        return title.lower().replace(" ", "-")

    def test_create_validates_location_and_uniqueness(self):
        """Create validates board/column existence and title uniqueness per column."""
        with self.assertRaises(BoardNotFound):
            self.repo.create_task(self._task("t", board="missing"), "t")

        with self.assertRaises(ColumnNotFound):
            self.repo.create_task(self._task("t", board="alpha", column="missing"), "t")

        self.repo.create_task(self._task("dupe", board="alpha", column="todo"), "dupe")
        with self.assertRaises(TaskAlreadyExists):
            self.repo.create_task(self._task("dupe", board="alpha", column="todo"), "dupe")

    def test_get_tasks_scope_and_filter(self):
        """List returns tasks by scope and applies `TaskFilter` constraints."""
        due_soon = datetime.now(UTC) + timedelta(days=1)
        due_later = datetime.now(UTC) + timedelta(days=10)

        t1 = self.repo.create_task(self._task("A", assigned_to="p", priority="high", tags=["x"], due_date=due_soon), "a")
        t2 = self.repo.create_task(self._task("B", board="alpha", column="doing", assigned_to="q", priority="low", tags=["y"], due_date=due_later), "b")
        t3 = self.repo.create_task(self._task("C", board="beta", column="todo", assigned_to="p", priority="high", tags=["x", "z"], due_date=due_later), "c")

        self.assertEqual({t.id for t in self.repo.get_tasks()}, {t1.id, t2.id, t3.id})
        self.assertEqual({t.id for t in self.repo.get_tasks(board="alpha")}, {t1.id, t2.id})
        self.assertEqual(self.repo.get_tasks(board="alpha", column="doing"), [t2])

    def test_get_tasks_validates_scope(self):
        """List validates explicit board/column scope before filtering."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_tasks(board="missing")
        with self.assertRaises(ColumnNotFound):
            self.repo.get_tasks(board="alpha", column="missing")

    def test_update_task_preserves_location_and_checks_collision(self):
        """Update keeps location immutable and blocks title collisions in-place."""
        first = self.repo.create_task(self._task("First", board="alpha", column="todo"), "first")
        self.repo.create_task(self._task("Second", board="alpha", column="todo"), "second")

        updated = Task(
            id=first.id,
            title="First Updated",
            slug="first-updated",
            board="beta",  # should be ignored by update
            column="todo",  # should be ignored by update
            assigned_to="new",
        )
        result = self.repo.update_task(updated, slug="first")

        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "todo")
        self.assertEqual(result.assigned_to, "new")
        self.assertIsNotNone(result.updated_at)

        with self.assertRaises(TaskAlreadyExists):
            task = Task(id=first.id, title="Second", slug="second", board="alpha", column="todo")
            self.repo.update_task(task, slug="first")

        with self.assertRaises(TaskNotFound):
            task = Task(id=uuid4(), title="Missing", slug="missing", board="alpha", column="todo")
            self.repo.update_task(task, slug="missing")

    def test_move_task_and_delete_task(self):
        """Move validates destination and collisions; delete removes by UUID."""
        moved = self.repo.create_task(self._task("Move me", board="alpha", column="todo"), self._filename("Move me"))
        self.repo.create_task(self._task("Move me", board="alpha", column="doing"), self._filename("Move me"))

        with self.assertRaises(TaskAlreadyExists):
            self.repo.move_task(moved, "doing")

        result = self.repo.move_task(moved, "todo")
        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "todo")

        with self.assertRaises(ColumnNotFound):
            self.repo.move_task(moved, "missing")

        self.repo.delete_task(moved)

        with self.assertRaises(TaskNotFound):
            self.repo.delete_task(moved)


if __name__ == "__main__":
    unittest.main()
