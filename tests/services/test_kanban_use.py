"""Behavior tests for `KanbanService.set_path()` context validation."""

from __future__ import annotations

import sys
import unittest
import tempfile

from pathlib import Path
from uuid import uuid4

from models import UserContext
from storage.kanban import BoardNotFound, ColumnNotFound
from services.kanban import KanbanService
from services.git import GitService
from services.index import IndexService
from storage.memory import InMemoryRepository


class TestKanbanServiceSetPath(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
        )
        self.repo.create_board("alpha")
        self.repo.create_column("alpha", "todo")

    def test_set_path_sets_existing_board_and_column(self):
        ctx = self.svc.set_path(path="alpha/todo")
        self.assertEqual(ctx.board, "alpha")
        self.assertEqual(ctx.column, "todo")

    def test_set_path_raises_for_missing_board(self):
        with self.assertRaises(BoardNotFound):
            self.svc.set_path(path="missing")

    def test_set_path_raises_for_missing_column(self):
        with self.assertRaises(ColumnNotFound):
            self.svc.set_path(path="alpha/missing")

    def test_set_path_relative_column_uses_active_board(self):
        self.svc.set_path(path="alpha")
        ctx = self.svc.set_path(path="todo")
        self.assertEqual(ctx.board, "alpha")
        self.assertEqual(ctx.column, "todo")


class TestKanbanServiceResolvePath(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
        )

    def test_resolve_path_relative_with_board_and_column_context(self):
        self.svc.update_user_context(board="alpha", column="todo")
        result = self.svc.resolve_path("task-one")
        self.assertEqual(result, Path("/alpha/todo/task-one"))

    def test_resolve_path_absolute_with_board_and_column_context(self):
        self.svc.update_user_context(board="alpha", column="todo")
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))

    def test_resolve_path_relative_with_board_only_context(self):
        self.svc.update_user_context(board="alpha", column=None)
        result = self.svc.resolve_path("todo/task-one")
        self.assertEqual(result, Path("/alpha/todo/task-one"))

    def test_resolve_path_absolute_with_board_only_context(self):
        self.svc.update_user_context(board="alpha", column=None)
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))

    def test_resolve_path_relative_with_empty_context(self):
        self.svc.update_user_context(board=None, column=None)
        result = self.svc.resolve_path("alpha/todo/task-one")
        self.assertEqual(result, Path("/alpha/todo/task-one"))

    def test_resolve_path_absolute_with_empty_context(self):
        self.svc.update_user_context(board=None, column=None)
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))


if __name__ == "__main__":
    unittest.main()
