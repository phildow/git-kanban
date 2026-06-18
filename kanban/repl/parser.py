"""
Verb-first command line argument parser for the kanban application.

This parser uses a verb-first command structure, e.g. `create board`, `list tasks`, `delete column`, etc.
It has a smaller command vocabulary than the noun-first parser and is designed for interactive use in the REPL, 
where users may prefer a more concise and discoverable command structure. 
The noun-first parser is more verbose but may be better suited for scripting and users familiar with the domain model.

Path arguments are explicit and fully specified by the caller.
"""

import argparse

from repl.commands import (
    handle_board_change,
    handle_column_change,
    handle_board_create,
    handle_board_rename,
    handle_list,
    handle_delete,
    handle_column_create,
    handle_column_rename,
    handle_column_reorder,
    handle_config_get,
    handle_config_set,
    handle_init,
    handle_log,
    handle_search,
    handle_status,
    handle_task_create,
    handle_task_edit,
    handle_task_move,
    handle_task_show,
    handle_task_update,
    handle_set_path,
)


FORMAT_CHOICES = ["table", "plain", "json"]
SORT_TASK_CHOICES = ["title", "priority", "due-date", "created-at", "updated-at", "created-by"]
SORT_BOARD_COLUMN_CHOICES = ["title"]
PRIORITY_CHOICES = ["low", "medium", "high"]


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    # parser.add_argument("--color", action="store_true", default=False, help="Enable colored output")
    parser.add_argument("--quiet", action="store_true", default=False, help="Suppress non-essential output")
    parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose output")


# TODO: remove
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

def _add_task_update_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assignee", metavar="NAME", help="Assign task to a user")
    parser.add_argument("--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("--due-date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("--created-by", metavar="NAME", help="Creator name")

# ---------------------------------------------------------------------------
# Verb-first subcommands
# ---------------------------------------------------------------------------

def _add_create_parser(subparsers: argparse._SubParsersAction) -> None:
    create_parser = subparsers.add_parser("create", aliases=["new", "n"], help="Create a board, column, or task")
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
    _add_task_update_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_create)


def _add_list_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("list", aliases=["ls"], help="List all boards, columns, or tasks in the current context or at a specified path")
    group = p.add_mutually_exclusive_group(required=False)
    group.add_argument("path", metavar="BOARD[/COLUMN]", nargs="?", help="Board or board/column to list (optional)")
    # p.add_subparsers(dest="path", metavar="BOARD[/COLUMN]", help="Board or board/column to list (optional)")
    _add_list_format_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_list)


def _add_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("delete", aliases=["rm"], help="Delete a board, column, or task")
    _add_global_flags(p)
    # delete_sub = p.add_subparsers(dest="path", metavar="BOARD[/COLUMN][/TASK]", help="Board, column, or task to delete")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("path", metavar="BOARD[/COLUMN][/TASK]", nargs="?", help="Board, column, or task to delete")
    # group.required = True
    p.set_defaults(func=handle_delete)


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
    edit_parser = subparsers.add_parser("edit", help="Edit tasks")
    _add_global_flags(edit_parser)
    edit_sub = edit_parser.add_subparsers(dest="edit_subject", metavar="SUBJECT")
    edit_sub.required = True

    # edit task
    p = edit_sub.add_parser("task", help="Open task in editor")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified task path")
    _add_global_flags(p)
    p.set_defaults(func=handle_task_edit)


def _add_update_parser(subparsers: argparse._SubParsersAction) -> None:
    update_parser = subparsers.add_parser("update", help="Update a task")
    _add_global_flags(update_parser)
    update_sub = update_parser.add_subparsers(dest="update_subject", metavar="SUBJECT")
    update_sub.required = True

    # update task
    p = update_sub.add_parser("task", help="Update task fields")
    p.add_argument("path", metavar="BOARD/COLUMN/TITLE", help="Fully qualified task path")
    _add_task_create_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_update)


def _add_move_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("move", aliases=["mv"], help="Move a task to another column or board")
    p.add_argument('path', type=str, help='The task to move')
    p.add_argument('dest', type=str, help='The destination (column, board, or new title)')
    _add_global_flags(p)
    p.set_defaults(func=handle_task_move)

    # move_sub = move_parser.add_subparsers(dest="move_subject", metavar="SUBJECT")
    # move_sub.required = True
    
    # # move task
    # p = move_sub.add_parser("task", help="Move task to another column on the same board")
    # p.add_argument("path", metavar="TASK", help="The task to move, specified by its title or a fully qualified path relative to the current context")
    # p.add_argument("dest", metavar="[BOARD/]COLUMN", help="Destination board/column path")
    # _add_global_flags(p)
    # p.set_defaults(func=handle_task_move)


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
    p.set_defaults(func=handle_set_path)


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


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
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

    _add_cd_parser(subparsers)
    _add_board_parser(subparsers)
    _add_column_parser(subparsers)

    # verb-first operations
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

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments and return the populated Namespace."""
    return build_parser().parse_args(argv)
