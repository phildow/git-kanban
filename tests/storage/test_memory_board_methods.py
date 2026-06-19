"""Tests for board-related behavior in `InMemoryRepository`.

These tests document expected board CRUD semantics, including:
- uniqueness and lookup errors
- rename side effects on columns, tasks, and current context
- delete side effects on tasks and context
"""

from __future__ import annotations

import sys
import tempfile
import unittest

from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid4

from models import Board, Column, Task
from storage.kanban import BoardAlreadyExists, BoardNotFound
from storage.memory import InMemoryRepository


class TestInMemoryRepositoryBoardOps(unittest.TestCase):
    """Board operation contract tests for the in-memory repository."""

    def setUp(self) -> None:
        temp_dir = tempfile.gettempdir()
        self.repo = InMemoryRepository(root=Path(temp_dir))

    def test_create_get_list_exists_board(self):
        """Creates a board and verifies basic lookup/list/existence behavior."""
        self.assertFalse(self.repo.board_exists("alpha"))

        board = self.repo.create_board("alpha")

        self.assertEqual(board, Board(name="alpha", columns=[]))
        self.assertTrue(self.repo.board_exists("alpha"))
        self.assertEqual(self.repo.get_board("alpha"), board)
        self.assertEqual(self.repo.get_boards(), [board])

    def test_create_board_raises_when_duplicate(self):
        """Creating a board with an existing name raises `BoardAlreadyExists`."""
        self.repo.create_board("alpha")
        with self.assertRaises(BoardAlreadyExists):
            self.repo.create_board("alpha")

    def test_get_board_raises_when_missing(self):
        """Fetching a missing board raises `BoardNotFound`."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_board("missing")

    def test_rename_board_updates_board_columns_tasks(self):
        """Renaming a board updates dependent columns and tasks."""
        board = self.repo.create_board("alpha")
        board.columns.append(Column(name="todo", board="alpha", position=0))

        task = Task(
            id=uuid4(),
            title="task-1",
            board="alpha",
            column="todo",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.repo._tasks_by_id[task.id] = task
        self.repo._task_locations[task.id] = ("alpha", "todo")

        renamed = self.repo.rename_board("alpha", "beta")

        self.assertEqual(renamed.name, "beta")
        self.assertFalse(self.repo.board_exists("alpha"))
        self.assertTrue(self.repo.board_exists("beta"))
        self.assertEqual(self.repo.get_board("beta").columns[0].board, "beta")
        self.assertEqual(self.repo._task_locations[task.id], ("beta", "todo"))
        self.assertEqual(self.repo._tasks_by_id[task.id].board, "beta")

    def test_rename_board_raises_when_source_missing(self):
        """Renaming a non-existent board raises `BoardNotFound`."""
        with self.assertRaises(BoardNotFound):
            self.repo.rename_board("missing", "new")

    def test_rename_board_raises_when_target_exists(self):
        """Renaming to an already-used board name raises `BoardAlreadyExists`."""
        self.repo.create_board("alpha")
        self.repo.create_board("beta")
        with self.assertRaises(BoardAlreadyExists):
            self.repo.rename_board("alpha", "beta")

    def test_delete_board_removes_board_tasks(self):
        """Deleting a board removes its tasks."""
        self.repo.create_board("alpha")
        self.repo.create_board("beta")

        task_on_alpha = Task(id=uuid4(), title="a")
        task_on_beta = Task(id=uuid4(), title="b")
        self.repo._tasks_by_id[task_on_alpha.id] = task_on_alpha
        self.repo._tasks_by_id[task_on_beta.id] = task_on_beta
        self.repo._task_locations[task_on_alpha.id] = ("alpha", "todo")
        self.repo._task_locations[task_on_beta.id] = ("beta", "todo")

        self.repo.delete_board("alpha")

        self.assertFalse(self.repo.board_exists("alpha"))
        self.assertTrue(self.repo.board_exists("beta"))
        self.assertNotIn(task_on_alpha.id, self.repo._tasks_by_id)
        self.assertIn(task_on_beta.id, self.repo._tasks_by_id)
        self.assertNotIn(task_on_alpha.id, self.repo._task_locations)
        self.assertIn(task_on_beta.id, self.repo._task_locations)

    def test_delete_board_raises_when_missing(self):
        """Deleting a missing board raises `BoardNotFound`."""
        with self.assertRaises(BoardNotFound):
            self.repo.delete_board("missing")


if __name__ == "__main__":
    unittest.main()
