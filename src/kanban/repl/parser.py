"""
Verb-first command line argument parser for the kanban application.

This parser uses a verb-first command structure, e.g. `create board`, `list tasks`, `delete column`, etc.
It has a smaller command vocabulary than the noun-first parser and is designed for interactive use in the REPL, 
where users may prefer a more concise and discoverable command structure. 
The noun-first parser is more verbose but may be better suited for scripting and users familiar with the domain model.

Path arguments are explicit and fully specified by the caller.
"""

import argparse

from ..models import Priority
from ..services.kanban import CONFIG_KEYS
from ..repl.commands import (
    handle_board_list,
    handle_column_list,
    handle_create,
    handle_init,
    handle_delete,
    handle_column_reorder,
    handle_get_config,
    handle_info,
    handle_list_config,
    handle_set_config,
    handle_log,
    handle_rename,
    handle_search,
    handle_status,
    handle_task_assign,
    handle_task_comment,
    handle_task_edit,
    handle_task_list,
    handle_task_move,
    handle_task_tag,
    handle_task_unset,
    handle_task_update,
    handle_task_view,
    handle_set_board,
)

SORT_TASK_CHOICES = ["title", "priority", "due-date", "created-at", "updated-at", "created-by", "column"]
PRIORITY_CHOICES = [p.value for p in Priority]

# The metavar carried by the arguments that name where a task is moved to: a
# column of the active board, or an absolute /board/column path. 
TASK_DESTINATION_METAVAR = "COLUMN | /BOARD/COLUMN"
_CONFIG_KEYS_HELP = ", ".join(sorted(CONFIG_KEYS))

# The commands that end the session.  They are handled by the consumer — the
# REPL leaves its loop, the TUI's command bar quits the app — rather than by a
# handler, so the names live here where both can read them.
EXIT_COMMANDS = {"exit", "quit", ":q"}

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
    # parser.add_argument("--verbose", action="store_true", default=False, help="Enable verbose output")


def _add_field_args(parser: argparse.ArgumentParser) -> None:
    """
    Add the --path and --id flags, which report one field of an object instead
    of the object.  Only commands that return a board, column, or task take
    them; a command that returns anything else rejects them as unrecognized.
    """
    parser.add_argument("--path", dest="show_path", action="store_true", default=False,
                        help="Print the object's path alone")
    parser.add_argument("--id", dest="show_id", action="store_true", default=False,
                        help="Print the object's id alone; with --path, the path comes first")


def add_task_filter_args(parser: argparse.ArgumentParser) -> None:
    """Add the task filter flags.  Public so the TUI's filter bar takes the same ones."""
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
    parser.add_argument("-d", "--due-date", dest="due_date", metavar="DATE", help="Due date (YYYY-MM-DD)")
    parser.add_argument("-b", "--created-by", dest="created_by", metavar="NAME", help="Creator name")
    parser.add_argument("--description", dest="description", metavar="TEXT", help="Description text (replaces the Description section of the task body)")


def _add_task_update_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-w", "--assigned-to", dest="assigned_to", metavar="NAME", help="Assign task to a user")
    parser.add_argument("-p", "--priority", choices=PRIORITY_CHOICES, metavar="LEVEL", help="Task priority")
    parser.add_argument("-t", "--tag", metavar="TAG", action="append", dest="tags", help="Add a tag (repeatable)")
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


def _add_list_args(parser: argparse.ArgumentParser, sort_choices: list[str]) -> None:
    parser.add_argument("-s", "--sort", choices=sort_choices, metavar="FIELD", help="Field to sort by")
    parser.add_argument("-r", "--reverse", action="store_true", default=False, help="Reverse the sort order")

# ---------------------------------------------------------------------------
# Verb-first subcommands
# ---------------------------------------------------------------------------

