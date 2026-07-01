"""
Verb-first command line argument parser for the kanban application.

This parser uses a verb-first command structure, e.g. `create board`, `list tasks`, `delete column`, etc.
It has a smaller command vocabulary than the noun-first parser and is designed for interactive use in the REPL, 
where users may prefer a more concise and discoverable command structure. 
The noun-first parser is more verbose but may be better suited for scripting and users familiar with the domain model.

Path arguments are explicit and fully specified by the caller.
"""

import argparse

from ..repl.commands import (
    handle_board_change,
    handle_column_change,
    handle_board_create,
    handle_init,
    handle_list,
    handle_delete,
    handle_column_create,
    handle_column_reorder,
    handle_config_get,
    handle_config_set,
    handle_log,
    handle_rename,
    handle_search,
    handle_status,
    handle_task_assign,
    handle_task_create,
    handle_task_edit,
    handle_task_move,
    handle_task_show,
    handle_task_update,
    handle_change_dir,
)

SORT_TASK_CHOICES = ["title", "priority", "due-date", "created-at", "updated-at", "created-by", "column"]
SORT_BOARD_COLUMN_CHOICES = ["title"]
PRIORITY_CHOICES = ["low", "medium", "high"]

class CustomFormatter(argparse.RawDescriptionHelpFormatter):
    @staticmethod
    def _customize_help_text(text: str | None) -> str:
        """Normalize help text before it is rendered."""
        if not text:
            return ""
        return " ".join(text.split())

    def _get_help_string(self, action: argparse.Action) -> str:
        """Return customized help text for each parser action."""
        text =self._customize_help_text(super()._get_help_string(action))
        text = text.replace("show this help message and exit", "Show this help message")
        return text

    def _format_usage(self, usage, actions, groups, prefix):
        """Return a customized usage string for the parser."""
        # Unfortunately not called for subparsers, so we have to customize the help text for each subparser individually.

        if prefix is None:
            prefix = "usage: "
        # Custom logic to avoid double space if prog is empty
        if not prefix.endswith(" ") and usage and not usage.startswith(" "):
            prefix = prefix[:-1]
        return super()._format_usage(usage, actions, groups, prefix)


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    ...
    # note:: These flags are not currently used, but they are defined here for possible future use.
    #
    # parser.add_argument("--color", action="store_true", default=False, help="Enable colored output")
    # parser.add_argument("--quiet", action="store_true", default=False, help="Suppress non-essential output")
    # parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose output")


def _add_task_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Filter by assigned-to user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Filter by priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Filter by tag (repeatable)")
    parser.add_argument("--due-before", dest="due_before", metavar="DATE", help="Filter tasks due before date (YYYY-MM-DD)")
    parser.add_argument("--due-after", dest="due_after", metavar="DATE", help="Filter tasks due after date (YYYY-MM-DD)")
    parser.add_argument("--created-by", dest="created_by", metavar="NAME", help="Filter by creator")


