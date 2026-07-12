"""Parser wiring tests for the kanban CLI.

This module documents expected parser structure, arguments, and handler
defaults for top-level and nested subcommands.
"""

from __future__ import annotations

import unittest

from kanban.cli import parser as cli_parser
from kanban.cli.commands import (
    handle_board_create,
    handle_board_delete,
    handle_board_list,
    handle_board_rename,
    handle_column_create,
    handle_column_delete,
    handle_column_list,
    handle_column_rename,
    handle_column_reorder,
    handle_config_get,
    handle_config_set,
    handle_init,
    handle_log,
    handle_repl,
    handle_search,
    handle_status,
    handle_task_create,
    handle_task_delete,
    handle_task_edit,
    handle_task_list,
    handle_task_assign,
    handle_task_move,
    handle_task_rename,
    handle_task_show,
    handle_task_update
)

class TestParserStructure(unittest.TestCase):
    """Tests that subparser trees and command groups are registered."""

    def _subparser_choices(self, parser, action_dest: str):
        for action in parser._actions:
            if isinstance(action, cli_parser.argparse._SubParsersAction) and action.dest == action_dest:
                return action.choices
        self.fail(f"Subparser action with dest={action_dest!r} not found")

    def test_top_level_subcommands_exist(self):
        """Top-level command names are registered on the root parser."""
        parser = cli_parser.build_parser()
        top = self._subparser_choices(parser, "command")
        self.assertEqual(
            set(top.keys()),
            {"init", "board", "column", "task", "tasks", "search", "log", "status", "config", "repl"},
        )

    def test_top_level_subcommands_do_not_include_cd(self):
        """Optional `cd` command is available only when explicitly enabled."""
        parser = cli_parser.build_parser()
        top = self._subparser_choices(parser, "command")
        self.assertNotIn("cd", set(top.keys()))

    def test_nested_subcommands_exist(self):
        """Nested command groups expose expected child subcommands."""
        parser = cli_parser.build_parser()
        top = self._subparser_choices(parser, "command")

        board = self._subparser_choices(top["board"], "board_command")
        self.assertEqual(set(board.keys()), {"list", "create", "rename", "delete"})

        column = self._subparser_choices(top["column"], "column_command")
        self.assertEqual(set(column.keys()), {"list", "create", "rename", "reorder", "delete"})

        task = self._subparser_choices(top["task"], "task_command")
        self.assertEqual(set(task.keys()), {"list", "create", "show", "edit", "update", "move", "delete", "assign", "rename"})

        config = self._subparser_choices(top["config"], "config_command")
        self.assertEqual(set(config.keys()), {"get", "set"})


