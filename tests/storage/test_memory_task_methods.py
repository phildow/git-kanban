"""Tests for task-related behavior in `InMemoryRepository`.

These tests document task CRUD, filtering, lookup semantics, uniqueness
constraints, and move behavior.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from models import Task, TaskFilter
from storage.kanban import (
    BoardNotFound,
    ColumnNotFound,
    TaskAlreadyExists,
    TaskNotFound,
)
from storage.memory import InMemoryRepository


class TestInMemoryRepositoryTaskOps(unittest.TestCase):
    """Task operation contract tests for the in-memory repository."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.repo.create_board("alpha")
        self.repo.create_board("beta")
        self.repo.create_column("alpha", "todo")
        self.repo.create_column("alpha", "doing")
        self.repo.create_column("beta", "todo")

    def _task(self, title: str, board: str = "alpha", column: str = "todo", **kwargs) -> Task:
        return Task(id=uuid4(), title=title, board=board, column=column, **kwargs)

    def _filename(self, title: str) -> str:
        return title.lower().replace(" ", "-")

    def test_create_and_get_by_id(self):
        """Creates a task and verifies ID lookup and timestamp defaults."""
        task = self._task("t1")
        created = self.repo.create_task(task, "t1")

        self.assertIs(created, task)
        self.assertIsNotNone(created.created_at)
        self.assertIsNotNone(created.updated_at)
        self.assertEqual(self.repo.get_task_by_id(task.id), task)

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

        t1 = self.repo.create_task(self._task("A", assignee="p", priority="high", tags=["x"], due_date=due_soon), "a")
        t2 = self.repo.create_task(self._task("B", board="alpha", column="doing", assignee="q", priority="low", tags=["y"], due_date=due_later), "b")
        t3 = self.repo.create_task(self._task("C", board="beta", column="todo", assignee="p", priority="high", tags=["x", "z"], due_date=due_later), "c")

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
            board="beta",  # should be ignored by update
            column="todo",  # should be ignored by update
            assignee="new",
        )
        result = self.repo.update_task(updated)

        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "todo")
        self.assertEqual(result.assignee, "new")
        self.assertIsNotNone(result.updated_at)

        with self.assertRaises(TaskAlreadyExists):
            self.repo.update_task(Task(id=first.id, title="Second"))

        with self.assertRaises(TaskNotFound):
            self.repo.update_task(Task(id=uuid4(), title="Missing"))

    def test_move_task_and_delete_task(self):
        """Move validates destination and collisions; delete removes by UUID."""
        moved = self.repo.create_task(self._task("Move me", board="alpha", column="todo"), self._filename("Move me"))
        self.repo.create_task(self._task("Move me", board="beta", column="todo"), self._filename("Move me"))

        with self.assertRaises(TaskAlreadyExists):
            self.repo.move_task(moved.id, "beta", "todo")

        result = self.repo.move_task(moved.id, "alpha", "doing")
        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "doing")

        with self.assertRaises(BoardNotFound):
            self.repo.move_task(moved.id, "missing", "todo")
        with self.assertRaises(ColumnNotFound):
            self.repo.move_task(moved.id, "alpha", "missing")

        self.repo.delete_task(moved.id)
        with self.assertRaises(TaskNotFound):
            self.repo.get_task_by_id(moved.id)
        with self.assertRaises(TaskNotFound):
            self.repo.delete_task(moved.id)

    def test_bootstrap_creates_tasks_for_each_board_andcolumn(self):
        """Bootstrap helper seeds a fixed number of tasks in each board column."""
        # 2 boards x 4 columns each x 3 tasks per column = 24 seeded tasks
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        seeded = repo.bootstrap()
        self.assertEqual(len(seeded), 24)

        boards = repo.get_boards()
        self.assertEqual(len(boards), 2)

        main = repo.get_tasks(board="main")
        infra = repo.get_tasks(board="infra")
        self.assertEqual(len(main), 12)
        self.assertEqual(len(infra), 12)

        todo = repo.get_tasks(board="main", column="todo")
        doing = repo.get_tasks(board="infra", column="todo")
        self.assertEqual(len(todo), 3)
        self.assertEqual(len(doing), 3)
        self.assertTrue(all(task.slug for task in seeded))


if __name__ == "__main__":
    unittest.main()
