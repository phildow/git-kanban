"""Tests for CLI subcommand handler dispatch.

Handlers are validated with mocked service/renderer collaborators to document
the expected method calls and argument mapping.
"""

from __future__ import annotations

import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from kanban.cli import commands
from kanban.models import Slug
from kanban.storage.seeds import BOOTSTRAP_CONFIG
from kanban.services.kanban import TaskCreateParams, TaskUpdateParams

# Note that tests also check that board/column/[task] paths are re-written to /board/column/[task]

class TestCommandHandlers(unittest.TestCase):
    """Dispatch contract tests for CLI command handlers."""

    def setUp(self) -> None:
        self.svc = MagicMock()
        self.renderer = MagicMock()
        self.json_renderer = MagicMock()
        self.repl_renderer = MagicMock()

    def _args(self, **kwargs) -> Namespace:
        return Namespace(format="plain", **kwargs)

    def test_handle_init_without_bootstrap(self):
        """`init` without --bootstrap calls initialize_kanban with config=None."""
        args = self._args(bootstrap=False)
        result = object()
        self.svc.initialize_kanban.return_value = result

        commands.handle_init(args, self.svc, self.renderer, self.json_renderer)

        self.svc.initialize_kanban.assert_called_once_with(config=None)
        self.renderer.render_init.assert_called_once_with(args, result)

    def test_handle_init_with_bootstrap(self):
        """`init --bootstrap` calls initialize_kanban with BOOTSTRAP_CONFIG."""
        args = self._args(bootstrap=True)
        result = object()
        self.svc.initialize_kanban.return_value = result

        commands.handle_init(args, self.svc, self.renderer, self.json_renderer)

        self.svc.initialize_kanban.assert_called_once_with(config=BOOTSTRAP_CONFIG)
        self.renderer.render_init.assert_called_once_with(args, result)

    def test_handle_board_list(self):
        """`board list` renders list output."""
        args = self._args(sort="title", reverse=True)
        result = object()
        self.svc.get_boards.return_value = result

        commands.handle_board_list(args, self.svc, self.renderer, self.json_renderer)

        self.svc.get_boards.assert_called_once_with()
        self.renderer.render_board_list.assert_called_once_with(args, result)

    def test_handle_board_create(self):
        """`board create` forwards board name and renders created board."""
        args = self._args(board="my-board")
        result = object()
        self.svc.create_board.return_value = result

        commands.handle_board_create(args, self.svc, self.renderer, self.json_renderer)

        self.svc.create_board.assert_called_once_with("my-board")
        self.renderer.render_board_create.assert_called_once_with(args, result)

    def test_handle_board_info(self):
        """`board info` fetches board details and renders result."""
        args = self._args(path="my-board")
        result = object()
        self.svc.get_board.return_value = result

        commands.handle_board_info(args, self.svc, self.renderer, self.json_renderer)

        self.svc.get_board.assert_called_once_with("my-board")
        self.renderer.render_board_info.assert_called_once_with(args, result)

    def test_handle_board_rename(self):
        """`board rename` forwards old/new board names and renders result."""
        args = self._args(path="old", new_name="new")
        result = object()
        self.svc.rename_board.return_value = result

        commands.handle_board_rename(args, self.svc, self.renderer, self.json_renderer)

        self.svc.rename_board.assert_called_once_with(Path("/old"), "new")
        self.renderer.render_board_rename.assert_called_once_with(args, result)

    def test_handle_board_delete(self):
        """`board delete` forwards board name and renders deletion result."""
        args = self._args(path="my-board", force=True)
        result = object()
        self.svc.delete_board.return_value = result

        commands.handle_board_delete(args, self.svc, self.renderer, self.json_renderer)

        self.svc.delete_board.assert_called_once_with(Path("/my-board"))
        self.renderer.render_board_delete.assert_called_once_with(args, result)

    def test_column_handlers(self):
        """Column handlers parse path arguments and dispatch correctly."""
        args = self._args(path="board-a", sort="title", reverse=False)
        result = object()
        self.svc.get_columns.return_value = result
        commands.handle_column_list(args, self.svc, self.renderer, self.json_renderer)
        self.svc.get_columns.assert_called_once_with(Path("/board-a"))
        self.renderer.render_column_list.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo")
        result = object()
        self.svc.get_column.return_value = result
        commands.handle_column_info(args, self.svc, self.renderer, self.json_renderer)
        self.svc.get_column.assert_called_once_with(Path("/board-a/todo"))
        self.renderer.render_column_info.assert_called_once_with(args, result)

        args = self._args(path="board-a", title="todo")
        result = object()
        self.svc.create_column.return_value = result
        commands.handle_column_create(args, self.svc, self.renderer, self.json_renderer)
        self.svc.create_column.assert_called_once_with(Path("/board-a"), "todo")
        self.renderer.render_column_create.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", new_name="doing")
        result = object()
        self.svc.rename_column.return_value = result
        commands.handle_column_rename(args, self.svc, self.renderer, self.json_renderer)
        self.svc.rename_column.assert_called_once_with(Path("/board-a/todo"), "doing")
        self.renderer.render_column_rename.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", position=2)
        result = object()
        self.svc.reorder_column.return_value = result
        commands.handle_column_reorder(args, self.svc, self.renderer, self.json_renderer)
        self.svc.reorder_column.assert_called_once_with(Path("/board-a/todo"), 2)
        self.renderer.render_column_reorder.assert_called_once_with(args, result)

        args = self._args(path="board-a/todo", force=True)
        result = object()
        self.svc.delete_column.return_value = result
        commands.handle_column_delete(args, self.svc, self.renderer, self.json_renderer)
        self.svc.delete_column.assert_called_once_with(Path("/board-a/todo"))
        self.renderer.render_column_delete.assert_called_once_with(args, result)

    def test_handle_task_list(self):
        """`task list` handler forwards path/sort options and renders output."""
        args = self._args(path="board-a/todo", sort="title", reverse=True, priority=None, assigned_to=None, tags=None, due_before=None, due_after=None, created_by=None, column=None)
        result = object()
        self.svc.get_tasks.return_value = result

        commands.handle_task_list(args, self.svc, self.renderer, self.json_renderer)

        from kanban.models import TaskFilter
        self.svc.get_tasks.assert_called_once_with(Path("/board-a/todo"), filter=TaskFilter(), sort="title", reverse=True)
        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_task_list_with_exclude_columns(self):
        """`task list -x/--exclude` maps to TaskFilter.exclude_columns."""
        args = self._args(path="board-a/todo", sort=None, reverse=False, priority=None, assigned_to=None, tags=None, due_before=None, due_after=None, created_by=None, column=["done", "archive"])
        result = object()
        self.svc.get_tasks.return_value = result

        commands.handle_task_list(args, self.svc, self.renderer, self.json_renderer)

        from kanban.models import TaskFilter
        self.svc.get_tasks.assert_called_once_with(
            Path("/board-a/todo"),
            filter=TaskFilter(exclude_columns=["done", "archive"]),
            sort=None,
            reverse=False,
        )
        self.renderer.render_task_list.assert_called_once_with(args, result)

    def test_handle_task_create_with_all_optional_fields(self):
        """`task create` maps all optional CLI fields into `TaskCreateParams`."""
        args = self._args(
            path="board-a/todo",
            title="fix-parser",
            assigned_to="philip",
            priority="high",
            tags=["cli", "tests"],
            due_date="2026-06-15",
            created_by="philip",
        )
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer, self.json_renderer)

        self.svc.create_task.assert_called_once_with(
            Path("/board-a/todo"),
            TaskCreateParams(
                title="fix-parser",
                assigned_to="philip",
                priority="high",
                tags=["cli", "tests"],
                due_date="2026-06-15",
                created_by="philip",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_create_with_default_optional_fields(self):
        """`task create` defaults missing optional fields and normalizes `tags` to empty list."""
        args = self._args(path="board-a/todo", title="check-no-other-args", priority=None, tags=None, assigned_to=None, due_date=None, created_by=None)
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer, self.json_renderer)

        self.svc.create_task.assert_called_once_with(
            Path("/board-a/todo"),
            TaskCreateParams(
                title="check-no-other-args",
                assigned_to=None,
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
            path="board-a/todo",
            title="check-tags-none",
            assigned_to="alex",
            priority=None,
            tags=None,
            due_date=None,
            created_by="alex",
        )
        result = object()
        self.svc.create_task.return_value = result

        commands.handle_task_create(args, self.svc, self.renderer, self.json_renderer)

        self.svc.create_task.assert_called_once_with(
            Path("/board-a/todo"),
            TaskCreateParams(
                title="check-tags-none",
                assigned_to="alex",
                priority=None,
                tags=[],
                due_date=None,
                created_by="alex",
            ),
        )
        self.renderer.render_task_create.assert_called_once_with(args, result)

    def test_handle_task_show(self):
        """`task info` fetches a task by path and forwards it to renderer."""
        args = self._args(path="board-a/todo/fix-parser")
        result = object()
        self.svc.get_task.return_value = result

        commands.handle_task_show(args, self.svc, self.renderer, self.json_renderer)

        self.svc.get_task.assert_called_once_with(Path("/board-a/todo/fix-parser"))
        self.renderer.render_task_show.assert_called_once_with(args, result)

    def test_handle_task_update_with_default_optional_fields(self):
        """`task update` defaults unspecified update fields to `None`."""
        args = self._args(path="/board-a/todo/fix-parser", priority=None, title=None, assigned_to=None, tags=None, due_date=None, created_by=None, column=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer, self.json_renderer)

        self.svc.update_task.assert_called_once_with(
            Path("/board-a/todo/fix-parser"),
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

    def test_handle_task_update_with_all_optional_fields(self):
        """`task update` maps all provided update fields into `TaskUpdateParams`."""
        args = self._args(
            path="board-a/todo/fix-parser",
            assigned_to="philip",
            priority="medium",
            tags=["cli", "refactor"],
            due_date="2026-07-01",
            created_by="mark",
            column=None,
        )
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer, self.json_renderer)

        self.svc.update_task.assert_called_once_with(
            Path("/board-a/todo/fix-parser"),
            updates=TaskUpdateParams(
                assigned_to="philip",
                priority="medium",
                tags=["cli", "refactor"],
                due_date="2026-07-01",
                created_by="mark",
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_update_with_column_moves_after_update(self):
        """`task update --column` updates first, then moves using the updated task path."""
        args = self._args(
            path="board-a/todo/fix-parser",
            assigned_to="philip",
            priority="medium",
            tags=["cli", "refactor"],
            due_date="2026-07-01",
            created_by="mark",
            column="done",
        )
        updated = SimpleNamespace(path="/board-a/todo/fix-parser")
        moved = object()
        self.svc.update_task.return_value = updated
        self.svc.move_task.return_value = moved

        commands.handle_task_update(args, self.svc, self.renderer, self.json_renderer)

        self.svc.update_task.assert_called_once_with(
            Path("/board-a/todo/fix-parser"),
            updates=TaskUpdateParams(
                assigned_to="philip",
                priority="medium",
                tags=["cli", "refactor"],
                due_date="2026-07-01",
                created_by="mark",
            ),
        )
        self.svc.move_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), Slug("done"))
        self.renderer.render_task_update.assert_called_once_with(args, moved)

    def test_handle_task_update_with_explicit_empty_tags(self):
        """`task edit` preserves an explicit empty tags list."""
        args = self._args(path="board-a/todo/fix-parser", tags=[], priority=None, title=None, assigned_to=None, due_date=None, created_by=None, column=None)
        result = object()
        self.svc.update_task.return_value = result

        commands.handle_task_update(args, self.svc, self.renderer, self.json_renderer)

        self.svc.update_task.assert_called_once_with(
            Path("/board-a/todo/fix-parser"),
            updates=TaskUpdateParams(
                title=None,
                assigned_to=None,
                priority=None,
                tags=[],
                due_date=None,
                created_by=None,
            ),
        )
        self.renderer.render_task_update.assert_called_once_with(args, result)

    def test_handle_task_rename(self):
        """`task rename` forwards path and new name to rename_task and renders result."""
        args = self._args(path="board-a/todo/fix-parser", new_name="Fixed Parser")
        result = object()
        self.svc.rename_task.return_value = result

        commands.handle_task_rename(args, self.svc, self.renderer, self.json_renderer)

        self.svc.rename_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), "Fixed Parser")
        self.renderer.render_task_rename.assert_called_once_with(args, result)

    def test_handle_task_move(self):
        """`task move` forwards the task path and destination column name."""
        args = self._args(path="board-a/todo/fix-parser", column="done")
        result = object()
        self.svc.move_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer, self.json_renderer)

        self.svc.move_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), Slug("done"))
        self.renderer.render_task_move.assert_called_once_with(args, result)

    def test_handle_task_move_top(self):
        """`task move --top` calls reorder_task with "top" and renders via render_task_reorder."""
        args = self._args(path="board-a/todo/fix-parser", column=None, top=True, bottom=False, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer, self.json_renderer)

        self.svc.reorder_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), "top")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "top"))

    def test_handle_task_move_bottom(self):
        """`task move --bottom` calls reorder_task with "bottom" and renders via render_task_reorder."""
        args = self._args(path="board-a/todo/fix-parser", column=None, top=False, bottom=True, up=False, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer, self.json_renderer)

        self.svc.reorder_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), "bottom")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "bottom"))

    def test_handle_task_move_up(self):
        """`task move --up` calls reorder_task with "up" and renders via render_task_reorder."""
        args = self._args(path="board-a/todo/fix-parser", column=None, top=False, bottom=False, up=True, down=False)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer, self.json_renderer)

        self.svc.reorder_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), "up")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "up"))

    def test_handle_task_move_down(self):
        """`task move --down` calls reorder_task with "down" and renders via render_task_reorder."""
        args = self._args(path="board-a/todo/fix-parser", column=None, top=False, bottom=False, up=False, down=True)
        result = object()
        self.svc.reorder_task.return_value = result

        commands.handle_task_move(args, self.svc, self.renderer, self.json_renderer)

        self.svc.reorder_task.assert_called_once_with(Path("/board-a/todo/fix-parser"), "down")
        self.renderer.render_task_reorder.assert_called_once_with(args, (result, "down"))

    def test_handle_task_assign(self):
        """`task assign` forwards path and user to assign_task and renders result."""
        args = self._args(path="board-a/todo/fix-parser", assigned_to="alice")
        result = object()
        self.svc.assign_task.return_value = result

        commands.handle_task_assign(args, self.svc, self.renderer, self.json_renderer)

        self.svc.assign_task.assert_called_once_with("/board-a/todo/fix-parser", "alice")
        self.renderer.render_task_assign.assert_called_once_with(args, result)

    def test_handle_task_delete(self):
        """`task delete` forwards task path and renders deletion result."""
        args = self._args(path="board-a/todo/fix-parser", force=True)
        result = object()
        self.svc.delete_task.return_value = result

        commands.handle_task_delete(args, self.svc, self.renderer, self.json_renderer)

        self.svc.delete_task.assert_called_once_with("/board-a/todo/fix-parser")
        self.renderer.render_task_delete.assert_called_once_with(args, result)

    def test_search_handler(self):
        """`search` handler forwards query and filter/sort options to service."""
        args = self._args(query="query", board="board-a", sort="title", reverse=False)
        result = object()
        self.svc.search.return_value = result

        commands.handle_search(args, self.svc, self.renderer, self.json_renderer)

        self.svc.search.assert_called_once_with("query", board="board-a", sort="title", reverse=False)
        self.renderer.render_search.assert_called_once_with(args, result)

    def test_log_handler(self):
        """`log` handler calls `svc.log` and renders the resulting output."""
        args = self._args(path="board-a/todo/task-1", limit=5)
        result = object()
        self.svc.log.return_value = result

        commands.handle_log(args, self.svc, self.renderer, self.json_renderer)

        self.svc.log.assert_called_once_with(path="/board-a/todo/task-1", limit=5)
        self.renderer.render_log.assert_called_once_with(args, result)

    def test_status_handler(self):
        """`status` handler renders result."""
        args = self._args()
        result = object()
        self.svc.status.return_value = result

        commands.handle_status(args, self.svc, self.renderer, self.json_renderer)

        self.svc.status.assert_called_once()
        self.renderer.render_status.assert_called_once_with(args, result)

    def test_config_handlers(self):
        """Config set/get handlers call their matching service operations."""
        args = self._args(key="name", value="Philip")
        result = object()
        self.svc.set_config.return_value = result
        commands.handle_set_config(args, self.svc, self.renderer, self.json_renderer)
        self.svc.set_config.assert_called_once_with("name", "Philip")
        self.renderer.render_set_config.assert_called_once_with(args, result)

        args = self._args(key="name")
        result = object()
        self.svc.get_config.return_value = result
        commands.handle_get_config(args, self.svc, self.renderer, self.json_renderer)
        self.svc.get_config.assert_called_once_with("name")
        self.renderer.render_get_config.assert_called_once_with(args, result)

    @patch("kanban.repl.render_helper.RenderHelper")
    @patch("kanban.repl.renderer.Renderer")
    @patch("kanban.repl.rich_renderer.RichRenderer")
    @patch("kanban.repl.run_repl")
    def test_handle_repl_with_no_rich_uses_plain_renderer(
        self, run_repl, rich_renderer_cls, renderer_cls, render_helper_cls
    ):
        """`repl --no-rich` starts the plain-text REPL renderer."""
        args = self._args(no_rich=True)

        commands.handle_repl(args, self.svc, self.renderer, self.json_renderer)

        render_helper_cls.assert_called_once_with(service=self.svc)
        renderer_cls.assert_called_once_with(render_helper=render_helper_cls.return_value)
        rich_renderer_cls.assert_not_called()
        run_repl.assert_called_once_with(svc=self.svc, renderer=renderer_cls.return_value)

    @patch("kanban.repl.render_helper.RenderHelper")
    @patch("kanban.repl.renderer.Renderer")
    @patch("kanban.repl.rich_renderer.RichRenderer")
    @patch("kanban.repl.run_repl")
    def test_handle_repl_defaults_to_rich_renderer(
        self, run_repl, rich_renderer_cls, renderer_cls, render_helper_cls
    ):
        """`repl` without --no-rich starts the REPL with the rich-text renderer by default."""
        args = self._args(no_rich=False)

        commands.handle_repl(args, self.svc, self.renderer, self.json_renderer)

        render_helper_cls.assert_called_once_with(service=self.svc)
        rich_renderer_cls.assert_called_once_with(render_helper=render_helper_cls.return_value)
        renderer_cls.assert_not_called()
        run_repl.assert_called_once_with(svc=self.svc, renderer=rich_renderer_cls.return_value)


if __name__ == "__main__":
    unittest.main()
