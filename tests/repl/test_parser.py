"""Parser wiring tests for the kanban REPL.

This module documents expected parser structure, arguments, and handler
defaults for top-level and nested subcommands.
"""

from __future__ import annotations

import unittest

from kanban.repl import parser as repl_parser
from kanban.repl.commands import (
    handle_board_create,
    handle_board_list,
    handle_column_create,
    handle_column_list,
    handle_set_board,
    handle_rename,
    handle_search,
    handle_task_assign,
    handle_task_comment,
    handle_task_create,
    handle_task_list,
    handle_task_move,
    handle_task_tag,
    handle_task_unset,
    handle_task_view,
    handle_task_info,
    handle_task_update,
)

class TestParserAliases(unittest.TestCase):
    """Tests for verb-first parser aliases and wiring."""

    def test_boards_command_maps_to_board_list_handler(self):
        args = repl_parser.parse_args(["boards"])
        self.assertEqual(args.command, "boards")
        self.assertFalse(args.slugs)
        self.assertIs(args.func, handle_board_list)

    def test_boards_slugs_flag(self):
        """`boards --slugs` sets slugs to True."""
        args = repl_parser.parse_args(["boards", "--slugs"])
        self.assertTrue(args.slugs)

    def test_columns_and_cols_alias_map_to_column_list_handler(self):
        args = repl_parser.parse_args(["columns"])
        self.assertEqual(args.command, "columns")
        self.assertIsNone(args.board)
        self.assertFalse(args.slugs)
        self.assertIs(args.func, handle_column_list)

        args = repl_parser.parse_args(["cols", "alpha"])
        self.assertEqual(args.command, "cols")
        self.assertEqual(args.board, "alpha")
        self.assertIs(args.func, handle_column_list)

    def test_columns_slugs_flag(self):
        """`columns ... --slugs` sets slugs to True."""
        args = repl_parser.parse_args(["columns", "alpha", "--slugs"])
        self.assertTrue(args.slugs)

    def test_tasks_maps_to_task_list_handler(self):
        args = repl_parser.parse_args(["tasks"])
        self.assertEqual(args.command, "tasks")
        self.assertIsNone(args.column)
        self.assertIsNone(args.sort)
        self.assertFalse(args.reverse)
        self.assertFalse(args.slugs)
        self.assertIsNone(args.exclude_columns)
        self.assertIs(args.func, handle_task_list)

        args = repl_parser.parse_args(["tasks", "alpha/todo"])
        self.assertEqual(args.column, "alpha/todo")
        self.assertIs(args.func, handle_task_list)

    def test_tasks_sort_reverse_and_slugs_flags(self):
        """`tasks ... --sort <field> --reverse --slugs` sets all three."""
        args = repl_parser.parse_args(["tasks", "alpha", "--sort", "title", "--reverse", "--slugs"])
        self.assertEqual(args.sort, "title")
        self.assertTrue(args.reverse)
        self.assertTrue(args.slugs)

    def test_tasks_exclude_flag_is_repeatable(self):
        """`tasks ... -x <column> --exclude <column>` accumulates into a list."""
        args = repl_parser.parse_args(["tasks", "alpha", "-x", "done", "--exclude", "archive"])
        self.assertEqual(args.exclude_columns, ["done", "archive"])

    def test_create_aliases_map_to_create_handlers(self):
        args = repl_parser.parse_args(["new", "board", "main"])
        self.assertEqual(args.command, "new")
        self.assertEqual(args.create_subject, "board")
        self.assertEqual(args.board, "main")
        self.assertIs(args.func, handle_board_create)

        args = repl_parser.parse_args(["new", "column", "todo"])
        self.assertEqual(args.command, "new")
        self.assertEqual(args.create_subject, "column")
        self.assertEqual(args.column, "todo")
        self.assertIs(args.func, handle_column_create)

        args = repl_parser.parse_args(["n", "task", "todo", "fix-parser"])
        self.assertEqual(args.command, "n")
        self.assertEqual(args.create_subject, "task")
        self.assertEqual(args.column, "todo")
        self.assertEqual(args.title, "fix-parser")
        self.assertFalse(args.edit)
        self.assertIs(args.func, handle_task_create)

    def test_create_task_edit_flag(self):
        """`create task ... --edit` sets edit to True."""
        args = repl_parser.parse_args(["create", "task", "todo", "fix-parser", "--edit"])
        self.assertTrue(args.edit)

    def test_search_maps_to_search_handler(self):
        args = repl_parser.parse_args(["search", "fix"])
        self.assertEqual(args.command, "search")
        self.assertEqual(args.query, "fix")
        self.assertIsNone(args.sort)
        self.assertFalse(args.reverse)
        self.assertFalse(args.slugs)
        self.assertIs(args.func, handle_search)

    def test_search_slugs_flag(self):
        """`search ... --slugs` sets slugs to True."""
        args = repl_parser.parse_args(["search", "fix", "--slugs"])
        self.assertTrue(args.slugs)

    def test_search_sort_and_reverse_flags(self):
        """`search ... --sort <field> --reverse` sets sort and reverse."""
        args = repl_parser.parse_args(["search", "fix", "--sort", "priority", "--reverse"])
        self.assertEqual(args.sort, "priority")
        self.assertTrue(args.reverse)

    def test_search_sort_rejects_invalid_choice(self):
        """`search --sort` only accepts SORT_TASK_CHOICES values."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["search", "fix", "--sort", "bogus"])

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
        self.assertIsNone(args.column)
        self.assertIs(args.func, handle_task_update)

    def test_update_task_column_flag_sets_column(self):
        """`update --column` (and its -c alias) populate dest="column"."""
        long = repl_parser.parse_args(["update", "main/todo/fix-parser", "--column", "done"])
        self.assertEqual(long.column, "done")

        short = repl_parser.parse_args(["update", "main/todo/fix-parser", "-c", "done"])
        self.assertEqual(short.column, "done")

    def test_unset_task_defaults_all_false(self):
        """`unset TASK` with no flags leaves all scalar dests False and tags None."""
        args = repl_parser.parse_args(["unset", "main/todo/fix-parser"])

        self.assertEqual(args.command, "unset")
        self.assertEqual(args.path, "main/todo/fix-parser")
        self.assertFalse(args.assigned_to)
        self.assertFalse(args.priority)
        self.assertFalse(args.due_date)
        self.assertFalse(args.created_by)
        self.assertIsNone(args.tags)
        self.assertIs(args.func, handle_task_unset)

    def test_unset_task_scalar_flags_set_true(self):
        """Scalar unset flags act as store_true (no value required)."""
        args = repl_parser.parse_args([
            "unset",
            "main/todo/fix-parser",
            "--assigned-to",
            "--priority",
            "--due-date",
            "--created-by",
        ])

        self.assertTrue(args.assigned_to)
        self.assertTrue(args.priority)
        self.assertTrue(args.due_date)
        self.assertTrue(args.created_by)

    def test_unset_task_tag_flag_takes_value_and_is_repeatable(self):
        """`unset --tag TAG` takes a value and appends when repeated."""
        args = repl_parser.parse_args([
            "unset",
            "main/todo/fix-parser",
            "--tag", "chore",
            "--tag", "bug",
        ])

        self.assertEqual(args.tags, ["chore", "bug"])

    def test_show_maps_to_show_handler_and_defaults_plain_to_false(self):
        args = repl_parser.parse_args(["show", "main/todo/fix-login"])
        self.assertEqual(args.command, "show")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertFalse(args.plain)
        self.assertIs(args.func, handle_task_view)

    def test_info_maps_to_info_handler(self):
        args = repl_parser.parse_args(["info", "main/todo/fix-login"])
        self.assertEqual(args.command, "info")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertIs(args.func, handle_task_info)

    def test_show_plain_flag(self):
        """`show ... -p`/`--plain` sets plain to True."""
        args = repl_parser.parse_args(["show", "main/todo/fix-login", "-p"])
        self.assertTrue(args.plain)

        args = repl_parser.parse_args(["show", "main/todo/fix-login", "--plain"])
        self.assertTrue(args.plain)

    def test_assign_requires_path_and_user(self):
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["assign"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["assign", "main/todo/fix-login"])

    def test_assign_binds_path_user_and_handler(self):
        """`assign TASK USER` binds path/assigned_to and leaves delete False."""
        args = repl_parser.parse_args(["assign", "main/todo/fix-login", "alice"])
        self.assertEqual(args.command, "assign")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertEqual(args.assigned_to, "alice")
        self.assertFalse(args.delete)
        self.assertIs(args.func, handle_task_assign)

    def test_assign_delete_flag(self):
        """`assign TASK -d`/`--delete` sets args.delete to True and leaves assigned_to None."""
        args = repl_parser.parse_args(["assign", "main/todo/fix-login", "-d"])
        self.assertTrue(args.delete)
        self.assertIsNone(args.assigned_to)

        args = repl_parser.parse_args(["assign", "main/todo/fix-login", "--delete"])
        self.assertTrue(args.delete)

    def test_assign_rejects_user_and_delete_together(self):
        """`assign TASK USER --delete` is rejected because they are mutually exclusive."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["assign", "main/todo/fix-login", "alice", "--delete"])

    def test_tag_requires_path_and_tag(self):
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["tag"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["tag", "main/todo/fix-login"])

    def test_tag_binds_path_tag_and_handler(self):
        """`tag TASK TAG` sets path/tag positional args and maps to handle_task_tag."""
        args = repl_parser.parse_args(["tag", "main/todo/fix-login", "auth"])
        self.assertEqual(args.command, "tag")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertEqual(args.tags, "auth")
        self.assertFalse(args.delete)
        self.assertIs(args.func, handle_task_tag)

    def test_tag_delete_flag(self):
        """`tag ... -d`/`--delete` sets args.delete to True."""
        args = repl_parser.parse_args(["tag", "main/todo/fix-login", "auth", "-d"])
        self.assertTrue(args.delete)

        args = repl_parser.parse_args(["tag", "main/todo/fix-login", "auth", "--delete"])
        self.assertTrue(args.delete)

    def test_comment_requires_path_and_comment(self):
        """`comment` requires a task path and either a comment or --edit."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["comment"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["comment", "main/todo/fix-login"])

    def test_comment_rejects_comment_and_edit_together(self):
        """`comment TASK COMMENT --edit` is rejected because they are mutually exclusive."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["comment", "main/todo/fix-login", "Looks good", "--edit"])

    def test_comment_binds_path_comment_and_handler(self):
        """`comment TASK COMMENT` binds path/comment and maps to handle_task_comment."""
        args = repl_parser.parse_args(["comment", "main/todo/fix-login", "Looks good"])
        self.assertEqual(args.command, "comment")
        self.assertEqual(args.path, "main/todo/fix-login")
        self.assertEqual(args.comment, "Looks good")
        self.assertFalse(args.edit)
        self.assertIs(args.func, handle_task_comment)

    def test_comment_edit_flag(self):
        """`comment TASK --edit` sets edit=True and leaves comment None."""
        args = repl_parser.parse_args(["comment", "main/todo/fix-login", "--edit"])
        self.assertTrue(args.edit)
        self.assertIsNone(args.comment)

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

    def test_rename_active_board_mode(self) -> None:
        """rename -b binds active-board mode with required new_name."""
        args = repl_parser.parse_args(["rename", "-b", "Work"])
        self.assertTrue(args.board)
        self.assertIsNone(args.path)
        self.assertIsNone(args.column)
        self.assertEqual(args.new_name, "Work")
        self.assertIs(args.func, handle_rename)

    def test_rename_column_mode(self) -> None:
        """rename -c COLUMN binds column mode with a column name and no path."""
        args = repl_parser.parse_args(["rename", "-c", "todo", "Doing"])
        self.assertEqual(args.column, "todo")
        self.assertIsNone(args.path)
        self.assertFalse(args.board)
        self.assertEqual(args.new_name, "Doing")
        self.assertIs(args.func, handle_rename)

    def test_rename_task_slug_binds_handler(self) -> None:
        """rename with a bare task slug binds handle_rename in path mode."""
        args = repl_parser.parse_args(["rename", "fix-parser", "Fixed Parser"])
        self.assertEqual(args.path, "fix-parser")
        self.assertFalse(args.board)
        self.assertIsNone(args.column)
        self.assertEqual(args.new_name, "Fixed Parser")
        self.assertIs(args.func, handle_rename)

    def test_rename_requires_mode_and_new_name(self) -> None:
        """rename requires either path, -b, or -c, and always requires new_name."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "fix-parser"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "-b"])
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "-c", "todo"])

    def test_rename_rejects_path_and_board_flag_together(self) -> None:
        """rename rejects combining a path with -b/--board."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "fix-parser", "-b", "Doing"])

    def test_rename_rejects_board_and_column_flags_together(self) -> None:
        """rename rejects combining -b/--board with -c/--column at the same time."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["rename", "-b", "-c", "todo", "Doing"])

    def test_delete_path_mode(self) -> None:
        """delete <task> binds path mode with board and column flags unset."""
        args = repl_parser.parse_args(["delete", "fix-parser", "--force"])
        self.assertEqual(args.path, "fix-parser")
        self.assertFalse(args.board)
        self.assertIsNone(args.column)
        self.assertTrue(args.force)

    def test_delete_board_mode(self) -> None:
        """delete -b binds active-board mode with no path or column."""
        args = repl_parser.parse_args(["delete", "-b", "--force"])
        self.assertTrue(args.board)
        self.assertIsNone(args.path)
        self.assertIsNone(args.column)
        self.assertTrue(args.force)

    def test_delete_column_mode(self) -> None:
        """delete -c COLUMN binds column mode with a column name and no path."""
        args = repl_parser.parse_args(["delete", "-c", "todo", "--force"])
        self.assertEqual(args.column, "todo")
        self.assertIsNone(args.path)
        self.assertFalse(args.board)
        self.assertTrue(args.force)

    def test_delete_requires_path_or_board_flag(self) -> None:
        """delete requires a TASK path, -b/--board, or -c/--column."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["delete"])

    def test_delete_rejects_path_and_board_flag_together(self) -> None:
        """delete rejects combining a path with -b/--board at the same time."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["delete", "fix-parser", "-b"])

    def test_delete_rejects_board_and_column_flags_together(self) -> None:
        """delete rejects combining -b/--board with -c/--column at the same time."""
        with self.assertRaises(SystemExit):
            repl_parser.parse_args(["delete", "-b", "-c", "todo"])

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

    def test_reorder_column_binds_column_and_position(self) -> None:
        """reorder column binds the target column into args.column (not args.path)."""
        args = repl_parser.parse_args(["reorder", "column", "proj/done", "2"])
        self.assertEqual(args.column, "proj/done")
        self.assertEqual(args.position, 2)

    def test_board_command_maps_to_set_path_handler(self):
        parser = repl_parser.build_parser()

        args = parser.parse_args(["board", "main"])
        self.assertEqual(args.command, "board")
        self.assertEqual(args.board, "main")
        self.assertIs(args.func, handle_set_board)


if __name__ == "__main__":
    unittest.main()
