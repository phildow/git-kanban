"""Tests for REPL subcommand handler dispatch.

Handlers are validated with mocked service/renderer collaborators to document
expected method calls and argument mapping.
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from models import Board, Column, Task
from repl import commands
from services.kanban import TaskCreateParams, TaskUpdateParams


class TestReplCommandHandlers(unittest.TestCase):
    """Dispatch contract tests for REPL command handlers."""

    def setUp(self) -> None:
        self.svc = MagicMock()
        self.renderer = MagicMock()

    def _args(self, **kwargs) -> Namespace:
        return Namespace(**kwargs)

    def test_handle_change_dir_defaults_to_clear_without_path(self):
        args = self._args(path=None, clear=False)
        result = object()
        self.svc.change_dir.return_value = result

        commands.handle_change_dir(args, self.svc, self.renderer)

        self.svc.change_dir.assert_called_once_with(clear=True)
        self.renderer.render_change_dir.assert_called_once_with(args, result)

    def test_handle_change_dir_clear_flag(self):
        args = self._args(path="alpha/todo", clear=True)
        result = object()
        self.svc.change_dir.return_value = result

        commands.handle_change_dir(args, self.svc, self.renderer)

        self.svc.change_dir.assert_called_once_with(clear=True)
        self.renderer.render_change_dir.assert_called_once_with(args, result)

    def test_handle_change_dir_with_path(self):
        args = self._args(path="alpha/todo", clear=False)
        result = object()
        self.svc.change_dir.return_value = result

        commands.handle_change_dir(args, self.svc, self.renderer)

        self.svc.change_dir.assert_called_once_with(path="alpha/todo")
        self.renderer.render_change_dir.assert_called_once_with(args, result)

    def test_handle_board_sets_context_to_board(self):
        args = self._args(board="alpha")
        result = object()
        self.svc.set_board.return_value = result

        commands.handle_board_change(args, self.svc, self.renderer)

        self.svc.set_board.assert_called_once_with(board="alpha")
        self.renderer.render_change_board.assert_called_once_with(args, result)

    def test_handle_board_raises_when_board_missing(self):
        args = self._args(board="missing")
        self.svc.set_board.side_effect = ValueError("Board not found: missing")

        with self.assertRaises(ValueError):
            commands.handle_board_change(args, self.svc, self.renderer)

    def test_handle_column_sets_context_to_column(self):
        args = self._args(column="todo")
        result = object()
        self.svc.set_column.return_value = result

        commands.handle_column_change(args, self.svc, self.renderer)

        self.svc.set_column.assert_called_once_with(column="todo")
        self.renderer.render_change_column.assert_called_once_with(args, result)

    def test_handle_column_raises_when_column_missing(self):
        args = self._args(column="missing")
        self.svc.set_column.side_effect = ValueError("Column not found: missing")

        with self.assertRaises(ValueError):
            commands.handle_column_change(args, self.svc, self.renderer)

    def test_handle_list_renders_board_list(self):
        args = self._args(path=None)
        result = object()
        with patch("repl.commands.handle_list_helper", return_value=(Board, result)):
            commands.handle_list(args, self.svc, self.renderer)

        self.renderer.render_board_list.assert_called_once_with(args, result)

    def test_handle_list_renders_column_list(self):
        args = self._args(path="alpha")
        result = object()
        with patch("repl.commands.handle_list_helper", return_value=(Column, result)):
            commands.handle_list(args, self.svc, self.renderer)

        self.renderer.render_column_list.assert_called_once_with(args, result)

    def test_handle_list_renders_task_list(self):
        args = self._args(path="alpha/todo")
        result = object()
        with patch("repl.commands.handle_list_helper", return_value=(Task, result)):
            commands.handle_list(args, self.svc, self.renderer)

        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_list_raises_for_unexpected_type(self):
        args = self._args(path=None)
        with patch("repl.commands.handle_list_helper", return_value=([], str)):
            with self.assertRaises(ValueError):
                commands.handle_list(args, self.svc, self.renderer)

    def test_handle_delete_renders_board_delete(self):
        args = self._args(path="alpha")
        with patch("repl.commands.handle_delete_helper", return_value=Board):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_board_delete.assert_called_once_with(args)

    def test_handle_delete_renders_column_delete(self):
        args = self._args(path="alpha/todo")
        with patch("repl.commands.handle_delete_helper", return_value=Column):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_column_delete.assert_called_once_with(args)

    def test_handle_delete_renders_task_delete(self):
        args = self._args(path="alpha/todo/fix-parser")
        with patch("repl.commands.handle_delete_helper", return_value=Task):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_task_delete.assert_called_once_with(args)

    def test_handle_delete_raises_for_unexpected_type(self):
        args = self._args(path="alpha")
        with patch("repl.commands.handle_delete_helper", return_value=str):
            with self.assertRaises(ValueError):
                commands.handle_delete(args, self.svc, self.renderer)

    def test_board_handlers(self):
        args = self._args(board="alpha")
        result = object()
        self.svc.create_board.return_value = result

        commands.handle_board_create(args, self.svc, self.renderer)

        self.svc.create_board.assert_called_once_with("alpha")
        self.renderer.render_board_create.assert_called_once_with(args, result)

        args = self._args(board="alpha", new_name="beta")
        result = object()
        self.svc.rename_board.return_value = result

        commands.handle_board_rename(args, self.svc, self.renderer)

        self.svc.rename_board.assert_called_once_with("alpha", "beta")
        self.renderer.render_board_rename.assert_called_once_with(args, result)

    def test_column_handlers(self):
        args = self._args(path="alpha/todo")
        result = object()
        self.svc.create_column.return_value = result
        commands.handle_column_create(args, self.svc, self.renderer)
        self.svc.create_column.assert_called_once_with("alpha/todo")
        self.renderer.render_column_create.assert_called_once_with(args, result)

        args = self._args(path="alpha/todo", new_name="doing")
        result = object()
        self.svc.rename_column.return_value = result
        commands.handle_column_rename(args, self.svc, self.renderer)
        self.svc.rename_column.assert_called_once_with("alpha/todo", "doing")
        self.renderer.render_column_rename.assert_called_once_with(args, result)

        args = self._args(path="alpha/todo", position=2)
        result = object()
        self.svc.reorder_column.return_value = result
        commands.handle_column_reorder(args, self.svc, self.renderer)
        self.svc.reorder_column.assert_called_once_with("alpha/todo", 2)
        self.renderer.render_column_reorder.assert_called_once_with(args, result)

    def test_handle_task_create_defaults(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "alpha/todo/fix-parser",
            TaskCreateParams(
                assigned_to=None,
                priority=None,
                tags=[],
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_optional_fields(self):
        args = self._args(
            path="alpha/todo/fix-parser",
            assigned_to="philip",
            priority="high",
            tags=["cli", "tests"],
            due_date="2026-06-17",
            created_by="philip",
        )
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "alpha/todo/fix-parser",
            TaskCreateParams(
                assigned_to="philip",
                priority="high",
                tags=["cli", "tests"],
                due_date="2026-06-17",
                created_by="philip",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_show(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.get_task.return_value = result

        commands.handle_task_show(args, self.svc, self.renderer)

        self.svc.get_task.assert_called_once_with("alpha/todo/fix-parser")
        self.renderer.render_task_show.assert_called_once_with(args, result)

    def test_handle_task_edit(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.edit_task.return_value = result

        commands.handle_task_edit(args, self.svc, self.renderer)

        self.svc.edit_task.assert_called_once_with("alpha/todo/fix-parser")
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_defaults(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            "alpha/todo/fix-parser",
            updates=TaskUpdateParams(
                title=None,
                assigned_to=None,
                priority=None,
                tags=None,
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_with_fields(self):
        args = self._args(
            path="alpha/todo/fix-parser",
            title="fix parser",
            assigned_to="philip",
            priority="medium",
            tags=["cli"],
            due_date="2026-07-01",
            created_by="alice",
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            "alpha/todo/fix-parser",
            updates=TaskUpdateParams(
                title="fix parser",
                assigned_to="philip",
                priority="medium",
                tags=["cli"],
                due_date="2026-07-01",
                created_by="alice",
            ),
        )
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_move(self):
        args = self._args(path="alpha/todo/fix-parser", column="done")
        result = object()
        self.svc.move_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with("alpha/todo/fix-parser", "done")
        self.renderer.render_task_move.assert_called_once_with(args, result)

    def test_handle_task_assign(self):
        """`assign` forwards path and user to assign_task and renders result."""
        args = self._args(path="alpha/todo/fix-parser", assigned_to="alice")
        result = object()
        self.svc.assign_task.return_value = result

        commands.handle_task_assign(args, self.svc, self.renderer)

        self.svc.assign_task.assert_called_once_with("alpha/todo/fix-parser", "alice")
        self.renderer.render_task_assign.assert_called_once_with(args, result)

    def test_handle_search(self):
        args = self._args(query="fix", board="alpha", sort="title", reverse=True)
        result = object()
        self.svc.search.return_value = result

        commands.handle_search(args, self.svc, self.renderer)

        self.svc.search.assert_called_once_with("fix", board="alpha", sort="title", reverse=True)
        self.renderer.render_search.assert_called_once_with(args, result)

    def test_handle_log(self):
        args = self._args(path="alpha/todo/fix-parser", limit=5)
        result = object()
        self.svc.log.return_value = result

        commands.handle_log(args, self.svc, self.renderer)

        self.svc.log.assert_called_once_with(path="alpha/todo/fix-parser", limit=5)
        self.renderer.render_log.assert_called_once_with(args, result)

    def test_handle_status(self):
        args = self._args(format="json")
        result = object()
        self.svc.status.return_value = result

        commands.handle_status(args, self.svc, self.renderer)

        self.svc.status.assert_called_once_with(format="json")
        self.renderer.render_status.assert_called_once_with(args, result)

    def test_handle_config_set_and_get(self):
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

if __name__ == "__main__":
    unittest.main()