def _add_task_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Assign task to a user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("--due-date", dest="due_date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("--created-by", dest="created_by", metavar="NAME", help="Creator name")


def _add_task_update_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Assign task to a user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("--due-date", dest="due_date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("--created-by", dest="created_by", metavar="NAME", help="Creator name")


def _add_list_args(parser: argparse.ArgumentParser, sort_choices: list[str]) -> None:
    parser.add_argument("-s", "--sort", choices=sort_choices, metavar="FIELD", help="Field to sort by")
    parser.add_argument("-r", "--reverse", action="store_true", default=False, help="Reverse the sort order")

# UNUSED
def _add_help_message(parser: argparse.ArgumentParser) -> None:
    """Print the help message for the REPL."""
    parser.add_argument("--h", action="help", default=argparse.SUPPRESS, help="Display this custom help message and exit.")

# ---------------------------------------------------------------------------
# Verb-first subcommands
# ---------------------------------------------------------------------------

def _add_create_parser(subparsers: argparse._SubParsersAction) -> None:
    create_parser = subparsers.add_parser("create", aliases=["new", "n"], help="Create a board, column, or task")
    _add_global_flags(create_parser)
    create_sub = create_parser.add_subparsers(dest="create_subject", metavar="SUBJECT")
    create_sub.required = True

    # create board
    p = create_sub.add_parser("board", aliases=["b"], help="Create a new board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_create)

    # create column
    p = create_sub.add_parser("column", aliases=["c"], help="Create a new column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_create)

    # create task
    p = create_sub.add_parser("task", aliases=["t"], help="Create a new task")
    p.add_argument("path", metavar="BOARD/COLUMN/TITLE", help="Fully qualified task path")
    _add_task_update_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_create)


def _add_list_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("list", aliases=["ls"], help="List all boards, columns, or tasks in the current context or at a specified path")
    p.add_argument("-l", "--list", action="store_true", default=False, help="Enable list-mode output")
    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("path", metavar="BOARD[/COLUMN]", nargs="?", help="Board or board/column to list (optional)")
    group.add_argument("-a", "--tasks", dest="all_tasks", action="store_true", default=False, help="List all tasks on the current board")
    _add_list_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_list)


def _add_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("delete", aliases=["del", "rm"], help="Delete a board, column, or task")
    _add_global_flags(p)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("path", metavar="BOARD[/COLUMN][/TASK]", nargs="?", help="Board, column, or task to delete")
    p.add_argument("-f", "--force", action="store_true", default=False, help="Skip confirmation prompt")
    p.set_defaults(func=handle_delete)


def _add_rename_parser(subparsers: argparse._SubParsersAction) -> None:
    rename_parser = subparsers.add_parser("rename", help="Rename a board, column, or task")
    rename_parser.add_argument("path", metavar="BOARD/COLUMN/TASK", help="The board, column, or task to rename")
    rename_parser.add_argument("new_name", metavar="NEW-NAME", help="The new name for the board, column, or task")
    _add_global_flags(rename_parser)
    rename_parser.set_defaults(func=handle_rename)


def _add_reorder_parser(subparsers: argparse._SubParsersAction) -> None:
    reorder_parser = subparsers.add_parser("reorder", help="Reorder columns or tasks")
    _add_global_flags(reorder_parser)
    reorder_sub = reorder_parser.add_subparsers(dest="reorder_subject", metavar="SUBJECT")
    reorder_sub.required = True

    # reorder column
    p = reorder_sub.add_parser("column", help="Move a column to a position")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    p.add_argument("position", metavar="POSITION", type=int, help="1-based target position")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_reorder)


def _add_show_parser(subparsers: argparse._SubParsersAction) -> None:
    show_parser = subparsers.add_parser("show", aliases=["view", "v", "s"], help="Show task details")
    show_parser.add_argument("path", metavar="BOARD/COLUMN/TASK", help="The task to show")
    show_parser.set_defaults(func=handle_task_show)


def _add_edit_parser(subparsers: argparse._SubParsersAction) -> None:
    edit_parser = subparsers.add_parser("edit", help="Edit a task in the default editor")
    _add_global_flags(edit_parser)
    edit_parser.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    edit_parser.set_defaults(func=handle_task_edit)


def _add_update_parser(subparsers: argparse._SubParsersAction) -> None:
    update_parser = subparsers.add_parser("update", help="Update a task")
    _add_global_flags(update_parser)
    update_parser.add_argument("path", metavar="BOARD/COLUMN/TITLE", help="Fully qualified task path")
    _add_task_create_args(update_parser)
    update_parser.set_defaults(func=handle_task_update)


def _add_move_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("move", aliases=["mv"], help="Move a task to another column")
    p.add_argument("path", type=str, help="The task to move")
    group = p.add_mutually_exclusive_group()
    group.add_argument("column", type=str, nargs="?", help="The destination column")
    group.add_argument("--top", action="store_true", default=False, help="The top of the current column")
    group.add_argument("--bottom", action="store_true", default=False, help="The bottom of the current column")
    group.add_argument("--up", action="store_true", default=False, help="Move the task up within the current column")
    group.add_argument("--down", action="store_true", default=False, help="Move the task down within the current column")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_move)


