"""Tests for handle_task_list_helper, the REPL `tasks` command's scoping logic."""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.repl.command_helpers import handle_task_list_helper
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestHandleTaskListHelper(unittest.TestCase):
    """handle_task_list_helper resolves the `tasks` command's path argument."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "done", slug="done")
        self.t1 = self.svc.create_task("alpha/todo/Fix login", TaskCreateParams())
        self.t2 = self.svc.create_task("alpha/done/Write docs", TaskCreateParams())

    def _args(self, **kwargs) -> Namespace:
        defaults = {"path": None, "sort": None, "reverse": False}
        defaults.update(kwargs)
        return Namespace(**defaults)

    def test_path_board_returns_all_tasks_in_board(self) -> None:
        """path='board' returns every task across all of that board's columns."""
        result = handle_task_list_helper(self._args(path="alpha"), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_path_board_column_scopes_to_that_column(self) -> None:
        """path='board/column' returns only tasks in that column."""
        result = handle_task_list_helper(self._args(path="alpha/done"), self.svc)
        self.assertEqual([t.id for t in result], [self.t2.id])

    def test_no_path_falls_back_to_active_board_all_columns(self) -> None:
        """Omitting path returns every task in the active board, across all columns."""
        self.svc.set_board("alpha")
        result = handle_task_list_helper(self._args(), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_no_path_ignores_active_column_scope(self) -> None:
        """Even with an active column set, omitting path still returns the whole board."""
        self.svc.set_board("alpha")
        self.svc.set_column("todo")
        result = handle_task_list_helper(self._args(), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_no_path_and_no_active_board_raises(self) -> None:
        """Omitting path with no active board raises rather than silently listing nothing."""
        with self.assertRaises(ValueError):
            handle_task_list_helper(self._args(), self.svc)

    def test_exclude_drops_tasks_in_named_column(self) -> None:
        """column=[name] (the --exclude flag's dest) drops tasks in that column."""
        result = handle_task_list_helper(self._args(path="alpha", column=["done"]), self.svc)
        self.assertEqual([t.id for t in result], [self.t1.id])


if __name__ == "__main__":
    unittest.main()
