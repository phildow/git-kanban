"""
Command line argument parser for the kanban application.

Path arguments are explicit and fully specified by the caller.
"""

import argparse

from ..models import Priority
from ..services.kanban import CONFIG_KEYS
from ..cli.commands import (
    handle_board_create,
    handle_board_info,
    handle_board_delete,
    handle_board_list,
    handle_board_rename,
    handle_column_create,
    handle_column_delete,
    handle_column_info,
    handle_column_list,
    handle_column_rename,
    handle_column_reorder,
    handle_get_config,
    handle_list_config,
    handle_set_config,
    handle_init,
    handle_log,
    handle_repl,
    handle_search,
    handle_status,
    handle_task_assign,
    handle_task_comment,
    handle_task_create,
    handle_task_delete,
    handle_task_edit,
    handle_task_info,
    handle_task_list,
    handle_task_move,
    handle_task_rename,
    handle_task_tag,
    handle_task_unset,
    handle_task_update,
    handle_task_view,
    handle_tui,
)


FORMAT_CHOICES = ["plain", "json"]
SORT_TASK_CHOICES = ["title", "priority", "due-date", "created-at", "updated-at", "created-by", "column"]
PRIORITY_CHOICES = [p.value for p in Priority]
_CONFIG_KEYS_HELP = ", ".join(sorted(CONFIG_KEYS))


def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    # parser.add_argument("--color", action="store_true", default=False, help="Enable colored output")
    pass


def _add_format_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=FORMAT_CHOICES, default="plain", metavar="FORMAT",
                        help="Output format: plain or json (default: plain)")


def _add_list_format_and_sort_args(parser: argparse.ArgumentParser, sort_choices: list[str]) -> None:
    parser.add_argument("-s", "--sort", choices=sort_choices, metavar="FIELD", help="Field to sort by")
    parser.add_argument("-r", "--reverse", action="store_true", default=False, help="Reverse the sort order")
    _add_format_arg(parser)


def _add_task_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Filter by assigned-to user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Filter by priority")
    parser.add_argument("-t","--tag", metavar="TAG", action="append", dest="tags", help="Filter by tag (repeatable)")
    parser.add_argument("--due-before", dest="due_before", metavar="DATE", help="Filter tasks due before date (YYYY-MM-DD)")
    parser.add_argument("--due-after", dest="due_after", metavar="DATE", help="Filter tasks due after date (YYYY-MM-DD)")
    parser.add_argument("--created-by", dest="created_by", metavar="NAME", help="Filter by creator")