def _add_create_parser(subparsers: argparse._SubParsersAction) -> None:
    epilog = """
Examples:
    create todo "Fix login"
    create --column "In Progress"
    create --board "Main Project"
    """
    p = subparsers.add_parser("create", aliases=["new", "n"], help="Create a board, column, or task", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_global_flags(p)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("column", metavar="COLUMN", nargs="?", help="Existing column to create the new task in")
    group.add_argument("--board", metavar="NAME", dest="new_board", help="Create a new board with the given name")
    group.add_argument("-c", "--column", metavar="NAME", dest="new_column", help="Create a new column with the given name in the active board")
    p.add_argument("title", metavar="TITLE", nargs="?", help="Title of the new task")
    p.add_argument("--edit", action="store_true", default=False, help="Open the new task in the editor after creating it")
    _add_task_update_args(p)
    _add_field_args(p)
    p.set_defaults(func=handle_create)


def _add_delete_parser(subparsers: argparse._SubParsersAction) -> None:
    epilog = """
Examples:
    delete fix-login
    delete -c todo
    delete -b
    """
    p = subparsers.add_parser("delete", aliases=["del", "rm"], help="Delete a board, column, or task", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_global_flags(p)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("path", metavar="TASK", nargs="?", help="The task to delete")
    group.add_argument("-b", "--board", action="store_true", default=False, help="Delete the active board")
    group.add_argument("-c", "--column", dest="column", metavar="COLUMN", help="Delete the named column")
    p.add_argument("-f", "--force", action="store_true", default=False, help="Skip confirmation prompt")
    _add_field_args(p)
    p.set_defaults(func=handle_delete)


def _add_rename_parser(subparsers: argparse._SubParsersAction) -> None:
    epilog = """
Examples:
    rename fix-login "Fix the login page"
    rename -c todo "In Progress"
    rename -b "Main Project"
    """
    rename_parser = subparsers.add_parser("rename", help="Rename a board, column, or task", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_global_flags(rename_parser)
    group = rename_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("path", metavar="TASK", nargs="?", help="The task to rename")
    group.add_argument("-b", "--board", action="store_true", default=False, help="Rename the active board")
    group.add_argument("-c", "--column", dest="column", metavar="COLUMN", help="Rename the named column")
    rename_parser.add_argument("new_name", metavar="NEW-NAME", help="The new name for the board, column, or task")
    _add_field_args(rename_parser)
    rename_parser.set_defaults(func=handle_rename)


def _add_reorder_parser(subparsers: argparse._SubParsersAction) -> None:
    reorder_parser = subparsers.add_parser("reorder", help="Reorder columns in a board")
    _add_global_flags(reorder_parser)
    reorder_sub = reorder_parser.add_subparsers(dest="reorder_subject", metavar="SUBJECT")
    reorder_sub.required = True

    # reorder column
    p = reorder_sub.add_parser("column", help="Move a column to a position")
    p.add_argument("column", metavar="COLUMN", help="The column to reorder")
    p.add_argument("position", metavar="POSITION", type=int, help="1-based target position")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_column_reorder)


def _add_show_parser(subparsers: argparse._SubParsersAction) -> None:
    show_parser = subparsers.add_parser("view", aliases=["show", "v", "s"], help="View task details and body")
    show_parser.add_argument("path", metavar="TASK", help="The task to show")
    show_parser.add_argument("-p", "--plain", action="store_true", default=False, help="Render the task body as plain text instead of Markdown")
    _add_field_args(show_parser)
    show_parser.set_defaults(func=handle_task_view)


def _add_info_parser(subparsers: argparse._SubParsersAction) -> None:
    epilog = """
Examples:
    info fix-login
    info -c todo
    info -b
    info fix-login --path
    info -b --id
    """
    p = subparsers.add_parser("info", aliases=["i"], help="View the details of a board, column, or task", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    _add_global_flags(p)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("path", metavar="TASK", nargs="?", help="The task to inspect")
    group.add_argument("-b", "--board", action="store_true", default=False, help="Inspect the active board")
    group.add_argument("-c", "--column", dest="column", metavar="COLUMN", help="Inspect the named column")
    _add_field_args(p)
    p.set_defaults(func=handle_info)


def _add_edit_parser(subparsers: argparse._SubParsersAction) -> None:
    edit_parser = subparsers.add_parser("edit", help="Edit a task in the default editor")
    _add_global_flags(edit_parser)
    edit_parser.add_argument("path", metavar="TASK", help="The task to edit")
    _add_field_args(edit_parser)
    edit_parser.set_defaults(func=handle_task_edit)


def _add_update_parser(subparsers: argparse._SubParsersAction) -> None:
    update_parser = subparsers.add_parser("update", help="Update a task")
    _add_global_flags(update_parser)
    update_parser.add_argument("path", metavar="TASK", help="The task to update")
    update_parser.add_argument("-c", "--column", dest="column", metavar=TASK_DESTINATION_METAVAR, help="Move the task to this column of the active board, or to an absolute /board/column path on another board")
    _add_task_create_args(update_parser)
    _add_field_args(update_parser)
    update_parser.set_defaults(func=handle_task_update)


def _add_unset_parser(subparsers: argparse._SubParsersAction) -> None:
    unset_parser = subparsers.add_parser("unset", help="Unset fields on a task")
    _add_global_flags(unset_parser)
    unset_parser.add_argument("path", metavar="TASK", help="The task to unset fields on")
    _add_task_unset_args(unset_parser)
    _add_field_args(unset_parser)
    unset_parser.set_defaults(func=handle_task_unset)


def _add_move_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("move", aliases=["mv"], help="Move a task to another column or board, or within its column")
    p.add_argument("path", metavar="TASK", type=str, help="The task to move")
    group = p.add_mutually_exclusive_group()
    group.add_argument("column", metavar=TASK_DESTINATION_METAVAR, type=str, nargs="?", help="The destination column in the active board, or an absolute /board/column path to move the task to another board")
    group.add_argument("--top", action="store_true", default=False, help="The top of the current column")
    group.add_argument("--bottom", action="store_true", default=False, help="The bottom of the current column")
    group.add_argument("--up", action="store_true", default=False, help="Move the task up within the current column")
    group.add_argument("--down", action="store_true", default=False, help="Move the task down within the current column")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_task_move)


def _add_config_parser(subparsers: argparse._SubParsersAction) -> None:
    config_parser = subparsers.add_parser("config", help="List, get, or set configuration values")
    _add_global_flags(config_parser)
    config_parser.set_defaults(func=handle_list_config)  # bare `config` lists all config values

    config_sub = config_parser.add_subparsers(dest="config_command", metavar="COMMAND")
    config_sub.required = False  # allow `config` with no subcommand to list all config values

    p = config_sub.add_parser("set", help="Set a configuration value")
    p.add_argument("key", metavar="KEY", help=f"Configuration key ({_CONFIG_KEYS_HELP})")
    p.add_argument("value", metavar="VALUE", help="Configuration value")
    _add_global_flags(p)
    p.set_defaults(func=handle_set_config)

    p = config_sub.add_parser("get", help="Get a configuration value")
    p.add_argument("key", metavar="KEY", help=f"Configuration key ({_CONFIG_KEYS_HELP})")
    _add_global_flags(p)
    p.set_defaults(func=handle_get_config)


def _add_board_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("board", help="Set the active board")
    p.add_argument("board", metavar="BOARD", help="Board to set active")
    _add_global_flags(p)
    p.set_defaults(func=handle_set_board)


def _add_boards_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("boards", help="List all boards in the kanban repository")
    p.add_argument("--slugs", action="store_true", default=False, help="Render a compact list of slugs only, like filenames")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_board_list)


def _add_columns_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("columns", aliases=["cols"], help="List the columns in the active board")
    p.add_argument("--slugs", action="store_true", default=False, help="Render a compact list of slugs only, like filenames")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_column_list)


