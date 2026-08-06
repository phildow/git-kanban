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

from kanban.models import Slug
from kanban.models.config import CONFIG_NEW_TASK_INSERT, INSERT_BELOW
from kanban.repl.command_helpers import (
    handle_create_helper,
    handle_info_helper,
    handle_task_list_helper,
)
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
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
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
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
            "include_archived": False,
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
        self.svc.set_board(Slug("alpha"))
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

    def test_include_archived_returns_archived_tasks(self) -> None:
        """The flag rides on the filter and widens the board listing to the archive."""
        archived = self.svc.archive_task(self.t2.path)

        result = handle_task_list_helper(self._args(column="alpha", include_archived=True), self.svc)

        self.assertEqual({t.id for t in result}, {self.t1.id, archived.id})

    def test_include_archived_with_a_column_raises(self) -> None:
        """The flag lists a whole board; naming a column is an error."""
        with self.assertRaises(ValueError):
            handle_task_list_helper(self._args(column="alpha/done", include_archived=True), self.svc)

    def test_include_archived_with_archive_excluded_raises(self) -> None:
        """Including and excluding the archive at once is an error."""
        self.svc.archive_task(self.t2.path)

        with self.assertRaises(ValueError):
            handle_task_list_helper(
                self._args(column="alpha", exclude_columns=["archive"], include_archived=True),
                self.svc,
            )


class TestHandleInfoHelper(unittest.TestCase):
    """handle_info_helper returns the object the `info` command names."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.svc.set_board(Slug("alpha"))
        self.task = self.svc.create_task("/alpha/todo", TaskCreateParams(title="Fix login"))

    def _args(self, **kwargs) -> Namespace:
        defaults = {"path": None, "board": False, "column": None}
        defaults.update(kwargs)
        return Namespace(**defaults)

    def test_board_flag_returns_the_active_board(self) -> None:
        """-b resolves the board the user context holds."""
        result = handle_info_helper(self._args(board=True), self.svc)

        self.assertEqual(result.slug, "alpha")
        self.assertEqual(str(result.path), "/alpha")

    def test_board_flag_without_an_active_board_raises(self) -> None:
        """-b has nothing to resolve when no board is active."""
        self.svc.clear_user_context()

        with self.assertRaises(ValueError):
            handle_info_helper(self._args(board=True), self.svc)

    def test_column_flag_returns_the_named_column(self) -> None:
        """-c COLUMN resolves within the active board."""
        result = handle_info_helper(self._args(column="todo"), self.svc)

        self.assertEqual(result.slug, "todo")
        self.assertEqual(str(result.path), "/alpha/todo")

    def test_task_slug_returns_the_task(self) -> None:
        """A bare slug resolves to its task, column and all."""
        result = handle_info_helper(self._args(path=Slug("fix-login")), self.svc)

        self.assertEqual(result.id, self.task.id)
        self.assertEqual(str(result.path), "/alpha/todo/fix-login")

    def test_no_target_raises(self) -> None:
        """A namespace naming nothing is a command that cannot be answered."""
        with self.assertRaises(ValueError):
            handle_info_helper(self._args(), self.svc)


class TestHandleCreateHelperSelection(unittest.TestCase):
    """The `create` command places a task against whatever the consumer has selected."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.svc.set_board(Slug("alpha"))

        for title in ("first", "second", "third"):
            self.svc.create_task("/alpha/todo", TaskCreateParams(title=title))

        self.svc.set_config(CONFIG_NEW_TASK_INSERT, INSERT_BELOW)

    def _args(self, title: str) -> Namespace:
        """Return the namespace `create <column> <title>` parses to."""
        return Namespace(
            new_board=None,
            new_column=None,
            column="todo",
            title=title,
            edit=False,
            assigned_to=None,
            priority=None,
            tags=None,
            due_date=None,
            created_by=None,
            description=None,
        )

    def _slugs(self) -> list[str]:
        """Return the slugs the todo column holds, in order."""
        return [task.slug for task in self.svc.get_tasks("/alpha/todo")]

    def test_a_selected_task_positions_the_new_one(self) -> None:
        """Set to below, the new task follows the task the consumer has selected."""
        self.svc.set_selection(Slug("alpha"), Slug("todo"), Slug("first"))
        handle_create_helper(self._args("fourth"), self.svc)

        self.assertEqual(self._slugs(), ["first", "fourth", "second", "third"])

    def test_no_selection_falls_back(self) -> None:
        """With nothing selected — the REPL's case — the task goes to the bottom."""
        handle_create_helper(self._args("fourth"), self.svc)

        self.assertEqual(self._slugs(), ["first", "second", "third", "fourth"])


if __name__ == "__main__":
    unittest.main()