def _add_task_create_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Assign task to a user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("-d", "--due-date", dest="due_date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("-b","--created-by", dest="created_by", metavar="NAME", help="Creator name")
    parser.add_argument("--description", dest="description", metavar="TEXT", help="Description text (replaces the Description section of the task body)")


def _add_task_update_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Assign task to a user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
    parser.add_argument("-c", "--column", dest="column", metavar="COLUMN", help="Move the task to this column")
    parser.add_argument("-d", "--due-date", dest="due_date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("-b", "--created-by", dest="created_by", metavar="NAME", help="Creator name")
    parser.add_argument("--description", dest="description", metavar="TEXT", help="Description text (replaces the Description section of the task body)")


def _add_task_unset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", action="store_true", default=False, help="Unset the assigned user")
    parser.add_argument("-p", "--priority", dest="priority", action="store_true", default=False, help="Unset the priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Remove a tag (repeatable)")
    parser.add_argument("-d", "--due-date", dest="due_date", action="store_true", default=False, help="Unset the due date")
    parser.add_argument("-b", "--created-by", dest="created_by", action="store_true", default=False, help="Unset the creator name")
    parser.add_argument("--description", dest="description", action="store_true", default=False, help="Clear the description (preserves the heading and any Comments section)")


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
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_list)

    # board create
    p = board_sub.add_parser("create", help="Create a new board")
    p.add_argument("board", metavar="BOARD", help="Board name")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_create)

    # board info
    p = board_sub.add_parser("info", help="Show board details")
    p.add_argument("path", metavar="BOARD", help="Fully qualified /board path")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_info)

    # board rename
    p = board_sub.add_parser("rename", help="Rename a board")
    p.add_argument("path", metavar="BOARD", help="Fully qualified /board path")
    p.add_argument("new_name", metavar="NEW-NAME", help="New board name")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_board_rename)

    # board delete
    p = board_sub.add_parser("delete", help="Delete a board")
    p.add_argument("path", metavar="BOARD", help="Fully qualified /board path")
    p.add_argument("-f", "--force", action="store_true", default=False, help="Skip confirmation prompt")
    _add_format_arg(p)
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
    p.add_argument("path", metavar="BOARD", help="Fully qualified /board path")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_list)

    # column create
    p = col_sub.add_parser("create", help="Create a new column")
    p.add_argument("path", metavar="BOARD", help="Fully qualified /board path")
    p.add_argument("title", metavar="TITLE", help="Column title")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_create)

    # column info
    p = col_sub.add_parser("info", help="Show column details")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Fully qualified /board/column path")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_info)

    # column rename
    p = col_sub.add_parser("rename", help="Rename a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Fully qualified /board/column path")
    p.add_argument("new_name", metavar="NEW-NAME", help="New column name")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_rename)

    # column reorder
    p = col_sub.add_parser("reorder", help="Move a column to a position")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Fully qualified /board/column path")
    p.add_argument("position", metavar="POSITION", type=int, help="1-based target position")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_column_reorder)

    # column delete
    p = col_sub.add_parser("delete", help="Delete a column")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Fully qualified /board/column path")
    p.add_argument("-f", "--force", action="store_true", default=False, help="Skip confirmation prompt")
    _add_format_arg(p)
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
    p.add_argument("path", metavar="BOARD[/COLUMN]", help="Fuly qualifed /board or /board/column path")
    p.add_argument("-x", "--exclude", metavar="COLUMN", action="append", dest="column", help="Exclude tasks in this column (repeatable)")
    p.add_argument("--include-archived", action="store_true", default=False, dest="include_archived", help="Include archived tasks when listing a whole board")
    _add_list_format_and_sort_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_list)

    # task create
    p = task_sub.add_parser("create", help="Create a new task")
    p.add_argument("path", metavar="BOARD/COLUMN", help="Fully qualified /board/column path")
    p.add_argument("title", metavar="TITLE", help="Task title")
    _add_task_create_args(p)
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_create)

    # task info
    p = task_sub.add_parser("info", help="Show task metadata")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_info)

    # task view
    p = task_sub.add_parser("view", help="Show task metadata and body")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    p.add_argument("-m", "--markdown", action="store_true", default=False, help="Render the task body as Markdown instead of plain text")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_view)

    # task edit
    p = task_sub.add_parser("edit", help="Open task in editor")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_edit)

    # task update
    p = task_sub.add_parser("update", help="Update task fields")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    _add_task_update_args(p)
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_update)

    # task unset
    p = task_sub.add_parser("unset", help="Unset fields on a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    _add_task_unset_args(p)
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_unset)

    # task delete
    p = task_sub.add_parser("delete", help="Delete a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    p.add_argument("-f", "--force", action="store_true", default=False, help="Skip confirmation prompt")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_delete)

    # task rename
    p = task_sub.add_parser("rename", help="Rename a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    p.add_argument("new_name", metavar="NEW-NAME", help="New task name")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_rename)

    # task move
    p = task_sub.add_parser("move", help="Move task to another column")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    group = p.add_mutually_exclusive_group()
    group.add_argument("column", type=str, nargs="?", help="The destination column")
    group.add_argument("--top", action="store_true", default=False, help="The top of the current column")
    group.add_argument("--bottom", action="store_true", default=False, help="The bottom of the current column")
    group.add_argument("--up", action="store_true", default=False, help="Move the task up within the current column")
    group.add_argument("--down", action="store_true", default=False, help="Move the task down within the current column")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_move)

    # task assign
    p = task_sub.add_parser("assign", help="Assign a task to a user or clear its assignment")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("assigned_to", metavar="USER", nargs="?", help="User to assign the task to")
    group.add_argument("-r", "--remove", action="store_true", default=False, help="Clear the task's assigned user")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_assign)

    # task tag
    p = task_sub.add_parser("tag", help="Add or remove a tag on a task")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    p.add_argument("tags", metavar="TAG", help="Tag to add to or remove from the task")
    p.add_argument("-r", "--remove", action="store_true", default=False, help="Remove the tag instead of adding it")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_tag)

    # task comment
    p = task_sub.add_parser("comment", help="Append a comment to a task under a `# Comments` heading")
    p.add_argument("path", metavar="BOARD/COLUMN/TASK", help="Fully qualified /board/column/task path")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("comment", metavar="COMMENT", nargs="?", help="The comment text to append")
    group.add_argument("--edit", action="store_true", default=False, help="Open the task body in the editor instead of appending a comment")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_task_comment)


# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Return the fully configured top-level argument parser."""
    epilog = """
Start with `kanban init` to create a new kanban project in the current directory.
Try `kanban repl` to start an interactive shell with tab completion and command history.
Try `kanban tui` to start a cards-based terminal user interface for kanban.
Use the CLI directly with `kanban board list`, `kanban task create`, etc.
    """
    parser = argparse.ArgumentParser(
        prog="kanban",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Kanban for engineers. Git-backed, Markdown-based kanban for your terminal.",
        # type: ignore
        color=False,
        epilog=epilog
    )
    _add_global_flags(parser)

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # init
    p = subparsers.add_parser("init", help="Create a new kanban project in the current directory")
    p.add_argument("-b", "--bootstrap", action="store_true", default=False,
                   help="Seed the repository with a default board and columns")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_init)

    # board / column / task
    _add_board_parser(subparsers)
    _add_column_parser(subparsers)
    _add_task_parser(subparsers)

    # search
    p = subparsers.add_parser("search", help="Full-text search across tasks")
    p.add_argument("query", metavar="QUERY", help="Search query")
    # Named `column` for the same reason `task list` is: it is the same filter,
    # built by the same helper.
    p.add_argument("-x", "--exclude", metavar="COLUMN", action="append", dest="column", help="Exclude tasks in this column (repeatable)")
    p.add_argument("--include-archived", action="store_true", default=False, dest="include_archived", help="Search the archived tasks too")
    _add_list_format_and_sort_args(p, SORT_TASK_CHOICES)
    _add_task_filter_args(p)
    p.add_argument("--board", metavar="BOARD", help="Restrict search to a specific board")
    _add_global_flags(p)
    p.set_defaults(func=handle_search)

    # log
    p = subparsers.add_parser("log", help="Show git log for a task or scope")
    p.add_argument("path", metavar="[BOARD/COLUMN/]TASK", nargs="?",
                   help="Fully qualified /board/column/task path (optional)")
    p.add_argument("--limit", metavar="N", type=int, help="Maximum number of log entries to show")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_log)

    # status
    p = subparsers.add_parser("status", help="Show repository status summary")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_status)

    # config
    config_parser = subparsers.add_parser("config", help="Get or set configuration values")
    _add_global_flags(config_parser)
    config_sub = config_parser.add_subparsers(dest="config_command", metavar="COMMAND")
    config_sub.required = True

    p = config_sub.add_parser("set", help="Set a configuration value")
    p.add_argument("key", metavar="KEY", help=f"Configuration key ({_CONFIG_KEYS_HELP})")
    p.add_argument("value", metavar="VALUE", help="Configuration value")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_set_config)

    p = config_sub.add_parser("get", help="Get a configuration value")
    p.add_argument("key", metavar="KEY", help=f"Configuration key ({_CONFIG_KEYS_HELP})")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_get_config)

    p = config_sub.add_parser("list", help="List all configuration values")
    _add_format_arg(p)
    _add_global_flags(p)
    p.set_defaults(func=handle_list_config)

    # repl
    p = subparsers.add_parser("repl", help="Start an interactive kanban shell")
    _add_global_flags(p)
    p.set_defaults(func=handle_repl)

    # tui
    p = subparsers.add_parser("tui", help="Start the cards-based terminal user interface")
    _add_global_flags(p)
    p.set_defaults(func=handle_tui)

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments and return the populated Namespace."""
    return build_parser().parse_args(argv)
