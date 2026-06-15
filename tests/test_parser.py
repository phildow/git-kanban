"""Parser wiring tests for the kanban CLI.

This module documents expected parser structure, arguments, and handler
defaults for top-level and nested subcommands.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# This project imports CLI modules as top-level "cli.*" from inside the
# package directory. Add /kanban to sys.path so tests can import the same way.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
KANBAN_SRC = PROJECT_ROOT / "kanban"
if str(KANBAN_SRC) not in sys.path:
    sys.path.insert(0, str(KANBAN_SRC))

from cli import noun_first_parser as cli_parser
from cli import verb_first_parser as verb_first_cli_parser
from cli.commands import (
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
    handle_task_move,
    handle_task_show,
    handle_use,
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
            {"init", "board", "column", "task", "search", "log", "status", "config", "repl"},
        )

    def test_top_level_subcommands_include_use_when_enabled(self):
        """Optional `use` command is available only when explicitly enabled."""
        parser = cli_parser.build_parser(enable_use=True)
        top = self._subparser_choices(parser, "command")
        self.assertIn("use", set(top.keys()))

    def test_nested_subcommands_exist(self):
        """Nested command groups expose expected child subcommands."""
        parser = cli_parser.build_parser()
        top = self._subparser_choices(parser, "command")

        board = self._subparser_choices(top["board"], "board_command")
        self.assertEqual(set(board.keys()), {"list", "create", "rename", "delete"})

        column = self._subparser_choices(top["column"], "column_command")
        self.assertEqual(set(column.keys()), {"list", "create", "rename", "reorder", "delete"})

        task = self._subparser_choices(top["task"], "task_command")
        self.assertEqual(set(task.keys()), {"list", "create", "show", "edit", "move", "delete"})

        config = self._subparser_choices(top["config"], "config_command")
        self.assertEqual(set(config.keys()), {"set", "get"})


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
        args = cli_parser.parse_args(["board", "list", "--sort", "title", "--reverse"])
        self.assertEqual(args.command, "board")
        self.assertEqual(args.board_command, "list")
        self.assertEqual(args.sort, "title")
        self.assertTrue(args.reverse)
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

    def test_use_command_available_when_enabled(self):
        """`use` parses only on parser instances that enable it."""
        parser = cli_parser.build_parser(enable_use=True)

        args = parser.parse_args(["use"])
        self.assertEqual(args.command, "use")
        self.assertIsNone(args.path)
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["use", "board-a/todo"])
        self.assertEqual(args.command, "use")
        self.assertEqual(args.path, "board-a/todo")
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["use", "--clear"])
        self.assertTrue(args.clear)
        self.assertIsNone(args.path)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["cd", "board-a/todo"])
        self.assertEqual(args.command, "cd")
        self.assertEqual(args.path, "board-a/todo")
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["cd", "--clear"])
        self.assertTrue(args.clear)
        self.assertIsNone(args.path)
        self.assertIs(args.func, handle_use)

    def test_column_commands(self):
        """Column subcommands parse arguments and bind the correct handlers."""
        args = cli_parser.parse_args(["column", "list", "board-a"])
        self.assertEqual(args.board, "board-a")
        self.assertEqual(args.format, "plain")
        self.assertEqual(args.sort, None)
        self.assertFalse(args.reverse)
        self.assertIs(args.func, handle_column_list)

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
            "--assignee",
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
        self.assertEqual(args.assignee, "philip")
        self.assertEqual(args.priority, "high")
        self.assertEqual(args.tags, ["bug", "urgent"])
        self.assertEqual(args.sort, "created-at")
        self.assertTrue(args.reverse)
        self.assertIs(args.func, handle_task_list)

        args = cli_parser.parse_args([
            "task",
            "create",
            "board-a/todo/fix-parser",
            "--assignee",
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
        self.assertEqual(args.assignee, "philip")
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

        args = cli_parser.parse_args(["task", "move", "board-a/todo/fix-parser", "board-a/done"])
        self.assertEqual(args.dest, "board-a/done")
        self.assertIs(args.func, handle_task_move)

        args = cli_parser.parse_args(["task", "delete", "board-a/todo/fix-parser"])
        self.assertIs(args.func, handle_task_delete)

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

        args = cli_parser.parse_args(["repl"])
        self.assertEqual(args.command, "repl")
        self.assertFalse(args.noun_first)
        self.assertIs(args.func, handle_repl)

        args = cli_parser.parse_args(["repl", "--noun-first"])
        self.assertTrue(args.noun_first)
        self.assertIs(args.func, handle_repl)

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


class TestVerbFirstParserAliases(unittest.TestCase):
    """Tests for verb-first parser aliases and wiring."""

    def test_list_plural_aliases_map_to_same_handlers(self):
        args = verb_first_cli_parser.parse_args(["list", "boards"])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.list_subject, "boards")
        self.assertIs(args.func, handle_board_list)

        args = verb_first_cli_parser.parse_args(["list", "columns", "main"])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.list_subject, "columns")
        self.assertEqual(args.board, "main")
        self.assertIs(args.func, handle_column_list)

        args = verb_first_cli_parser.parse_args(["list", "tasks", "main/todo"])
        self.assertEqual(args.command, "list")
        self.assertEqual(args.list_subject, "tasks")
        self.assertEqual(args.path, "main/todo")
        self.assertIs(args.func, handle_task_list)

        args = verb_first_cli_parser.parse_args(["ls", "board"])
        self.assertEqual(args.command, "ls")
        self.assertEqual(args.list_subject, "board")
        self.assertIs(args.func, handle_board_list)

    def test_cd_alias_maps_to_use_handler(self):
        parser = verb_first_cli_parser.build_parser(enable_use=True)

        args = parser.parse_args(["cd"])
        self.assertEqual(args.command, "cd")
        self.assertIsNone(args.path)
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["cd", "main/todo"])
        self.assertEqual(args.command, "cd")
        self.assertEqual(args.path, "main/todo")
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_use)

        args = parser.parse_args(["cd", "--clear"])
        self.assertTrue(args.clear)
        self.assertIsNone(args.path)
        self.assertIs(args.func, handle_use)


if __name__ == "__main__":
    unittest.main()
