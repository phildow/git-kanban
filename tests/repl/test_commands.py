"""Tests for REPL subcommand handler dispatch.

Handlers are validated with mocked service/renderer collaborators to document
expected method calls and argument mapping.
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from kanban.models import Board, Column, Slug, Task
from kanban.repl import commands
from kanban.services.kanban import TaskCreateParams, TaskUpdateParams


class TestReplCommandHandlers(unittest.TestCase):
    """Dispatch contract tests for REPL command handlers."""

    def setUp(self) -> None:
        self.svc = MagicMock()
        self.renderer = MagicMock()

    def _args(self, **kwargs) -> Namespace:
        return Namespace(**kwargs)

    def test_handle_set_board_defaults_to_clear_without_board(self):
        args = self._args(board=None)
        result = object()
        self.svc.change_dir.return_value = result

        commands.handle_set_board(args, self.svc, self.renderer)

        self.svc.change_dir.assert_called_once_with(clear=True)
        self.renderer.render_set_board.assert_called_once_with(args, result)

    def test_handle_set_board_with_board(self):
        args = self._args(board="alpha")
        result = object()
        self.svc.set_board.return_value = result

        commands.handle_set_board(args, self.svc, self.renderer)

        self.svc.set_board.assert_called_once_with(board="alpha")
        self.renderer.render_set_board.assert_called_once_with(args, result)

    def test_handle_delete_renders_board_delete(self):
        args = self._args(path="alpha")
        deleted = object()
        with patch("kanban.repl.commands.handle_delete_helper", return_value=(Board, deleted)):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_board_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_renders_column_delete(self):
        args = self._args(path="alpha/todo")
        deleted = object()
        with patch("kanban.repl.commands.handle_delete_helper", return_value=(Column, deleted)):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_column_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_renders_task_delete(self):
        args = self._args(path="alpha/todo/fix-parser")
        deleted = object()
        with patch("kanban.repl.commands.handle_delete_helper", return_value=(Task, deleted)):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_task_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_raises_for_unexpected_type(self):
        args = self._args(path="alpha")
        with patch("kanban.repl.commands.handle_delete_helper", return_value=(str, object())):
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

    def test_handle_rename_board(self) -> None:
        """`rename -b` calls rename_board for the active board and renders the result."""
        result = object()
        self.svc.rename_board.return_value = result
        self.svc.working_board = "proj"
        args = self._args(path=None, board=True, new_name="Work")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_board.assert_called_once_with(path=None, new_name="Work")
        self.renderer.render_board_rename.assert_called_once_with(args, result)

    def test_handle_rename_column(self) -> None:
        """`rename` with a board/column path calls rename_column and renders the result."""
        self.svc.path_components.return_value = ("proj", "todo", None)
        result = object()
        self.svc.rename_column.return_value = result
        args = self._args(path="proj/todo", board=False, new_name="Doing")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_column.assert_called_once_with(path=Path("/proj/todo"), new_name="Doing")
        self.renderer.render_column_rename.assert_called_once_with(args, result)

    def test_handle_rename_task(self) -> None:
        """`rename` with a board/column/task path calls rename_task and renders the result."""
        self.svc.path_components.return_value = ("proj", "todo", "fix-parser")
        result = object()
        self.svc.rename_task.return_value = result
        args = self._args(path="proj/todo/fix-parser", board=False, new_name="Fixed Parser")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_task.assert_called_once_with(path=Path("/proj/todo/fix-parser"), new_title="Fixed Parser")
        self.renderer.render_task_rename.assert_called_once_with(args, result)

    def test_column_handlers(self):
        args = self._args(column="todo")
        self.svc.working_board = "alpha"
        result = object()
        self.svc.create_column.return_value = result
        commands.handle_column_create(args, self.svc, self.renderer)
        self.svc.create_column.assert_called_once_with(None, "todo")
        self.renderer.render_column_create.assert_called_once_with(args, result)

    def test_handle_column_create_raises_without_active_board(self):
        """create column with no active board raises rather than resolving nonsense."""
        args = self._args(column="todo")
        self.svc.working_board = None
        with self.assertRaises(ValueError):
            commands.handle_column_create(args, self.svc, self.renderer)

    def test_handle_board_list(self):
        """`boards` renders the board list."""
        args = self._args()
        result = object()
        self.svc.get_boards.return_value = result

        commands.handle_board_list(args, self.svc, self.renderer)

        self.svc.get_boards.assert_called_once_with()
        self.renderer.render_board_list.assert_called_once_with(args, result)

    def test_handle_task_list(self):
        """`tasks` delegates to handle_task_list_helper and renders the result."""
        args = self._args(path="alpha/todo")
        result = [object()]
        with patch("kanban.repl.commands.handle_task_list_helper", return_value=result) as mock_helper:
            commands.handle_task_list(args, self.svc, self.renderer)

        mock_helper.assert_called_once_with(args, self.svc)
        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_column_list(self):
        """`columns`/`cols` forwards board and renders the column list."""
        args = self._args(board="alpha")
        result = object()
        self.svc.get_columns.return_value = result

        commands.handle_column_list(args, self.svc, self.renderer)

        self.svc.get_columns.assert_called_once_with(board="alpha")
        self.renderer.render_column_list.assert_called_once_with(args, result)

    def test_handle_column_list_defaults_to_active_board(self):
        """`columns` with no board falls back to the active board context."""
        args = self._args(board=None)
        result = object()
        self.svc.working_board = "alpha"
        self.svc.get_columns.return_value = result

        commands.handle_column_list(args, self.svc, self.renderer)

        self.svc.get_columns.assert_called_once_with(board=None)
        self.renderer.render_column_list.assert_called_once_with(args, result)

    def test_handle_column_list_raises_without_any_board(self):
        """`columns` with no board argument and no active board raises."""
        args = self._args(board=None)
        self.svc.working_board = None
        self.svc.get_columns.side_effect = ValueError("No board specified and no board in context")

        with self.assertRaises(ValueError):
            commands.handle_column_list(args, self.svc, self.renderer)

    def test_handle_task_create_defaults(self):
        args = self._args(column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        self.svc.working_board = "alpha"
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "todo",
            TaskCreateParams(
                title="fix-parser",
                assigned_to=None,
                priority=None,
                tags=[],
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_without_edit_flag_does_not_open_editor(self):
        """create task without --edit does not call svc.edit_task."""
        args = self._args(column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        self.svc.working_board = "alpha"
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.edit_task.assert_not_called()
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_edit_flag_opens_editor(self):
        """create task --edit opens the newly created task in the editor."""
        args = self._args(column="todo", title="fix-parser", edit=True, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        self.svc.working_board = "alpha"
        created = Task(id=uuid4(), title="Fix parser", slug="fix-parser", board="alpha", column="todo")
        edited = Task(id=uuid4(), title="Fix parser", slug="fix-parser", board="alpha", column="todo")
        self.svc.create_task.return_value = created
        self.svc.edit_task.return_value = edited

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.edit_task.assert_called_once_with(created.path)
        self.renderer.render_task_create.assert_called_once_with(args, edited)

    def test_handle_task_create_with_optional_fields(self):
        args = self._args(
            column="todo",
            title="fix-parser",
            assigned_to="philip",
            priority="high",
            tags=["cli", "tests"],
            due_date="2026-06-17",
            created_by="philip",
            edit=False,
        )
        self.svc.working_board = "alpha"
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "todo",
            TaskCreateParams(
                title="fix-parser",
                assigned_to="philip",
                priority="high",
                tags=["cli", "tests"],
                due_date="2026-06-17",
                created_by="philip",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_raises_without_active_board(self):
        """create task with no active board raises rather than resolving nonsense."""
        args = self._args(column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        self.svc.working_board = None
        self.svc.create_task.side_effect = ValueError("No active board; set one with `board` before creating a task")
        with self.assertRaises(ValueError):
            commands.handle_task_create(args, self.svc, self.renderer)

    def test_handle_task_show(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.get_task.return_value = result

        commands.handle_task_show(args, self.svc, self.renderer)

        self.svc.get_task.assert_called_once_with(Slug("alpha/todo/fix-parser"))
        self.renderer.render_task_show.assert_called_once_with(args, result)

    def test_handle_task_edit(self):
        args = self._args(path="alpha/todo/fix-parser")
        result = object()
        self.svc.edit_task.return_value = result

        commands.handle_task_edit(args, self.svc, self.renderer)

        self.svc.edit_task.assert_called_once_with(Slug("alpha/todo/fix-parser"))
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_defaults(self):
        args = self._args(path="alpha/todo/fix-parser", assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, column=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            Slug("alpha/todo/fix-parser"),
            updates=TaskUpdateParams(
                title=None,
                assigned_to=None,
                priority=None,
                tags=None,
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_update_with_fields(self):
        args = self._args(
            path="alpha/todo/fix-parser",
            assigned_to="philip",
            priority="medium",
            tags=["cli"],
            due_date="2026-07-01",
            created_by="alice",
            column=None,
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            Slug("alpha/todo/fix-parser"),
            updates=TaskUpdateParams(
                assigned_to="philip",
                priority="medium",
                tags=["cli"],
                due_date="2026-07-01",
                created_by="alice",
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_update_without_column_does_not_move(self):
        """`update` without --column applies updates only and never calls move_task."""
        args = self._args(path="alpha/todo/fix-parser", column=None, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.move_task.assert_not_called()
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_update_with_column_moves_task(self):
        """`update --column` moves the updated task to the given column and renders the moved result."""
        args = self._args(path="alpha/todo/fix-parser", column="done", assigned_to=None, priority=None, tags=None, due_date=None, created_by=None)
        updated = MagicMock()
        updated.path = "/alpha/todo/fix-parser"
        moved = object()
        self.svc.update_task.return_value = updated
        self.svc.move_task.return_value = moved

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with(Path("/alpha/todo/fix-parser"), Slug("done"))
        self.renderer.render_task_update.assert_called_once_with(args, moved)

    def test_handle_task_move(self):
        """`move` with a column forwards path and column to move_task and renders via render_task_move."""
        args = self._args(path="alpha/todo/fix-parser", column="done")
        result = object()
        self.svc.move_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), Slug("done"))
        self.renderer.render_task_move.assert_called_once_with(args, result)

    def test_handle_task_move_top(self):
        """`move --top` calls reorder_task with "top" and renders via render_task_reorder."""
        args = self._args(path="alpha/todo/fix-parser", column=None, top=True, bottom=False, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), "top")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "top"))

    def test_handle_task_move_bottom(self):
        """`move --bottom` calls reorder_task with "bottom" and renders via render_task_reorder."""
        args = self._args(path="alpha/todo/fix-parser", column=None, top=False, bottom=True, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), "bottom")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "bottom"))

    def test_handle_task_move_up(self):
        """`move --up` calls reorder_task with "up" and renders via render_task_reorder."""
        args = self._args(path="alpha/todo/fix-parser", column=None, top=False, bottom=False, up=True, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), "up")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "up"))

    def test_handle_task_move_down(self):
        """`move --down` calls reorder_task with "down" and renders via render_task_reorder."""
        args = self._args(path="alpha/todo/fix-parser", column=None, top=False, bottom=False, up=False, down=True)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), "down")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "down"))

    def test_handle_task_assign(self):
        """`assign` forwards path and user to assign_task and renders result."""
        args = self._args(path="alpha/todo/fix-parser", assigned_to="alice")
        result = object()
        self.svc.assign_task.return_value = result

        commands.handle_task_assign(args, self.svc, self.renderer)

        self.svc.assign_task.assert_called_once_with(Slug("alpha/todo/fix-parser"), "alice")
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

        self.svc.log.assert_called_once_with(path=Path("alpha/todo/fix-parser"), limit=5)
        self.renderer.render_log.assert_called_once_with(args, result)

    def test_handle_status(self):
        args = self._args(format="json")
        result = object()
        self.svc.status.return_value = result

        commands.handle_status(args, self.svc, self.renderer)

        self.svc.status.assert_called_once()
        self.renderer.render_status.assert_called_once_with(args, result)

    def test_handle_set_config_and_get(self):
        args = self._args(key="name", value="Philip")
        result = object()
        self.svc.set_config.return_value = result

        commands.handle_set_config(args, self.svc, self.renderer)

        self.svc.set_config.assert_called_once_with("name", "Philip")
        self.renderer.render_set_config.assert_called_once_with(args, result)

        args = self._args(key="name")
        result = object()
        self.svc.get_config.return_value = result

        commands.handle_get_config(args, self.svc, self.renderer)

        self.svc.get_config.assert_called_once_with("name")
        self.renderer.render_get_config.assert_called_once_with(args, result)

if __name__ == "__main__":
    unittest.main()
