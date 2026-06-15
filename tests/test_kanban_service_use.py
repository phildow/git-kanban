"""Behavior tests for `KanbanService.use()` context validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KANBAN_SRC = PROJECT_ROOT / "kanban"
if str(KANBAN_SRC) not in sys.path:
    sys.path.insert(0, str(KANBAN_SRC))

from repository import BoardNotFound, ColumnNotFound
from services.kanban_service import KanbanService
from services.git_service import GitService
from services.index_service import IndexService
from storage.memory_repository import InMemoryRepository


class TestKanbanServiceUse(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
        )
        self.repo.create_board("alpha")
        self.repo.create_column("alpha", "todo")

    def test_use_sets_existing_board_and_column(self):
        ctx = self.svc.use(path="alpha/todo")
        self.assertEqual(ctx.board, "alpha")
        self.assertEqual(ctx.column, "todo")

    def test_use_raises_for_missing_board(self):
        with self.assertRaises(BoardNotFound):
            self.svc.use(path="missing")

    def test_use_raises_for_missing_column(self):
        with self.assertRaises(ColumnNotFound):
            self.svc.use(path="alpha/missing")

    def test_use_relative_column_uses_active_board(self):
        self.svc.use(path="alpha")
        ctx = self.svc.use(path="todo")
        self.assertEqual(ctx.board, "alpha")
        self.assertEqual(ctx.column, "todo")


if __name__ == "__main__":
    unittest.main()
