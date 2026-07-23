"""Behavior tests for `KanbanService.change_dir()` context validation."""

from __future__ import annotations

import unittest
import tempfile

from pathlib import Path
from uuid import uuid4

from kanban.storage.base import BoardNotFound, ColumnNotFound
from kanban.services.kanban import KanbanService
from kanban.services.git import GitService
from kanban.services.index import IndexService
from kanban.index.memory import InMemoryIndex
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceChangeDir(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")

    def test_change_dir_sets_existing_board_and_column(self):
        ctx = self.svc.change_dir(path="alpha/todo")
        self.assertEqual(ctx.board, "alpha")

    def test_change_dir_raises_for_missing_board(self):
        with self.assertRaises(BoardNotFound):
            self.svc.change_dir(path="missing")

    def test_change_dir_raises_for_missing_column(self):
        with self.assertRaises(ColumnNotFound):
            self.svc.change_dir(path="alpha/missing")

    def test_change_dir_relative_column_uses_active_board(self):
        self.svc.change_dir(path="alpha")
        ctx = self.svc.change_dir(path="todo")
        self.assertEqual(ctx.board, "alpha")


class TestKanbanServiceResolvePath(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )

    def test_resolve_path_relative_with_board_and_column_context(self):
        self.svc.update_user_context(board="alpha")
        result = self.svc.resolve_path("task-one")
        self.assertEqual(result, Path("/alpha/task-one"))

    def test_resolve_path_absolute_with_board_and_column_context(self):
        self.svc.update_user_context(board="alpha")
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))

    def test_resolve_path_relative_with_board_only_context(self):
        self.svc.update_user_context(board="alpha")
        result = self.svc.resolve_path("todo/task-one")
        self.assertEqual(result, Path("/alpha/todo/task-one"))

    def test_resolve_path_absolute_with_board_only_context(self):
        self.svc.update_user_context(board="alpha")
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))

    def test_resolve_path_relative_with_empty_context(self):
        self.svc.update_user_context(board=None)
        result = self.svc.resolve_path("alpha/todo/task-one")
        self.assertEqual(result, Path("/alpha/todo/task-one"))

    def test_resolve_path_absolute_with_empty_context(self):
        self.svc.update_user_context(board=None)
        result = self.svc.resolve_path("/infra/backlog/task-two")
        self.assertEqual(result, Path("/infra/backlog/task-two"))


class TestKanbanServiceWorkingContextSetters(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )

    def test_working_board_setter_updates_board(self) -> None:
        self.svc.update_user_context(board="alpha")

        self.svc.working_board = "beta"

        self.assertEqual(self.svc.working_board, "beta")

    def test_working_board_setter_persists_userdata(self) -> None:
        self.svc.update_user_context(board="alpha")

        self.svc.working_board = "beta"

        self.assertEqual(self.svc.get_userdata("user-context.board"), "beta")


if __name__ == "__main__":
    unittest.main()
