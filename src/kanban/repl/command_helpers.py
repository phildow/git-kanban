
"""
A service that provides handlers for REPL commands that reuse the same logic as the CLI handlers, 
but with a different interface for passing arguments and rendering results.

Designed to keep the base handlers lean. The main entry points for the REPL are in repl/handlers.py, 
which call into this service as needed to perform more complex operations.
"""

import argparse
from pathlib import Path

from ..models import Board, Column, Slug, Task
from ..services.kanban import KanbanService, TaskCreateParams
from ..utils.args import build_task_filter, parse_priority


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def handle_task_list_helper(args: argparse.Namespace, svc: KanbanService) -> list[Task]:
    """
    Return tasks scoped by path (a board or board/column path).  This is
    the main entry point for the `tasks` command in the REPL.  When path is
    omitted, falls back to every task in the active board (all columns),
    raising if no board is active.

    `--include-archived` rides on the filter and widens a board listing to the
    archived tasks; the service is what refuses it alongside a column or an
    excluded archive.
    """
    path = args.column
    filter = build_task_filter(args)
    sort = args.sort
    reverse = args.reverse

    if not path:
        board = svc.working_board
        if not board:
            raise ValueError("No active board; provide a board or board/column, or set one with `board`")
        return svc.get_tasks(path=Path(f"/{board}"), filter=filter, sort=sort, reverse=reverse)

    board, column, _ = svc.path_components(path)
    if board is None:
        raise ValueError(f"Cannot resolve board from: {path}")
    if column:
        return svc.get_tasks(path=Path(f"/{board}/{column}"), filter=filter, sort=sort, reverse=reverse)
    return svc.get_tasks(path=Path(f"/{board}"), filter=filter, sort=sort, reverse=reverse)


def handle_delete_helper(args: argparse.Namespace, svc: KanbanService) -> Board | Column | Task | None:
    """
    Delete the entity at the given path.  This is the main entry point for
    all delete/rm commands in the REPL, which pass a user-provided path or a flag
    to delete the active board.  Returns the deleted entity, or None if the user
    declines deletion.
    """

    # args.path | args.board (flag to delete active board) | args.column (flag to delete a column)

    def _confirm(message: str) -> bool:
        # Put to the consumer's own Interaction rather than to the terminal:
        # the REPL prompts on it, and a consumer drawing its own screen asks
        # the way it can.
        return args.force or svc.interaction.confirm(message)

    if svc.working_board is None:
        raise ValueError("No active board; set one with `board` before deleting an board, column, or task")

    if args.board:
        board = svc.working_board
        if _confirm(f"Are you sure you want to delete the active board ({board})?"):
            return svc.delete_board(path=None)
    elif args.column:
        column = svc.get_column(args.column)
        if _confirm(f"Are you sure you want to delete the column '{column.name}'?"):
            return svc.delete_column(path=Slug(args.column))
    elif args.path:
        task = svc.get_task(args.path)
        if _confirm(f"Are you sure you want to delete the task '{task.title}'?"):
            return svc.delete_task(path=task.path)
    else:
        raise ValueError("Delete expects either --board, --column <column> or a <task> path")

    # User declined deletion
    return None
    

def handle_rename_helper(args: argparse.Namespace, svc: KanbanService) -> Board | Column | Task:
    """
    Rename the entity at the given path to a new name.  This is the main
    entry point for all rename commands in the REPL, which pass a user-provided
    """

    # args.path | args.board (flag to rename active board) | args.column (flag to rename a column)
    # args.new_name

    new_name = args.new_name

    if not new_name:
        raise ValueError("New name must be provided for rename operation")

    if svc.working_board is None:
        raise ValueError("No active board; set one with `board` before renaming a board, column, or task")

    if args.board:
        return svc.rename_board(path=None, new_name=new_name)
    elif args.column:
        return svc.rename_column(path=Slug(args.column), new_name=new_name)
    elif args.path:
        return svc.rename_task(path=args.path, new_title=new_name)
    else:
        raise ValueError("Rename expects either --board, --column <column>, or a <task> path")


def handle_info_helper(args: argparse.Namespace, svc: KanbanService) -> Board | Column | Task:
    """
    Return the board, column, or task the command names.  This is the main
    entry point for the `info` command in the REPL, which reads an object
    rather than changing it and which takes the same target arguments as
    `rename` and `delete`: the active board, a named column, or a task by its
    bare slug.
    """

    # args.path | args.board (flag for the active board) | args.column (flag for a column)

    if args.board:
        board = svc.working_board
        if board is None:
            raise ValueError("No active board; set one with `board` first")
        return svc.get_board(board)
    elif args.column:
        return svc.get_column(Slug(args.column))
    elif args.path:
        return svc.get_task(args.path)
    else:
        raise ValueError("Expects either --board, --column <column>, or a <task>")


def handle_create_helper(args: argparse.Namespace, svc: KanbanService) -> Board | Column | Task:
    """
    Create a new board, column, or task. This is the main entry point for
    all create/new/n commands in the REPL. The parser guarantees exactly one
    of `args.new_board`, `args.new_column`, or `args.column` is set (mutex
    group). Board creation does not require an active board; column creation
    requires an active board; task creation requires either an active board
    or a slash-prefixed column path.
    """

    # args.new_board  | args.new_column  | args.column (existing column for a new task)
    # args.title      | args.edit        | task update args

    if args.new_board:
        return svc.create_board(args.new_board)

    if args.new_column:
        if svc.working_board is None:
            raise ValueError("No active board; set one with `board` before creating a column")
        return svc.create_column(None, args.new_column)

    if args.column:
        if not args.title:
            raise ValueError("Task title is required")
        if svc.working_board is None and not args.column.startswith("/"):
            raise ValueError("No active board; set one with `board` before creating a task")
        params = TaskCreateParams(
            title=args.title,
            assigned_to=args.assigned_to,
            priority=parse_priority(args),
            tags=args.tags or [],
            due_date=args.due_date,
            created_by=args.created_by,
            description=args.description,
        )
        # The selected task is what `new-task.insert` places the new one against
        # when set to above/below.  It is empty in the REPL, which has no
        # selection, and set by the TUI when the command comes from its bar.
        result = svc.create_task(Slug(args.column), params, svc.selection.task)
        if args.edit:
            result = svc.edit_task(Path(result.path))
        return result

    raise ValueError("Create expects either --board NAME, --column NAME, or a <column> <title>")