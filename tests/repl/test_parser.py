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
    handle_board_create,
    handle_board_rename,
    handle_column_create,
    handle_column_rename,
    handle_delete,
    handle_list,
    handle_task_create,
    handle_task_update,
    handle_use,
)

class TestParserAliases(unittest.TestCase):
    """Tests for verb-first parser aliases and wiring."""

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
            "--assignee",
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
        self.assertEqual(args.assignee, "philip")
        self.assertEqual(args.priority, "medium")
        self.assertEqual(args.tags, ["cli"])
        self.assertEqual(args.due_date, "2026-06-20")
        self.assertEqual(args.created_by, "philip")
        self.assertIs(args.func, handle_task_update)

    def test_list_and_ls_alias_map_to_list_handler(self):
        args = repl_parser.parse_args(["list"])
        self.assertEqual(args.command, "list")
        self.assertIs(args.func, handle_list)

        args = repl_parser.parse_args(["ls"])
        self.assertEqual(args.command, "ls")
        self.assertIs(args.func, handle_list)

    def test_cd_alias_maps_to_use_handler(self):
        parser = repl_parser.build_parser()

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
