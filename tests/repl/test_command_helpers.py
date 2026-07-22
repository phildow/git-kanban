"""Tests for handle_list_helper and handle_task_list_helper, the REPL
`list`/`ls` and `tasks` commands' scoping logic.
"""

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
    """handle_task_list_helper resolves the `tasks` command's column argument."""

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
        self.t1 = self.svc.create_task("alpha/todo", TaskCreateParams(title="Fix login"))
        self.t2 = self.svc.create_task("alpha/done", TaskCreateParams(title="Write docs"))

    def _args(self, **kwargs) -> Namespace:
        defaults = {
            "column": None,
            "exclude_columns": None,
            "sort": None,
            "reverse": False,
            "assigned_to": None,
            "priority": None,
            "tags": None,
            "due_before": None,
            "due_after": None,
            "created_by": None,
        }
        defaults.update(kwargs)
        return Namespace(**defaults)

    def test_column_board_returns_all_tasks_in_board(self) -> None:
        """column='board' returns every task across all of that board's columns."""
        result = handle_task_list_helper(self._args(column="alpha"), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_column_board_column_scopes_to_that_column(self) -> None:
        """column='board/column' returns only tasks in that column."""
        result = handle_task_list_helper(self._args(column="alpha/done"), self.svc)
        self.assertEqual([t.id for t in result], [self.t2.id])

    def test_no_column_falls_back_to_active_board_all_columns(self) -> None:
        """Omitting column returns every task in the active board, across all columns."""
        self.svc.set_board("alpha")
        result = handle_task_list_helper(self._args(), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_no_column_ignores_active_column_scope(self) -> None:
        """Even with an active column set, omitting column still returns the whole board."""
        self.svc.set_board("alpha")
        self.svc.set_column("todo")
        result = handle_task_list_helper(self._args(), self.svc)
        self.assertEqual({t.id for t in result}, {self.t1.id, self.t2.id})

    def test_no_column_and_no_active_board_raises(self) -> None:
        """Omitting column with no active board raises rather than silently listing nothing."""
        with self.assertRaises(ValueError):
            handle_task_list_helper(self._args(), self.svc)

    def test_exclude_drops_tasks_in_named_column(self) -> None:
        """exclude_columns=[name] drops tasks in that column."""
        result = handle_task_list_helper(self._args(column="alpha", exclude_columns=["done"]), self.svc)
        self.assertEqual([t.id for t in result], [self.t1.id])


if __name__ == "__main__":
    unittest.main()
