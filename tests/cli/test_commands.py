"""Tests for CLI subcommand handler dispatch.

Handlers are validated with mocked service/renderer collaborators to document
the expected method calls and argument mapping.
"""

from __future__ import annotations

import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from cli import commands
from services.kanban import TaskCreateParams, TaskUpdateParams


class TestCommandHandlers(unittest.TestCase):
    """Dispatch contract tests for CLI command handlers."""

    def setUp(self) -> None:
        self.svc = MagicMock()
        self.renderer = MagicMock()
        self.repl_renderer = MagicMock()

    def _args(self, **kwargs) -> Namespace:
        return Namespace(**kwargs)

    def test_handle_init_calls_service_and_renderer(self):
        """`init` handler calls service `initialize_kanban()` and forwards result to renderer."""
        args = self._args()
        result = object()
        self.svc.initialize_kanban.return_value = result

        commands.handle_init(args, self.svc, self.renderer)

        self.svc.initialize_kanban.assert_called_once_with()
        self.renderer.render_init.assert_called_once_with(args, result)

    def test_handle_board_list(self):
        """`board list` forwards sort options and renders list output."""
        args = self._args(sort="title", reverse=True)
        result = object()
        self.svc.get_boards.return_value = result

        commands.handle_board_list(args, self.svc, self.renderer)

        self.svc.get_boards.assert_called_once_with(sort="title", reverse=True)
        self.renderer.render_board_list.assert_called_once_with(args, result)

    def test_handle_board_create(self):
        """`board create` forwards board name and renders created board."""
        args = self._args(board="my-board")
        result = object()
        self.svc.create_board.return_value = result

        commands.handle_board_create(args, self.svc, self.renderer)

        self.svc.create_board.assert_called_once_with("my-board")
        self.renderer.render_board_create.assert_called_once_with(args, result)

    def test_handle_board_rename(self):
        """`board rename` forwards old/new board names and renders result."""
        args = self._args(board="old", new_name="new")
        result = object()
        self.svc.rename_board.return_value = result

        commands.handle_board_rename(args, self.svc, self.renderer)

        self.svc.rename_board.assert_called_once_with("old", "new")
        self.renderer.render_board_rename.assert_called_once_with(args, result)

    def test_handle_board_delete(self):
        """`board delete` forwards board name and renders deletion result."""
        args = self._args(board="my-board", force=True)
        result = object()
        self.svc.delete_board.return_value = result

        commands.handle_board_delete(args, self.svc, self.renderer)

        self.svc.delete_board.assert_called_once_with("my-board")
        self.renderer.render_board_delete.assert_called_once_with(args, result)

    def test_column_handlers(self):
        """Column handlers parse path arguments and dispatch correctly."""
        args = self._args(board="board-a", sort="title", reverse=False)
        result = object()
        self.svc.get_columns.return_value = result
        commands.handle_column_list(args, self.svc, self.renderer)
        self.svc.get_columns.assert_called_once_with(board="board-a", sort="title", reverse=False)
        self.renderer.render_column_list.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo")
        result = object()
        self.svc.create_column.return_value = result
        commands.handle_column_create(args, self.svc, self.renderer)
        self.svc.create_column.assert_called_once_with("board-a/todo")
        self.renderer.render_column_create.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", new_name="doing")
        result = object()
        self.svc.rename_column.return_value = result
        commands.handle_column_rename(args, self.svc, self.renderer)
        self.svc.rename_column.assert_called_once_with("board-a/todo", "doing")
        self.renderer.render_column_rename.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", position=2)
        result = object()
        self.svc.reorder_column.return_value = result
        commands.handle_column_reorder(args, self.svc, self.renderer)
        self.svc.reorder_column.assert_called_once_with("board-a/todo", 2)
        self.renderer.render_column_reorder.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", force=True)
        result = object()
        self.svc.delete_column.return_value = result
        commands.handle_column_delete(args, self.svc, self.renderer)
        self.svc.delete_column.assert_called_once_with("board-a/todo")
        self.renderer.render_column_delete.assert_called_once_with(args, result)

    def test_handle_task_list(self):
        """`task list` handler forwards path/sort options and renders output."""
        args = self._args(path="board-a/todo", sort="title", reverse=True)
        result = object()
        self.svc.get_tasks.return_value = result

        commands.handle_task_list(args, self.svc, self.renderer)

        from models import TaskFilter
        self.svc.get_tasks.assert_called_once_with(path="board-a/todo", filter=TaskFilter(), sort="title", reverse=True)
        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_task_create_with_all_optional_fields(self):
        """`task create` maps all optional CLI fields into `TaskCreateParams`."""
        args = self._args(
            path="board-a/todo/fix-parser",
            assignee="philip",
            priority="high",
            tags=["cli", "tests"],
            due_date="2026-06-15",
            created_by="philip",
        )
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "board-a/todo/fix-parser",
            TaskCreateParams(
                assignee="philip",
                priority="high",
                tags=["cli", "tests"],
                due_date="2026-06-15",
                created_by="philip",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_default_optional_fields(self):
        """`task create` defaults missing optional fields and normalizes `tags` to empty list."""
        args = self._args(path="board-a/todo/check-no-other-args")
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "board-a/todo/check-no-other-args",
            TaskCreateParams(
                assignee=None,
                priority=None,
                tags=[],
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_explicit_none_tags(self):
        """`task create` treats explicit `tags=None` the same as omitted tags."""
        args = self._args(
            path="board-a/todo/check-tags-none",
            assignee="alex",
            priority=None,
            tags=None,
            due_date=None,
            created_by="alex",
        )
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "board-a/todo/check-tags-none",
            TaskCreateParams(
                assignee="alex",
                priority=None,
                tags=[],
                due_date=None,
                created_by="alex",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_show(self):
        """`task show` fetches a task by path and forwards it to renderer."""
        args = self._args(path="board-a/todo/fix-parser")
        result = object()
        self.svc.get_task.return_value = result

        commands.handle_task_show(args, self.svc, self.renderer)

        self.svc.get_task.assert_called_once_with("board-a/todo/fix-parser")
        self.renderer.render_task_show.assert_called_once_with(args, result)

    def test_handle_task_update_with_default_optional_fields(self):
        """`task update` defaults unspecified update fields to `None`."""
        args = self._args(path="board-a/todo/fix-parser")
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            "board-a/todo/fix-parser",
            updates=TaskUpdateParams(
                title=None,
                assignee=None,
                priority=None,
                tags=None,
                due_date=None,
            ),
        )
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_with_all_optional_fields(self):
        """`task update` maps all provided update fields into `TaskUpdateParams`."""
        args = self._args(
            path="board-a/todo/fix-parser",
            title="fix parser robustly",
            assignee="philip",
            priority="medium",
            tags=["cli", "refactor"],
            due_date="2026-07-01",
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            "board-a/todo/fix-parser",
            updates=TaskUpdateParams(
                title="fix parser robustly",
                assignee="philip",
                priority="medium",
                tags=["cli", "refactor"],
                due_date="2026-07-01",
            ),
        )
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_with_explicit_empty_tags(self):
        """`task edit` preserves an explicit empty tags list."""
        args = self._args(path="board-a/todo/fix-parser", tags=[])
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            "board-a/todo/fix-parser",
            updates=TaskUpdateParams(
                title=None,
                assignee=None,
                priority=None,
                tags=[],
                due_date=None,
            ),
        )
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_move(self):
        """`task move` forwards source and destination paths."""
        args = self._args(path="board-a/todo/fix-parser", dest="board-a/done")
        result = object()
        self.svc.move_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with("board-a/todo/fix-parser", "board-a/done")
        self.renderer.render_task_move.assert_called_once_with(args, result)

    def test_handle_task_delete(self):
        """`task delete` forwards task path and renders deletion result."""
        args = self._args(path="board-a/todo/fix-parser", force=True)
        result = object()
        self.svc.delete_task.return_value = result

        commands.handle_task_delete(args, self.svc, self.renderer)

        self.svc.delete_task.assert_called_once_with("board-a/todo/fix-parser")
        self.renderer.render_task_delete.assert_called_once_with(args, result)

    def test_search_handler(self):
        """`search` handler forwards query and filter/sort options to service."""
        args = self._args(query="query", board="board-a", sort="title", reverse=False)
        result = object()
        self.svc.search.return_value = result

        commands.handle_search(args, self.svc, self.renderer)

        self.svc.search.assert_called_once_with("query", board="board-a", sort="title", reverse=False)
        self.renderer.render_search.assert_called_once_with(args, result)

    def test_log_handler(self):
        """`log` handler calls `svc.log` and renders the resulting output."""
        args = self._args(path="board-a/todo/task-1", limit=5)
        result = object()
        self.svc.log.return_value = result

        commands.handle_log(args, self.svc, self.renderer)

        self.svc.log.assert_called_once_with(path="board-a/todo/task-1", limit=5)
        self.renderer.render_log.assert_called_once_with(args, result)

    def test_log_handler_raises_if_missing(self):
        """`log` handler raises `NotImplementedError` when service lacks `log`."""
        args = self._args(path=None, limit=None)
        del self.svc.log

        with self.assertRaises(NotImplementedError):
            commands.handle_log(args, self.svc, self.renderer)

    def test_status_handler(self):
        """`status` handler forwards format option and renders result."""
        args = self._args(format="json")
        result = object()
        self.svc.status.return_value = result

        commands.handle_status(args, self.svc, self.renderer)

        self.svc.status.assert_called_once_with(format="json")
        self.renderer.render_status.assert_called_once_with(args, result)

    def test_status_handler_raises_if_missing(self):
        """`status` handler raises when service does not implement status."""
        args = self._args(format="table")
        del self.svc.status

        with self.assertRaises(NotImplementedError):
            commands.handle_status(args, self.svc, self.renderer)

    def test_config_handlers(self):
        """Config set/get handlers call their matching service operations."""
        args = self._args(key="name", value="Philip")
        result = object()
        self.svc.config_set.return_value = result
        commands.handle_config_set(args, self.svc, self.renderer)
        self.svc.config_set.assert_called_once_with("name", "Philip")
        self.renderer.render_config_set.assert_called_once_with(args, result)

        args = self._args(key="name")
        result = object()
        self.svc.config_get.return_value = result
        commands.handle_config_get(args, self.svc, self.renderer)
        self.svc.config_get.assert_called_once_with("name")
        self.renderer.render_config_get.assert_called_once_with(args, result)

    def test_config_handlers_raise_if_missing(self):
        """Config handlers raise when service lacks set/get implementations."""
        args_set = self._args(key="k", value="v")
        args_get = self._args(key="k")
        del self.svc.config_set
        del self.svc.config_get

        with self.assertRaises(NotImplementedError):
            commands.handle_config_set(args_set, self.svc, self.renderer)

        with self.assertRaises(NotImplementedError):
            commands.handle_config_get(args_get, self.svc, self.renderer)


if __name__ == "__main__":
    unittest.main()
