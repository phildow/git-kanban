"""Parser wiring tests for the kanban REPL.

This module documents expected parser structure, arguments, and handler
defaults for top-level and nested subcommands.
"""

from __future__ import annotations

import unittest

# TODO: add handle_list tests
from kanban.repl import parser as repl_parser
from kanban.repl.commands import (
    handle_board_change,
    handle_board_create,
    handle_column_change,
    handle_column_create,
    handle_list,
    handle_change_dir,
    handle_rename,
    handle_task_assign,
    handle_task_create,
    handle_task_move,
    handle_task_update,
)

class TestParserAliases(unittest.TestCase):
    """Tests for verb-first parser aliases and wiring."""

    def test_board_command_maps_to_board_handler(self):
        args = repl_parser.parse_args(["board", "main"])
        self.assertEqual(args.command, "board")
        self.assertEqual(args.board, "main")
        self.assertIs(args.func, handle_board_change)

    def test_board_command_requires_name(self):
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["board"])

    def test_column_command_maps_to_column_handler(self):
        args = repl_parser.parse_args(["column", "todo"])
        self.assertEqual(args.command, "column")
        self.assertEqual(args.column, "todo")
        self.assertIs(args.func, handle_column_change)

    def test_column_command_requires_name(self):
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["column"])

    def test_create_aliases_map_to_create_handlers(self):
        args = repl_parser.parse_args(["new", "board", "main"])
        self.assertEqual(args.command, "new")
        self.assertEqual(args.create_subject, "board")
        self.assertEqual(args.board, "main")
        self.assertIs(args.func, handle_board_create)

        args = repl_parser.parse_args(["new", "column", "main/todo"])
        self.assertEqual(args.command, "new")
        self.assertEqual(args.create_subject, "column")
        self.assertEqual(args.path, "main/todo")
        self.assertIs(args.func, handle_column_create)

        args = repl_parser.parse_args(["n", "task", "main/todo/fix-parser"])
        self.assertEqual(args.command, "n")
        self.assertEqual(args.create_subject, "task")
        self.assertEqual(args.path, "main/todo/fix-parser")
        self.assertIs(args.func, handle_task_create)

    def test_update_task_maps_to_update_handler(self):
        args = repl_parser.parse_args([
            "update",
            "main/todo/fix-parser",
            "--assigned-to",
            "philip",
            "--priority",
            "medium",
            "--tag",
            "cli",
            "--due-date",
            "2026-06-20",
            "--created-by",
            "philip",
        ])

        self.assertEqual(args.command, "update")
        self.assertEqual(args.path, "main/todo/fix-parser")
        self.assertEqual(args.assigned_to, "philip")
        self.assertEqual(args.priority, "medium")
        self.assertEqual(args.tags, ["cli"])
        self.assertEqual(args.due_date, "2026-06-20")
        self.assertEqual(args.created_by, "philip")
        self.assertIs(args.func, handle_task_update)

    def test_list_and_ls_alias_map_to_list_handler(self):
        args = repl_parser.parse_args(["list"])
        self.assertEqual(args.command, "list")
        self.assertIs(args.func, handle_list)
        self.assertFalse(args.list)

        args = repl_parser.parse_args(["ls"])
        self.assertEqual(args.command, "ls")
        self.assertIs(args.func, handle_list)
        self.assertFalse(args.list)

        args = repl_parser.parse_args(["list", "-l"])
        self.assertTrue(args.list)

        args = repl_parser.parse_args(["list", "--list"])
        self.assertTrue(args.list)

    def test_assign_maps_to_assign_handler(self):
        args = repl_parser.parse_args(["assign", "main/todo/fix-login", "alice"])
        self.assertEqual(args.command, "assign")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertEqual(args.assigned_to, "alice")
        self.assertIs(args.func, handle_task_assign)

    def test_assign_requires_path_and_user(self):
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["assign"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["assign", "main/todo/fix-login"])

    def test_move_path_and_handler(self) -> None:
        """move binds the path argument and the handle_task_move handler."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "done"])
        self.assertEqual(args.path, "todo/fix-parser")
        self.assertIs(args.func, handle_task_move)

    def test_move_column_arg(self) -> None:
        """move with a positional column sets column and leaves flags at their defaults."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "done"])
        self.assertEqual(args.column, "done")
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_move_top_flag(self) -> None:
        """move --top sets top=True and leaves column None and other flags False."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "--top"])
        self.assertTrue(args.top)
        self.assertIsNone(args.column)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_move_bottom_flag(self) -> None:
        """move --bottom sets bottom=True and leaves column None and other flags False."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "--bottom"])
        self.assertTrue(args.bottom)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_move_up_flag(self) -> None:
        """move --up sets up=True and leaves column None and other flags False."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "--up"])
        self.assertTrue(args.up)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.down)

    def test_move_down_flag(self) -> None:
        """move --down sets down=True and leaves column None and other flags False."""
        args = repl_parser.parse_args(["move", "todo/fix-parser", "--down"])
        self.assertTrue(args.down)
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)

    def test_move_no_destination_defaults(self) -> None:
        """move with only a path leaves column=None and all flags False."""
        args = repl_parser.parse_args(["move", "todo/fix-parser"])
        self.assertIsNone(args.column)
        self.assertFalse(args.top)
        self.assertFalse(args.bottom)
        self.assertFalse(args.up)
        self.assertFalse(args.down)

    def test_rename_path_new_name_and_handler(self) -> None:
        """rename binds path, new_name, and the handle_rename handler."""
        args = repl_parser.parse_args(["rename", "proj", "Work"])
        self.assertEqual(args.path, "proj")
        self.assertEqual(args.new_name, "Work")
        self.assertIs(args.func, handle_rename)

    def test_rename_column_path_binds_handler(self) -> None:
        """rename with a board/column path still binds handle_rename."""
        args = repl_parser.parse_args(["rename", "proj/todo", "Doing"])
        self.assertEqual(args.path, "proj/todo")
        self.assertEqual(args.new_name, "Doing")
        self.assertIs(args.func, handle_rename)

    def test_rename_task_path_binds_handler(self) -> None:
        """rename with a board/column/task path still binds handle_rename."""
        args = repl_parser.parse_args(["rename", "proj/todo/fix-parser", "Fixed Parser"])
        self.assertEqual(args.path, "proj/todo/fix-parser")
        self.assertEqual(args.new_name, "Fixed Parser")
        self.assertIs(args.func, handle_rename)

    def test_rename_requires_path_and_new_name(self) -> None:
        """rename raises SystemExit when path or new_name is missing."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "proj"])

    def test_mv_alias_maps_to_move_handler(self) -> None:
        """mv is an alias for move and binds the same handler."""
        args = repl_parser.parse_args(["mv", "todo/fix-parser", "--up"])
        self.assertEqual(args.command, "mv")
        self.assertTrue(args.up)
        self.assertIs(args.func, handle_task_move)

    def test_move_mutual_exclusion(self) -> None:
        """move rejects more than one destination argument at once."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["move", "todo/fix-parser", "--top", "--bottom"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["move", "todo/fix-parser", "--up", "--down"])

    def test_cd_alias_maps_to_set_path_handler(self):
        parser = repl_parser.build_parser()

        args = parser.parse_args(["cd"])
        self.assertEqual(args.command, "cd")
        self.assertIsNone(args.path)
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_change_dir)

        args = parser.parse_args(["cd", "main/todo"])
        self.assertEqual(args.command, "cd")
        self.assertEqual(args.path, "main/todo")
        self.assertFalse(args.clear)
        self.assertIs(args.func, handle_change_dir)

        args = parser.parse_args(["cd", "--clear"])
        self.assertTrue(args.clear)
        self.assertIsNone(args.path)
        self.assertIs(args.func, handle_change_dir)


if __name__ == "__main__":
    unittest.main()
