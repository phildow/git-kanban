"""
Command line argument parser for the kanban application.

Path arguments are explicit and fully specified by the caller.
"""

import argparse

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
    handle_task_update,
    handle_use,
)


FORMAT_CHOICES = ["table", "plain", "json"]
SORT_TASK_CHOICES = ["title", "priority", "due-date", "created-at", "updated-at", "created-by"]
SORT_BOARD_COLUMN_CHOICES = ["title"]
PRIORITY_CHOICES = ["low", "medium", "high"]


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    # parser.add_argument("--color", action="store_true", default=False, help="Enable colored output")
    parser.add_argument("--quiet", action="store_true", default=False, help="Suppress non-essential output")
    parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose output")


def _add_list_format_args(parser: argparse.ArgumentParser, sort_choices: list[str]) -> None:
    parser.add_argument("--format", choices=FORMAT_CHOICES, default="plain", metavar="FORMAT",
                        help="Output format: table, plain, or json")
    parser.add_argument("--sort", choices=sort_choices, metavar="FIELD", help="Field to sort by")
    parser.add_argument("--reverse", action="store_true", default=False, help="Reverse the sort order")


def _add_task_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assignee", metavar="NAME", help="Filter by assignee")
    parser.add_argument("--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Filter by priority")
    parser.add_argument("--tag", metavar="TAG", action="append", dest="tags", help="Filter by tag (repeatable)")
    parser.add_argument("--due-before", metavar="DATE", help="Filter tasks due before date (YYYY-MM-DD)")
    parser.add_argument("--due-after", metavar="DATE", help="Filter tasks due after date (YYYY-MM-DD)")
    parser.add_argument("--created-by", metavar="NAME", help="Filter by creator")


def _add_task_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assignee", metavar="NAME", help="Assign task to a user")
    parser.add_argument("--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("--due-date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("--created-by", metavar="NAME", help="Creator name")


# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def _add_board_parser(subparsers: argparse._SubParsersAction) -> None:
    board_parser = subparsers.add_parser("board", help="Manage boards")
    _add_global_flags(board_parser)
    board_sub = board_parser.add_subparsers(dest="board_command", metavar="COMMAND")
    board_sub.required = True

    # board list
    p = board_sub.add_parser("list", help="List all boards")
    _add_list_format_args(p, SORT_BOARD_COLUMN_CHOICES)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_list)

    # board create
    p = board_sub.add_parser("create", help="Create a new board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_create)

    # board rename
    p = board_sub.add_parser("rename", help="Rename a board")
    p.add_argument("board", metavar="BOARD", help="Current board name")
    p.add_argument("new_name", metavar="NEW-NAME", help="New board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_rename)

    # board delete
    p = board_sub.add_parser("delete", help="Delete a board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_delete)


# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def _add_column_parser(subparsers: argparse._SubParsersAction) -> None:
    col_parser = subparsers.add_parser("column", help="Manage columns")
    _add_global_flags(col_parser)
    col_sub = col_parser.add_subparsers(dest="column_command", metavar="COMMAND")
    col_sub.required = True

    # column list
    p = col_sub.add_parser("list", help="List columns")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_list_format_args(p, SORT_BOARD_COLUMN_CHOICES)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_list)

    # column create
    p = col_sub.add_parser("create", help="Create a new column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_create)

    # column rename
    p = col_sub.add_parser("rename", help="Rename a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    p.add_argument("new_name", metavar="NEW-NAME", help="New column name")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_rename)

    # column reorder
    p = col_sub.add_parser("reorder", help="Move a column to a position")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    p.add_argument("position", metavar="POSITION", type=int, help="1-based target position")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_reorder)

    # column delete
    p = col_sub.add_parser("delete", help="Delete a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_delete)


# ---------------------------------------------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

def _add_task_parser(subparsers: argparse._SubParsersAction) -> None:
    task_parser = subparsers.add_parser("task", help="Manage tasks")
    _add_global_flags(task_parser)
    task_sub = task_parser.add_subparsers(dest="task_command", metavar="COMMAND")
    task_sub.required = True

    # task list
    p = task_sub.add_parser("list", help="List tasks")
    p.add_argument("path", metavar="BOARD[/COLUMN]", help="Board/column path")
    _add_list_format_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_list)

    # task create
    p = task_sub.add_parser("create", help="Create a new task")
    p.add_argument("path", metavar="BOARD/COLUMN/TITLE", help="Fully qualified task path")
    _add_task_create_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_create)

    # task show
    p = task_sub.add_parser("show", help="Show task details")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    p.add_argument("--format", choices=FORMAT_CHOICES, default="plain", metavar="FORMAT",
                   help="Output format: table, plain, or json")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_show)

    # task edit
    p = task_sub.add_parser("edit", help="Open task in editor")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_edit)

    # task move
    p = task_sub.add_parser("move", help="Move task to another column or board")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    p.add_argument("dest", metavar="BOARD/COLUMN", help="Destination board/column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_move)

    # task delete
    p = task_sub.add_parser("delete", help="Delete a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_delete)


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------

def _add_use_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("use", aliases=["cd"], help="Set or clear the active board/column context")
    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("path", metavar="BOARD[/COLUMN]", nargs="?", help="Board or board/column to set active")
    group.add_argument("--clear", action="store_true", default=False, help="Clear the active context")
    _add_global_flags(p)
    p.set_defaults(func=handle_use)


def build_parser(*, enable_use: bool = False) -> argparse.ArgumentParser:
    """Return the fully configured top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="kanban",
        description="A filesystem-backed, git-tracked kanban task manager.",
        color=False
    )
    _add_global_flags(parser)

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # init
    p = subparsers.add_parser("init", help="Initialise a new kanban repository in the current directory")
    _add_global_flags(p)
    p.set_defaults(func=handle_init)

    if enable_use:
        _add_use_parser(subparsers)

    # board / column / task
    _add_board_parser(subparsers)
    _add_column_parser(subparsers)
    _add_task_parser(subparsers)

    # search
    p = subparsers.add_parser("search", help="Full-text search across tasks")
    p.add_argument("query", metavar="QUERY", help="Search query")
    _add_list_format_args(p, SORT_TASK_CHOICES)
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
    p.add_argument("--format", choices=FORMAT_CHOICES, default="plain", metavar="FORMAT",
                   help="Output format: table, plain, or json")
    _add_global_flags(p)
    p.set_defaults(func=handle_status)

    # config
    config_parser = subparsers.add_parser("config", help="Get or set configuration values")
    _add_global_flags(config_parser)
    config_sub = config_parser.add_subparsers(dest="config_command", metavar="COMMAND")
    config_sub.required = True

    p = config_sub.add_parser("set", help="Set a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    p.add_argument("value", metavar="VALUE", help="Configuration value")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_set)

    p = config_sub.add_parser("get", help="Get a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_get)

    # repl
    p = subparsers.add_parser("repl", help="Start an interactive kanban shell")
    p.add_argument("--noun-first", action="store_true", default=False,
                   help="Use noun-first command style in the REPL (e.g. `board create`)")
    _add_global_flags(p)
    p.set_defaults(func=handle_repl)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments and return the populated Namespace."""
    return build_parser(enable_use=False).parse_args(argv)
