"""
Verb-first command line argument parser for the kanban application.

This parser mirrors the behavior of `cli.noun_first_parser` but flips command ordering
for board/column/task/config operations, e.g. `create board` instead of
`board create`.

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
# Verb-first subcommands
# ---------------------------------------------------------------------------

def _add_create_parser(subparsers: argparse._SubParsersAction) -> None:
    create_parser = subparsers.add_parser("create", help="Create a board, column, or task")
    _add_global_flags(create_parser)
    create_sub = create_parser.add_subparsers(dest="create_subject", metavar="SUBJECT")
    create_sub.required = True

    # create board
    p = create_sub.add_parser("board", help="Create a new board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_create)

    # create column
    p = create_sub.add_parser("column", help="Create a new column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_create)

    # create task
    p = create_sub.add_parser("task", help="Create a new task")
    p.add_argument("path", metavar="BOARD/COLUMN/TITLE", help="Fully qualified task path")
    _add_task_create_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_create)


def _add_list_parser(subparsers: argparse._SubParsersAction) -> None:
    list_parser = subparsers.add_parser("list", aliases=["ls"], help="List boards, columns, or tasks")
    _add_global_flags(list_parser)
    list_sub = list_parser.add_subparsers(dest="list_subject", metavar="SUBJECT")
    list_sub.required = True

    # list board
    p = list_sub.add_parser("board", aliases=["boards"], help="List all boards")
    _add_list_format_args(p, SORT_BOARD_COLUMN_CHOICES)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_list)

    # list column
    p = list_sub.add_parser("column", aliases=["columns"], help="List columns")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_list_format_args(p, SORT_BOARD_COLUMN_CHOICES)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_list)

    # list task
    p = list_sub.add_parser("task", aliases=["tasks"], help="List tasks")
    p.add_argument("path", metavar="BOARD[/COLUMN]", help="Board/column path")
    _add_list_format_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_list)


def _add_rename_parser(subparsers: argparse._SubParsersAction) -> None:
    rename_parser = subparsers.add_parser("rename", help="Rename a board or column")
    _add_global_flags(rename_parser)
    rename_sub = rename_parser.add_subparsers(dest="rename_subject", metavar="SUBJECT")
    rename_sub.required = True

    # rename board
    p = rename_sub.add_parser("board", help="Rename a board")
    p.add_argument("board", metavar="BOARD", help="Current board name")
    p.add_argument("new_name", metavar="NEW-NAME", help="New board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_rename)

    # rename column
    p = rename_sub.add_parser("column", help="Rename a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    p.add_argument("new_name", metavar="NEW-NAME", help="New column name")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_rename)


def _add_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    delete_parser = subparsers.add_parser("delete", help="Delete a board, column, or task")
    _add_global_flags(delete_parser)
    delete_sub = delete_parser.add_subparsers(dest="delete_subject", metavar="SUBJECT")
    delete_sub.required = True

    # delete board
    p = delete_sub.add_parser("board", help="Delete a board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_global_flags(p)
    p.set_defaults(func=handle_board_delete)

    # delete column
    p = delete_sub.add_parser("column", help="Delete a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_column_delete)

    # delete task
    p = delete_sub.add_parser("task", help="Delete a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_delete)


def _add_reorder_parser(subparsers: argparse._SubParsersAction) -> None:
    reorder_parser = subparsers.add_parser("reorder", help="Reorder entities")
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
    show_parser = subparsers.add_parser("show", help="Show entity details")
    _add_global_flags(show_parser)
    show_sub = show_parser.add_subparsers(dest="show_subject", metavar="SUBJECT")
    show_sub.required = True

    # show task
    p = show_sub.add_parser("task", help="Show task details")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    p.add_argument("--format", choices=FORMAT_CHOICES, default="plain", metavar="FORMAT",
                   help="Output format: table, plain, or json")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_show)


def _add_edit_parser(subparsers: argparse._SubParsersAction) -> None:
    edit_parser = subparsers.add_parser("edit", help="Edit entities")
    _add_global_flags(edit_parser)
    edit_sub = edit_parser.add_subparsers(dest="edit_subject", metavar="SUBJECT")
    edit_sub.required = True

    # edit task
    p = edit_sub.add_parser("task", help="Open task in editor")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_edit)


def _add_move_parser(subparsers: argparse._SubParsersAction) -> None:
    move_parser = subparsers.add_parser("move", help="Move entities")
    _add_global_flags(move_parser)
    move_sub = move_parser.add_subparsers(dest="move_subject", metavar="SUBJECT")
    move_sub.required = True

    # move task
    p = move_sub.add_parser("task", help="Move task to another column or board")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    p.add_argument("dest", metavar="BOARD/COLUMN", help="Destination board/column path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_move)


def _add_set_parser(subparsers: argparse._SubParsersAction) -> None:
    set_parser = subparsers.add_parser("set", help="Set values")
    _add_global_flags(set_parser)
    set_sub = set_parser.add_subparsers(dest="set_subject", metavar="SUBJECT")
    set_sub.required = True

    # set config
    p = set_sub.add_parser("config", help="Set a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    p.add_argument("value", metavar="VALUE", help="Configuration value")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_set)


def _add_get_parser(subparsers: argparse._SubParsersAction) -> None:
    get_parser = subparsers.add_parser("get", help="Get values")
    _add_global_flags(get_parser)
    get_sub = get_parser.add_subparsers(dest="get_subject", metavar="SUBJECT")
    get_sub.required = True

    # get config
    p = get_sub.add_parser("config", help="Get a configuration value")
    p.add_argument("key", metavar="KEY", help="Configuration key (e.g. name)")
    _add_global_flags(p)
    p.set_defaults(func=handle_config_get)


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
    """Return the fully configured top-level verb-first argument parser."""
    parser = argparse.ArgumentParser(
        prog="kanban",
        description="A filesystem-backed, git-tracked kanban task manager.",
        color=False,
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

    # verb-first operations
    _add_create_parser(subparsers)
    _add_list_parser(subparsers)
    _add_rename_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_reorder_parser(subparsers)
    _add_show_parser(subparsers)
    _add_edit_parser(subparsers)
    _add_move_parser(subparsers)
    _add_set_parser(subparsers)
    _add_get_parser(subparsers)

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

    # repl
    p = subparsers.add_parser("repl", help="Start an interactive kanban shell")
    _add_global_flags(p)
    p.set_defaults(func=handle_repl)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments and return the populated Namespace."""
    return build_parser(enable_use=False).parse_args(argv)