def _add_config_parser(subparsers: argparse._SubParsersAction) -> None:
    config_parser = subparsers.add_parser("config", help="List, get, or set configuration values")
    _add_global_flags(config_parser)
    
    config_sub = config_parser.add_subparsers(dest="config_command", metavar="COMMAND")
    config_sub.required = False  # allow `config` with no subcommand to list all config values

    p = config_sub.add_parser("set", help="Set a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    p.add_argument("value", metavar="VALUE", help="Configuration value")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_set)

    p = config_sub.add_parser("get", help="Get a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_get)


def _add_cd_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("cd", help="Set or clear the active board and column")
    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("path", metavar="BOARD[/COLUMN]", nargs="?", help="Board or board/column to set active")
    group.add_argument("--clear", action="store_true", default=False, help="Clear the current context")
    _add_global_flags(p)
    p.set_defaults(func=handle_change_dir)


def _add_board_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("board", help="Set the active board")
    p.add_argument("board", metavar="BOARD", help="Name of board to go to")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_change)


def _add_column_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("column", help="Set the active column")
    p.add_argument("column", metavar="COLUMN", help="Name of column to go to")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_change)


def _add_assign_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("assign", help="Assign a task to a user")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    p.add_argument("assigned_to", metavar="USER", help="User to assign the task to")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_assign)

# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Return the fully configured top-level verb-first argument parser."""
    parser = argparse.ArgumentParser(
        add_help=False,
        prog="",
        formatter_class=CustomFormatter,
        description="Git Kanban: the backed-by-the-filesystem, tracked-by-git task manager",
        color=False,
    )
    
    _add_global_flags(parser)

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # init
    p = subparsers.add_parser("init", help="Initialise a new kanban repository")
    p.add_argument("-b", "--bootstrap", action="store_true", default=False,
                   help="Seed the repository with a default board and columns")
    _add_global_flags(p)
    p.set_defaults(func=handle_init)

    _add_cd_parser(subparsers)
    _add_board_parser(subparsers)
    _add_column_parser(subparsers)
    _add_create_parser(subparsers)
    _add_list_parser(subparsers)
    _add_rename_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_reorder_parser(subparsers)
    _add_show_parser(subparsers)
    _add_edit_parser(subparsers)
    _add_update_parser(subparsers)
    _add_move_parser(subparsers)
    _add_config_parser(subparsers)
    _add_assign_parser(subparsers)

    # search
    p = subparsers.add_parser("search", help="Full-text search across tasks")
    p.add_argument("query", metavar="QUERY", help="Search query")
    _add_task_filter_args(p)
    p.add_argument("--board", metavar="BOARD", help="Restrict search to a specific board")
    _add_global_flags(p)
    p.set_defaults(func=handle_search)

    # log
    p = subparsers.add_parser("log", help="Show git log for a task or scope")
    p.add_argument("path", metavar="[BOARD/COLUMN/]TASK", nargs="?",
                   help="Task path or title (optional)")
    p.add_argument("--limit", metavar="N", type=int, help="Maximum number of log entries to show")
    _add_global_flags(p)
    p.set_defaults(func=handle_log)

    # status
    p = subparsers.add_parser("status", help="Show repository status summary")
    _add_global_flags(p)
    p.set_defaults(func=handle_status)

    # exit
    p = subparsers.add_parser("exit", aliases=["quit", ":q"], help="Exit the REPL")
    p.set_defaults(func=lambda args: None)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments and return the populated Namespace."""
    return build_parser().parse_args(argv)
