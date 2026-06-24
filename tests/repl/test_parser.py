"""Parser wiring tests for the kanban REPL.

This module documents expected parser structure, arguments, and handler
defaults for top-level and nested subcommands.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# TODO: add handle_list tests
from repl import parser as repl_parser
from repl.commands import (
    handle_board_change,
    handle_board_create,
    handle_board_rename,
    handle_column_change,
    handle_column_create,
    handle_column_rename,
    handle_delete,
    handle_list,
    handle_change_dir,
    handle_task_assign,
    handle_task_create,
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
            "task",
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
        self.assertEqual(args.update_subject, "task")
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
