"""Bootstrap tests for `KanbanService.init()`.

These tests document initialization semantics for in-memory bootstrapping.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from models import UserContext
from services.kanban import KanbanService, KanbanRoot
from services.git import GitService
from services.index import IndexService
from storage.memory import InMemoryRepository


class TestKanbanServiceInit(unittest.TestCase):
    """Tests for one-time repository bootstrap behavior."""

    def test_init_creates_main_board_and_marks_initialized(self):
        """First init creates main board, default columns, context, and init flag."""
        repo = InMemoryRepository()
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
            user_context=UserContext(),
        )

        result = svc.init(Path("."))

        self.assertIsInstance(result, KanbanRoot)
        self.assertEqual(result.path, Path(".kanban"))
        self.assertEqual(result.boards_dir, Path(".kanban/boards"))
        self.assertFalse(result.git_init)
        self.assertTrue(repo.board_exists("main"))
        self.assertEqual(
            [c.name for c in repo.list_columns("main")],
            ["todo", "in-progress", "in-review", "done"],
        )
        self.assertEqual(
            [c.position for c in repo.list_columns("main")],
            [0, 1, 2, 3],
        )

        self.assertEqual(svc.user_context.board, "main")
        self.assertEqual(svc.user_context.column, "todo")
        self.assertEqual(repo.get_config("initialized"), "true")

    def test_init_raises_when_called_twice(self):
        """Second init call raises because repository is already initialized."""
        repo = InMemoryRepository()
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
            user_context=UserContext(),
        )

        svc.init(Path("."))
        with self.assertRaises(ValueError):
            svc.init(Path("."))

    def test_init_raises_when_main_board_already_exists(self):
        """Init raises if sentinel board state already indicates bootstrapped repo."""
        repo = InMemoryRepository()
        repo.create_board("main")
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
            user_context=UserContext(),
        )

        with self.assertRaises(ValueError):
            svc.init(Path("."))


if __name__ == "__main__":
    unittest.main()