def _add_tasks_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("tasks", help="List tasks, optionally filtered and scoped to a column")
    p.add_argument("column", metavar="COLUMN", nargs="?", help="The column to list tasks for or none to list all tasks in the active board")
    p.add_argument("--slugs", action="store_true", default=False, help="Render a compact list of slugs only, like filenames")
    p.add_argument("-x", "--exclude", metavar="COLUMN", action="append", dest="exclude_columns", help="Exclude tasks in this column (repeatable)")
    p.add_argument("--include-archived", action="store_true", default=False, dest="include_archived", help="Include archived tasks when listing the whole board")
    _add_list_args(p, SORT_TASK_CHOICES)
    add_task_filter_args(p)
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_task_list)


def _add_assign_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("assign", help="Assign a task to a user or clear its assignment")
    p.add_argument("path", metavar="TASK", help="The task to assign")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("assigned_to", metavar="USER", nargs="?", help="User to assign the task to")
    group.add_argument("-r", "--remove", action="store_true", default=False, help="Clear the task's assigned user")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_task_assign)


def _add_tag_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("tag", help="Add or remove a tag on a task")
    p.add_argument("path", metavar="TASK", help="The task to tag")
    p.add_argument("tags", metavar="TAG", help="Tag to add to or remove from the task")
    p.add_argument("-r", "--remove", action="store_true", default=False, help="Remove the tag instead of adding it")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_task_tag)