class TestParserArgumentsAndDefaults(unittest.TestCase):
    """Tests that parsed arguments and default handlers are correct."""

    def test_init_defaults(self):
        """`init` parses with expected defaults and dispatch handler."""
        args = cli_parser.parse_args(["init"])
        self.assertEqual(args.command, "init")
        self.assertFalse(args.quiet)
        self.assertFalse(args.verbose)
        self.assertIs(args.func, handle_init)

    def test_board_commands(self):
        """Board subcommands parse arguments and bind the correct handlers."""
        args = cli_parser.parse_args(["board", "list"])
        self.assertEqual(args.command, "board")
        self.assertEqual(args.board_command, "list")
        self.assertEqual(args.format, "plain")
        self.assertIs(args.func, handle_board_list)

        args = cli_parser.parse_args(["board", "create", "my-board"])
        self.assertEqual(args.board, "my-board")
        self.assertIs(args.func, handle_board_create)

        args = cli_parser.parse_args(["board", "rename", "old", "new"])
        self.assertEqual(args.board, "old")
        self.assertEqual(args.new_name, "new")
        self.assertIs(args.func, handle_board_rename)

        args = cli_parser.parse_args(["board", "delete", "my-board"])
        self.assertEqual(args.board, "my-board")
        self.assertIs(args.func, handle_board_delete)

    def test_column_commands(self):
        """Column subcommands parse arguments and bind the correct handlers."""
        args = cli_parser.parse_args(["column", "list", "board-a"])
        self.assertEqual(args.board, "board-a")
        self.assertEqual(args.format, "plain")
        self.assertIs(args.func, handle_column_list)

        args = cli_parser.parse_args(["column", "list", "board-a"])

        args = cli_parser.parse_args(["column", "create", "board-a/todo"])
        self.assertEqual(args.path, "board-a/todo")
        self.assertIs(args.func, handle_column_create)

        args = cli_parser.parse_args(["column", "rename", "board-a/todo", "doing"])
        self.assertEqual(args.path, "board-a/todo")
        self.assertEqual(args.new_name, "doing")
        self.assertIs(args.func, handle_column_rename)

        args = cli_parser.parse_args(["column", "reorder", "board-a/todo", "2"])
        self.assertEqual(args.path, "board-a/todo")
        self.assertEqual(args.position, 2)
        self.assertIs(args.func, handle_column_reorder)

        args = cli_parser.parse_args(["column", "delete", "board-a/todo"])
        self.assertEqual(args.path, "board-a/todo")
        self.assertIs(args.func, handle_column_delete)

    def test_task_commands(self):
        """Task subcommands parse flags/paths and bind the correct handlers."""
        args = cli_parser.parse_args([
            "task",
            "list",
            "board-a/todo",
            "--assigned-to",
            "philip",
            "--priority",
            "high",
            "--tag",
            "bug",
            "--tag",
            "urgent",
            "--sort",
            "created-at",
            "--reverse",
        ])
        self.assertEqual(args.path, "board-a/todo")
        self.assertEqual(args.assigned_to, "philip")
        self.assertEqual(args.priority, "high")
        self.assertEqual(args.tags, ["bug", "urgent"])
        self.assertEqual(args.sort, "created-at")
        self.assertTrue(args.reverse)
        self.assertIs(args.func, handle_task_list)

        args = cli_parser.parse_args(["task", "list", "board-a/todo"])

        args = cli_parser.parse_args([
            "task",
            "create",
            "board-a/todo/fix-parser",
            "--assigned-to",
            "philip",
            "--priority",
            "medium",
            "--tag",
            "cli",
            "--due-date",
            "2026-06-15",
            "--created-by",
            "philip",
        ])
        self.assertEqual(args.path, "board-a/todo/fix-parser")
        self.assertEqual(args.assigned_to, "philip")
        self.assertEqual(args.priority, "medium")
        self.assertEqual(args.tags, ["cli"])
        self.assertEqual(args.due_date, "2026-06-15")
        self.assertEqual(args.created_by, "philip")
        self.assertIs(args.func, handle_task_create)

        args = cli_parser.parse_args(["task", "show", "board-a/todo/fix-parser", "--format", "json"])
        self.assertEqual(args.format, "json")
        self.assertIs(args.func, handle_task_show)

        args = cli_parser.parse_args(["task", "edit", "board-a/todo/fix-parser"])
        self.assertIs(args.func, handle_task_edit)

        args = cli_parser.parse_args([
            "task",
            "update",
            "board-a/todo/fix-parser",
            "--assigned-to",
            "philip",
            "--priority",
            "medium",
            "--tag",
            "cli",
            "--due-date",
            "2026-06-16",
            "--created-by",
            "philip",
        ])
        self.assertEqual(args.path, "board-a/todo/fix-parser")
        self.assertEqual(args.assigned_to, "philip")
        self.assertEqual(args.priority, "medium")
        self.assertEqual(args.tags, ["cli"])
        self.assertEqual(args.due_date, "2026-06-16")
        self.assertEqual(args.created_by, "philip")
        self.assertIs(args.func, handle_task_update)

        args = cli_parser.parse_args(["tasks", "update", "board-a/todo/fix-parser"])
        self.assertEqual(args.command, "tasks")
        self.assertIs(args.func, handle_task_update)

        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "done"])
        self.assertEqual(args.column, "done")
        self.assertIs(args.func, handle_task_move)

        args = cli_parser.parse_args(["task", "delete", "board-a/todo/fix-parser"])
        self.assertIs(args.func, handle_task_delete)

        args = cli_parser.parse_args(["task", "assign", "board-a/todo/fix-parser", "alice"])
        self.assertEqual(args.path, "board-a/todo/fix-parser")
        self.assertEqual(args.assigned_to, "alice")
        self.assertEqual(args.format, "plain")
        self.assertIs(args.func, handle_task_assign)

    def test_search_log_status_and_config(self):
        """Other top-level commands parse correctly and set proper handlers."""
        args = cli_parser.parse_args(["search", "query", "--board", "board-a", "--sort", "title"])
        self.assertEqual(args.query, "query")
        self.assertEqual(args.board, "board-a")
        self.assertEqual(args.sort, "title")
        self.assertIs(args.func, handle_search)

        args = cli_parser.parse_args(["log", "board-a/todo/task-1", "--limit", "5"])
        self.assertEqual(args.path, "board-a/todo/task-1")
        self.assertEqual(args.limit, 5)
        self.assertIs(args.func, handle_log)

        args = cli_parser.parse_args(["status", "--format", "plain"])
        self.assertEqual(args.format, "plain")
        self.assertIs(args.func, handle_status)

        args = cli_parser.parse_args(["config", "set", "name", "Philip"])
        self.assertEqual(args.key, "name")
        self.assertEqual(args.value, "Philip")
        self.assertIs(args.func, handle_config_set)

        args = cli_parser.parse_args(["config", "get", "name"])
        self.assertEqual(args.key, "name")
        self.assertIs(args.func, handle_config_get)


    def test_task_rename_path_new_name_and_handler(self) -> None:
        """task rename binds path, new_name, and the handle_task_rename handler."""
        args = cli_parser.parse_args(["task", "rename", "board-a/todo/fix-parser", "Fixed Parser"])
        self.assertEqual(args.path, "board-a/todo/fix-parser")
        self.assertEqual(args.new_name, "Fixed Parser")
        self.assertIs(args.func, handle_task_rename)

    def test_task_rename_format_default(self) -> None:
        """task rename defaults to plain format."""
        args = cli_parser.parse_args(["task", "rename", "board-a/todo/fix-parser", "Fixed Parser"])
        self.assertEqual(args.format, "plain")

    def test_task_rename_format_json(self) -> None:
        """task rename accepts --format json."""
        args = cli_parser.parse_args(["task", "rename", "board-a/todo/fix-parser", "Fixed Parser", "--format", "json"])
        self.assertEqual(args.format, "json")

    def test_task_move_path_and_handler(self) -> None:
        """task move binds path and the handle_task_move handler."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "done"])
        self.assertEqual(args.path, "board-a/todo/fix-parser")
        self.assertIs(args.func, handle_task_move)

    def test_task_move_column_arg(self) -> None:
        """task move with a positional column sets column and leaves flags False."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "done"])
        self.assertEqual(args.column, "done")
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_task_move_top_flag(self) -> None:
        """task move --top sets top=True and leaves other flags False and column None."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--top"])
        self.assertTrue(args.top)
        self.assertIsNone(args.column)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_task_move_bottom_flag(self) -> None:
        """task move --bottom sets bottom=True and leaves other flags False and column None."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--bottom"])
        self.assertTrue(args.bottom)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_task_move_up_flag(self) -> None:
        """task move --up sets up=True and leaves other flags False and column None."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--up"])
        self.assertTrue(args.up)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.down)

    def test_task_move_down_flag(self) -> None:
        """task move --down sets down=True and leaves other flags False and column None."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--down"])
        self.assertTrue(args.down)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)

    def test_task_move_no_destination_defaults(self) -> None:
        """task move with only a path sets column=None and all flags False."""
        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser"])
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_task_move_mutual_exclusion(self) -> None:
        """task move rejects more than one destination argument at once."""
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--top", "--bottom"])
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "--up", "--down"])

    def test_repl_defaults(self):
        """`repl` defaults --no-rich to False and binds handle_repl."""
        args = cli_parser.parse_args(["repl"])
        self.assertEqual(args.command, "repl")
        self.assertFalse(args.no_rich)
        self.assertIs(args.func, handle_repl)

    def test_repl_no_rich_flag(self):
        """`repl --no-rich` sets no_rich to True."""
        args = cli_parser.parse_args(["repl", "--no-rich"])
        self.assertTrue(args.no_rich)

    def test_required_subparsers_raise(self):
        """Missing required subcommands trigger parser exit errors."""
        with self.assertRaises(SystemExit):
            cli_parser.parse_args([])
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["board"])
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["column"])
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["task"])
        with self.assertRaises(SystemExit):
            cli_parser.parse_args(["config"])

if __name__ == "__main__":
    unittest.main()
