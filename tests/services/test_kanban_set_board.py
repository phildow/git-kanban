"""Behavior tests for `KanbanService` path and working-context helpers."""

from __future__ import annotations

import unittest
import tempfile

from pathlib import Path
from uuid import uuid4

from kanban.services.kanban import KanbanService
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.index import IndexService
from kanban.index.memory import InMemoryIndex
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceResolvePath(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
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
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
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
