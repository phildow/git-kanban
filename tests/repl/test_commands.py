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

from kanban.models import Board, Column, Selection, Slug, Task, TaskFilter
from kanban.repl import commands
from kanban.services.kanban import TaskCreateParams, TaskUnsetParams, TaskUpdateParams


class TestReplCommandHandlers(unittest.TestCase):
    """Dispatch contract tests for REPL command handlers."""

    def setUp(self) -> None:
        self.svc = MagicMock()
        self.renderer = MagicMock()
        # The REPL selects nothing, so the create handler passes no task to
        # position the new one against.
        self.svc.selection = Selection()

    def _args(self, **kwargs) -> Namespace:
        return Namespace(**kwargs)

    def test_handle_set_board_with_board(self):
        args = self._args(board="alpha")
        result = object()
        self.svc.set_board.return_value = result

        commands.handle_set_board(args, self.svc, self.renderer)

        self.svc.set_board.assert_called_once_with(slug=Slug("alpha"))
        self.renderer.render_set_board.assert_called_once_with(args, result)

    def test_handle_delete_renders_board_delete(self):
        args = self._args(path=None, board=True, column=None)
        deleted = MagicMock(spec=Board)
        with patch("kanban.repl.commands.handle_delete_helper", return_value=deleted):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_board_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_renders_column_delete(self):
        args = self._args(path=None, board=False, column="todo")
        deleted = MagicMock(spec=Column)
        with patch("kanban.repl.commands.handle_delete_helper", return_value=deleted):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_column_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_renders_task_delete(self):
        args = self._args(path="fix-parser", board=False, column=None)
        deleted = MagicMock(spec=Task)
        with patch("kanban.repl.commands.handle_delete_helper", return_value=deleted):
            commands.handle_delete(args, self.svc, self.renderer)

        self.renderer.render_task_delete.assert_called_once_with(args, deleted)

    def test_handle_delete_raises_for_unexpected_type(self):
        args = self._args(path=None, board=True, column=None)
        with patch("kanban.repl.commands.handle_delete_helper", return_value=object()):
            with self.assertRaises(ValueError):
                commands.handle_delete(args, self.svc, self.renderer)

    def test_board_handlers(self):
        args = self._args(new_board="alpha", new_column=None, column=None)
        result = MagicMock(spec=Board)
        self.svc.create_board.return_value = result

        commands.handle_create(args, self.svc, self.renderer)

        self.svc.create_board.assert_called_once_with("alpha")
        self.renderer.render_board_create.assert_called_once_with(args, result)

        args = self._args(board="alpha", new_name="beta")
        result = MagicMock(spec=Board)
        self.svc.rename_board.return_value = result

    def test_handle_rename_board(self) -> None:
        """`rename -b` calls rename_board for the active board and renders the result."""
        result = MagicMock(spec=Board)
        self.svc.rename_board.return_value = result
        self.svc.working_board = "proj"
        args = self._args(path=None, board=True, column=None, new_name="Work")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_board.assert_called_once_with(path=None, new_name="Work")
        self.renderer.render_board_rename.assert_called_once_with(args, result)

    def test_handle_rename_column(self) -> None:
        """`rename -c COLUMN` calls rename_column and renders the result."""
        result = MagicMock(spec=Column)
        self.svc.rename_column.return_value = result
        self.svc.working_board = "proj"
        args = self._args(path=None, board=False, column="todo", new_name="Doing")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_column.assert_called_once_with(path=Slug("todo"), new_name="Doing")
        self.renderer.render_column_rename.assert_called_once_with(args, result)

    def test_handle_rename_task(self) -> None:
        """`rename <task-slug>` calls rename_task and renders the result."""
        result = MagicMock(spec=Task)
        self.svc.rename_task.return_value = result
        self.svc.working_board = "proj"
        args = self._args(path="fix-parser", board=False, column=None, new_name="Fixed Parser")

        commands.handle_rename(args, self.svc, self.renderer)

        self.svc.rename_task.assert_called_once_with(path=Slug("fix-parser"), new_title="Fixed Parser")
        self.renderer.render_task_rename.assert_called_once_with(args, result)

    def test_handle_info_board(self) -> None:
        """`info -b` looks the active board up and renders its details."""
        result = MagicMock(spec=Board)
        self.svc.get_board.return_value = result
        self.svc.working_board = Slug("proj")
        args = self._args(path=None, board=True, column=None, show_path=False, show_id=False)

        commands.handle_info(args, self.svc, self.renderer)

        self.svc.get_board.assert_called_once_with(Slug("proj"))
        self.renderer.render_board_info.assert_called_once_with(args, result)

    def test_handle_info_column(self) -> None:
        """`info -c COLUMN` looks the column up and renders its details."""
        result = MagicMock(spec=Column)
        self.svc.get_column.return_value = result
        args = self._args(path=None, board=False, column="todo", show_path=False, show_id=False)

        commands.handle_info(args, self.svc, self.renderer)

        self.svc.get_column.assert_called_once_with(Slug("todo"))
        self.renderer.render_column_info.assert_called_once_with(args, result)

    def test_handle_info_renders_the_object_whatever_the_field_flags_say(self) -> None:
        """
        The handler renders the object it found and nothing more.

        `--path` and `--id` are answered by the FieldRenderer the shell puts in
        front of the renderer, so the handler makes the same call either way.
        """
        result = MagicMock(spec=Task)
        self.svc.get_task.return_value = result
        args = self._args(path="fix-parser", board=False, column=None, show_path=True, show_id=True)

        commands.handle_info(args, self.svc, self.renderer)

        self.renderer.render_task_info.assert_called_once_with(args, result)

    def test_column_handlers(self):
        args = self._args(new_board=None, new_column="todo", column=None)
        self.svc.working_board = "alpha"
        result = MagicMock(spec=Column)
        self.svc.create_column.return_value = result
        commands.handle_create(args, self.svc, self.renderer)
        self.svc.create_column.assert_called_once_with(None, "todo")
        self.renderer.render_column_create.assert_called_once_with(args, result)

    def test_handle_column_create_raises_without_active_board(self):
        """create column with no active board raises rather than resolving nonsense."""
        args = self._args(new_board=None, new_column="todo", column=None)
        self.svc.working_board = None
        with self.assertRaises(ValueError):
            commands.handle_create(args, self.svc, self.renderer)

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
        args = self._args(column="todo")
        result = [object()]
        with patch("kanban.repl.commands.handle_task_list_helper", return_value=result) as mock_helper:
            commands.handle_task_list(args, self.svc, self.renderer)

        mock_helper.assert_called_once_with(args, self.svc)
        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_column_list(self):
        """`columns`/`cols` uses the active board and renders the column list."""
        self.svc.working_board = "alpha"
        args = self._args()
        result = object()
        self.svc.get_columns.return_value = result

        commands.handle_column_list(args, self.svc, self.renderer)

        self.svc.get_columns.assert_called_once_with(board=None)
        self.renderer.render_column_list.assert_called_once_with(args, result)

    def test_handle_column_list_raises_without_any_board(self):
        """`columns` with no active board propagates the service error."""
        args = self._args()
        self.svc.working_board = None
        self.svc.get_columns.side_effect = ValueError("No board specified and no board in context")

        with self.assertRaises(ValueError):
            commands.handle_column_list(args, self.svc, self.renderer)

    def test_handle_task_create_defaults(self):
        args = self._args(new_board=None, new_column=None, column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        self.svc.working_board = "alpha"
        result = MagicMock(spec=Task)
        self.svc.create_task.return_value = result

        commands.handle_create(args, self.svc, self.renderer)

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
            None,
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_without_edit_flag_does_not_open_editor(self):
        """create task without --edit does not call svc.edit_task."""
        args = self._args(new_board=None, new_column=None, column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        self.svc.working_board = "alpha"
        result = MagicMock(spec=Task)
        self.svc.create_task.return_value = result

        commands.handle_create(args, self.svc, self.renderer)

        self.svc.edit_task.assert_not_called()
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_edit_flag_opens_editor(self):
        """create task --edit opens the newly created task in the editor."""
        args = self._args(new_board=None, new_column=None, column="todo", title="fix-parser", edit=True, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        self.svc.working_board = "alpha"
        created = Task(id=uuid4(), title="Fix parser", slug="fix-parser", board="alpha", column="todo")
        edited = Task(id=uuid4(), title="Fix parser", slug="fix-parser", board="alpha", column="todo")
        self.svc.create_task.return_value = created
        self.svc.edit_task.return_value = edited

        commands.handle_create(args, self.svc, self.renderer)

        self.svc.edit_task.assert_called_once_with(created.path)
        self.renderer.render_task_create.assert_called_once_with(args, edited)

    def test_handle_task_create_with_optional_fields(self):
        args = self._args(
            new_board=None,
            new_column=None,
            column="todo",
            title="fix-parser",
            assigned_to="philip",
            priority="high",
            tags=["cli", "tests"],
            due_date="2026-06-17",
            created_by="philip",
            edit=False,
            description=None,
        )
        self.svc.working_board = "alpha"
        result = MagicMock(spec=Task)
        self.svc.create_task.return_value = result

        commands.handle_create(args, self.svc, self.renderer)

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
            None,
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_raises_without_active_board(self):
        """create task with no active board raises rather than resolving nonsense."""
        args = self._args(new_board=None, new_column=None, column="todo", title="fix-parser", edit=False, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        self.svc.working_board = None
        with self.assertRaises(ValueError):
            commands.handle_create(args, self.svc, self.renderer)

    def test_handle_task_create_forwards_description(self):
        """`create <column> <title> --description TEXT` forwards description into `TaskCreateParams`."""
        args = self._args(
            new_board=None,
            new_column=None,
            column="todo",
            title="fix-parser",
            edit=False,
            assigned_to=None,
            priority=None,
            tags=None,
            due_date=None,
            created_by=None,
            description="Login is broken",
        )
        self.svc.working_board = "alpha"
        result = MagicMock(spec=Task)
        self.svc.create_task.return_value = result

        commands.handle_create(args, self.svc, self.renderer)

        self.svc.create_task.assert_called_once_with(
            "todo",
            TaskCreateParams(
                title="fix-parser",
                assigned_to=None,
                priority=None,
                tags=[],
                due_date=None,
                created_by=None,
                description="Login is broken",
            ),
            None,
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_view(self):
        args = self._args(path="fix-parser")
        result = object()
        self.svc.get_task.return_value = result

        commands.handle_task_view(args, self.svc, self.renderer)

        self.svc.get_task.assert_called_once_with(Slug("fix-parser"))
        self.renderer.render_task_view.assert_called_once_with(args, result)

    def test_handle_info_task(self):
        args = self._args(path="fix-parser", board=False, column=None, show_path=False, show_id=False)
        result = MagicMock(spec=Task)
        self.svc.get_task.return_value = result

        commands.handle_info(args, self.svc, self.renderer)

        self.svc.get_task.assert_called_once_with(Slug("fix-parser"))
        self.renderer.render_task_info.assert_called_once_with(args, result)

    def test_handle_task_edit(self):
        args = self._args(path="fix-parser")
        result = object()
        self.svc.edit_task.return_value = result

        commands.handle_task_edit(args, self.svc, self.renderer)

        self.svc.edit_task.assert_called_once_with(Slug("fix-parser"))
        self.renderer.render_task_edit.assert_called_once_with(args, result)

    def test_handle_task_update_defaults(self):
        args = self._args(path="fix-parser", assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, column=None, description=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            Slug("fix-parser"),
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
            path="fix-parser",
            assigned_to="philip",
            priority="medium",
            tags=["cli"],
            due_date="2026-07-01",
            created_by="alice",
            column=None,
            description=None,
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            Slug("fix-parser"),
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
        args = self._args(path="fix-parser", column=None, assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.move_task.assert_not_called()
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_update_with_column_moves_task(self):
        """`update --column` moves the updated task to the given column and renders the moved result."""
        args = self._args(path="fix-parser", column="done", assigned_to=None, priority=None, tags=None, due_date=None, created_by=None, description=None)
        updated = MagicMock()
        updated.path = "fix-parser"
        moved = object()
        self.svc.update_task.return_value = updated
        self.svc.move_task.return_value = moved

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with(Path("fix-parser"), Slug("done"))
        self.renderer.render_task_update.assert_called_once_with(args, moved)

    def test_handle_task_update_forwards_description(self):
        """`update --description TEXT` forwards description into `TaskUpdateParams`."""
        args = self._args(
            path="fix-parser",
            assigned_to=None,
            priority=None,
            tags=None,
            due_date=None,
            created_by=None,
            column=None,
            description="New content",
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer)

        self.svc.update_task.assert_called_once_with(
            Slug("fix-parser"),
            updates=TaskUpdateParams(
                title=None,
                assigned_to=None,
                priority=None,
                tags=None,
                due_date=None,
                created_by=None,
                description="New content",
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_unset_defaults(self):
        """`unset` with no flags forwards an empty TaskUnsetParams and renders via render_task_update."""
        args = self._args(path="fix-parser", assigned_to=False, priority=False, tags=None, due_date=False, created_by=False, description=False)
        result = object()
        self.svc.unset_task.return_value = result

        commands.handle_task_unset(args, self.svc, self.renderer)

        self.svc.unset_task.assert_called_once_with(
            Slug("fix-parser"),
            unsets=TaskUnsetParams(
                assigned_to=False,
                priority=False,
                tags=[],
                due_date=False,
                created_by=False,
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_unset_with_flags(self):
        """`unset` translates boolean flags and tag list into TaskUnsetParams and calls unset_task."""
        args = self._args(
            path="fix-parser",
            assigned_to=True,
            priority=False,
            tags=["chore"],
            due_date=True,
            created_by=False,
            description=False,
        )
        result = object()
        self.svc.unset_task.return_value = result

        commands.handle_task_unset(args, self.svc, self.renderer)

        self.svc.unset_task.assert_called_once_with(
            Slug("fix-parser"),
            unsets=TaskUnsetParams(
                assigned_to=True,
                priority=False,
                tags=["chore"],
                due_date=True,
                created_by=False,
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_unset_with_description_flag(self):
        """`unset --description` forwards description=True in TaskUnsetParams."""
        args = self._args(
            path="fix-parser",
            assigned_to=False,
            priority=False,
            tags=None,
            due_date=False,
            created_by=False,
            description=True,
        )
        result = object()
        self.svc.unset_task.return_value = result

        commands.handle_task_unset(args, self.svc, self.renderer)

        self.svc.unset_task.assert_called_once_with(
            Slug("fix-parser"),
            unsets=TaskUnsetParams(
                assigned_to=False,
                priority=False,
                tags=[],
                due_date=False,
                created_by=False,
                description=True,
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_move(self):
        """`move` with a column forwards path and column to move_task and renders via render_task_move."""
        args = self._args(path="fix-parser", column="done")
        result = object()
        self.svc.move_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.move_task.assert_called_once_with(Slug("fix-parser"), Slug("done"))
        self.renderer.render_task_move.assert_called_once_with(args, result)

    def test_handle_task_move_top(self):
        """`move --top` calls reorder_task with "top" and renders via render_task_reorder."""
        args = self._args(path="fix-parser", column=None, top=True, bottom=False, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("fix-parser"), "top")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "top"))

    def test_handle_task_move_bottom(self):
        """`move --bottom` calls reorder_task with "bottom" and renders via render_task_reorder."""
        args = self._args(path="fix-parser", column=None, top=False, bottom=True, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("fix-parser"), "bottom")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "bottom"))

    def test_handle_task_move_up(self):
        """`move --up` calls reorder_task with "up" and renders via render_task_reorder."""
        args = self._args(path="fix-parser", column=None, top=False, bottom=False, up=True, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("fix-parser"), "up")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "up"))

    def test_handle_task_move_down(self):
        """`move --down` calls reorder_task with "down" and renders via render_task_reorder."""
        args = self._args(path="fix-parser", column=None, top=False, bottom=False, up=False, down=True)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer)

        self.svc.reorder_task.assert_called_once_with(Slug("fix-parser"), "down")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "down"))

    def test_handle_task_assign(self):
        """`assign` forwards path and user to assign_task and renders result."""
        args = self._args(path="fix-parser", assigned_to="alice", remove=False)
        result = object()
        self.svc.assign_task.return_value = result

        commands.handle_task_assign(args, self.svc, self.renderer)

        self.svc.assign_task.assert_called_once_with(Slug("fix-parser"), "alice")
        self.svc.unset_task.assert_not_called()
        self.renderer.render_task_assign.assert_called_once_with(args, result)

    def test_handle_task_assign_with_remove_flag(self):
        """`assign --remove` clears the task's assigned_to via unset_task."""
        args = self._args(path="fix-parser", assigned_to=None, remove=True)
        result = object()
        self.svc.unset_task.return_value = result

        commands.handle_task_assign(args, self.svc, self.renderer)

        self.svc.unset_task.assert_called_once_with(Slug("fix-parser"), TaskUnsetParams(assigned_to=True))
        self.svc.assign_task.assert_not_called()
        self.renderer.render_task_assign.assert_called_once_with(args, result)

    def test_handle_task_tag(self):
        """`tag` forwards path and tag to tag_task and renders result."""
        args = self._args(path="fix-parser", tags="auth", remove=False)
        result = object()
        self.svc.tag_task.return_value = result

        commands.handle_task_tag(args, self.svc, self.renderer)

        self.svc.tag_task.assert_called_once_with(Slug("fix-parser"), "auth")
        self.renderer.render_task_tag.assert_called_once_with(args, result)

    def test_handle_task_tag_with_remove_flag(self):
        """`tag --remove` forwards path and tag to untag_task and renders result."""
        args = self._args(path="fix-parser", tags="auth", remove=True)
        result = object()
        self.svc.untag_task.return_value = result

        commands.handle_task_tag(args, self.svc, self.renderer)

        self.svc.untag_task.assert_called_once_with(Slug("fix-parser"), "auth")
        self.svc.tag_task.assert_not_called()
        self.renderer.render_task_tag.assert_called_once_with(args, result)

    def test_handle_task_comment(self):
        """`comment` forwards path and comment to comment_task and renders result."""
        args = self._args(path="fix-parser", comment="Looks good", edit=False)
        result = object()
        self.svc.comment_task.return_value = result

        commands.handle_task_comment(args, self.svc, self.renderer)

        self.svc.comment_task.assert_called_once_with(Slug("fix-parser"), "Looks good")
        self.svc.edit_task.assert_not_called()
        self.renderer.render_task_comment.assert_called_once_with(args, result)

    def test_handle_task_comment_with_edit_flag(self):
        """`comment --edit` opens the task in the editor after appending an empty comment."""
        edit_result = object()
        self.svc.edit_task.return_value = edit_result
        args = self._args(path="fix-parser", comment=None, edit=True)

        commands.handle_task_comment(args, self.svc, self.renderer)

        self.svc.comment_task.assert_called_once_with(Slug("fix-parser"), "")
        self.svc.edit_task.assert_called_once_with(Slug("fix-parser"))
        self.renderer.render_task_comment.assert_called_once_with(args, edit_result)

    def test_handle_search(self):
        args = self._args(
            query="fix",
            board="alpha",
            sort="title",
            reverse=True,
            assigned_to=None,
            priority=None,
            tags=None,
            due_before=None,
            due_after=None,
            created_by=None,
            exclude_columns=None,
            include_archived=False,
        )
        result = object()
        self.svc.search.return_value = result

        commands.handle_search(args, self.svc, self.renderer)

        self.svc.search.assert_called_once_with(
            "fix", filter=TaskFilter(), board="alpha", sort="title", reverse=True
        )
        self.renderer.render_search.assert_called_once_with(args, result)

    def test_handle_search_excludes_named_columns(self):
        """`search -x/--exclude` maps to TaskFilter.exclude_columns."""
        args = self._args(
            query="fix",
            board=None,
            sort=None,
            reverse=False,
            assigned_to=None,
            priority=None,
            tags=None,
            due_before=None,
            due_after=None,
            created_by=None,
            exclude_columns=["archive"],
            include_archived=False,
        )
        self.svc.search.return_value = object()

        commands.handle_search(args, self.svc, self.renderer)

        self.svc.search.assert_called_once_with(
            "fix",
            filter=TaskFilter(exclude_columns=["archive"]),
            board=None,
            sort=None,
            reverse=False,
        )

    def test_handle_log(self):
        args = self._args(path="fix-parser", limit=5)
        result = object()
        self.svc.log.return_value = result

        commands.handle_log(args, self.svc, self.renderer)

        self.svc.log.assert_called_once_with(path=Path("fix-parser"), limit=5)
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

    def test_handle_list_config(self):
        """Bare `config` renders every configuration value."""
        args = self._args()
        result = {"user.name": "Philip"}
        self.svc.list_config.return_value = result

        commands.handle_list_config(args, self.svc, self.renderer)

        self.svc.list_config.assert_called_once_with()
        self.renderer.render_list_config.assert_called_once_with(args, result)

if __name__ == "__main__":
    unittest.main()