def _add_comment_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("comment", help="Append a comment to a task under a `# Comments` heading")
    p.add_argument("path", metavar="TASK", help="The task to comment on")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("comment", metavar="COMMENT", nargs="?", help="The comment text to append")
    group.add_argument("--edit", action="store_true", default=False, help="Open the task body in the editor instead of appending a comment")
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_task_comment)

# ---------------------------------------------------------------------------
# Top-level parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Return the fully configured top-level verb-first argument parser."""
    epilog = """
Examples:
    board main         Set the active board to 'main'
    cols               List the columns in the active board
    new todo "Fix login" -p high -t bug
                       Create a new task in the 'todo' column with title, priority, and tag
    tasks todo         List all tasks in the 'todo' column of the active board
    tasks -x done      List all tasks in the active board except those in the 'done' column
    tasks -t bug       List all tasks in the active board with the 'bug' tag
    tag fix-login urgent
                       Add the 'urgent' tag to the 'fix-login' task
    move fix-login done
                       Move the 'fix-login' task to the 'done' column
    move fix-login /other/todo
                       Move the 'fix-login' task to the 'todo' column of the 'other' board
    view fix-login     View the details and body of the 'fix-login' task
    tasks --help       Show help for the 'tasks' command

Slugs:
    Identify tasks and other objects using their slugs. 
    Whenever a board, column, or task is created, it is assigned a slug based on its title. 
    Slugs are unique within their scope and can be used to refer to the object in commands.
    
    For example, a task with the title "Fix login" might have the slug "fix-login". 
    Use the `--slugs` flag with the 'boards', 'columns', and 'tasks' commands to see the respective slugs."""
    
    parser = argparse.ArgumentParser(
        add_help=False,
        prog="",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # formatter_class=CustomFormatter,
        description="Kanban for engineers. Git-backed, Markdown-based kanban for your terminal.",
        # type: ignore
        color=False,
        epilog=epilog,
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

    _add_board_parser(subparsers)
    _add_boards_parser(subparsers)
    _add_columns_parser(subparsers)
    _add_tasks_parser(subparsers)
    _add_create_parser(subparsers)
    _add_rename_parser(subparsers)
    _add_delete_parser(subparsers)
    _add_reorder_parser(subparsers)
    _add_show_parser(subparsers)
    _add_info_parser(subparsers)
    _add_edit_parser(subparsers)
    _add_update_parser(subparsers)
    _add_unset_parser(subparsers)
    _add_move_parser(subparsers)
    _add_config_parser(subparsers)
    _add_assign_parser(subparsers)
    _add_tag_parser(subparsers)
    _add_comment_parser(subparsers)

    # search
    p = subparsers.add_parser("search", help="Full-text search across tasks")
    p.add_argument("query", metavar="QUERY", help="Search query")
    p.add_argument("--slugs", action="store_true", default=False, help="Render a compact list of slugs only, like filenames")
    p.add_argument("-x", "--exclude", metavar="COLUMN", action="append", dest="exclude_columns", help="Exclude tasks in this column (repeatable)")
    p.add_argument("--include-archived", action="store_true", default=False, dest="include_archived", help="Search the archived tasks too")
    add_task_filter_args(p)
    p.add_argument("--board", metavar="BOARD", help="Restrict search to a specific board")
    _add_list_args(p, SORT_TASK_CHOICES)
    _add_global_flags(p)
    _add_field_args(p)
    p.set_defaults(func=handle_search)

    # log
    p = subparsers.add_parser("log", help="Show git log for a task or scope")
    p.add_argument("path", metavar="COLUMN[/TASK]", nargs="?", help="The column or path to show the log for, or none to show the log for the active board")
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
