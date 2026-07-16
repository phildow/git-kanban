
"""
A service that provides handlers for REPL commands that reuse the same logic as the CLI handlers, 
but with a different interface for passing arguments and rendering results.

Designed to keep the base handlers lean. The main entry points for the REPL are in repl/handlers.py, 
which call into this service as needed to perform more complex operations.
"""

import argparse
from datetime import datetime, timezone

from ..models import Board, Column, Priority, Task, TaskFilter
from ..services.kanban import KanbanService
from ..utils.shell import prompt_for_confirmation


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _parse_priority(args: argparse.Namespace) -> Priority | None:
    """Return the --priority argument as a Priority, or None if not provided."""
    return Priority(args.priority) if args.priority else None


def _build_task_filter(args: argparse.Namespace) -> TaskFilter:
    """Build a TaskFilter from parsed CLI/REPL filter arguments."""
    def _parse_date(s: str | None) -> datetime | None:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

    return TaskFilter(
        assigned_to=args.assigned_to,
        priority=_parse_priority(args),
        tags=args.tags or [],
        due_before=_parse_date(args.due_before),
        due_after=_parse_date(args.due_after),
        created_by=args.created_by,
        exclude_columns=args.column or [],
    )

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def handle_list_helper(args: argparse.Namespace, svc: KanbanService) -> list[Task]:
    """
    List tasks scoped to a board or board/column path, falling back to the
    current user context.  This is the main entry point for all list/ls
    commands in the REPL.  A board-only scope returns every task in that
    board, across all columns.  Raises if no board can be resolved from
    the path or context.
    """
    path = args.path or ""
    board, column, _ = svc.path_components(path)

    filter = _build_task_filter(args)
    sort = args.sort
    reverse = args.reverse

    if board is None:
        raise ValueError("No active board; provide a board or board/column, or set one with `cd`")

    task_path = f"/{board}/{column}" if column else f"/{board}"
    return svc.get_tasks(path=task_path, filter=filter, sort=sort, reverse=reverse)


def handle_task_list_helper(args: argparse.Namespace, svc: KanbanService) -> list[Task]:
    """
    Return tasks scoped by path (a board or board/column path).  This is
    the main entry point for the `tasks` command in the REPL.  When path is
    omitted, falls back to every task in the active board (all columns),
    raising if no board is active.
    """
    path = args.path or ""
    filter = _build_task_filter(args)
    sort = args.sort
    reverse = args.reverse

    if not path:
        board = svc.working_board
        if not board:
            raise ValueError("No active board; provide a board or board/column, or set one with `board`/`cd`")
        return svc.get_tasks(path=f"/{board}", filter=filter, sort=sort, reverse=reverse)

    board, column, _ = svc.path_components(path)
    if board is None:
        raise ValueError(f"Cannot resolve board from: {path}")
    if column:
        return svc.get_tasks(path=f"/{board}/{column}", filter=filter, sort=sort, reverse=reverse)
    return svc.get_tasks(path=f"/{board}", filter=filter, sort=sort, reverse=reverse)


def handle_delete_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, Board | Column | Task] | tuple[None, None]:
    """
    Delete the entity at the given path.  This is the main entry point for
    all delete/rm commands in the REPL, which pass a user-provided path that
    may be absolute or relative to the current context.
    """
    path = args.path or ""
    force = args.force
    board, column, task = svc.path_components(path)

    def _confirm(message: str) -> bool:
        return force or prompt_for_confirmation(message)

    if board and column and task:
        if _confirm(f"Are you sure you want to delete the task '{task}'?"):
            return Task, svc.delete_task(path=f"/{board}/{column}/{task}")
    elif board and column:
        if _confirm(f"Are you sure you want to delete the column '{column}'?"):
            return Column, svc.delete_column(path=f"/{board}/{column}")
    elif board:
        if _confirm(f"Are you sure you want to delete the board '{board}'?"):
            return Board, svc.delete_board(board)
    else:
        raise ValueError("Cannot delete without a board name: {}".format(path))

    # User declined deletion
    return None, None
    

def handle_rename_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, Board | Column | Task]:
    """
    Rename the entity at the given path to a new name.  This is the main
    entry point for all rename commands in the REPL, which pass a user-provided
    """
    path = args.path or ""
    new_name = args.new_name

    if not new_name:
        raise ValueError("New name must be provided for rename operation")

    board, column, task = svc.path_components(path)

    if board and column and task:
        return Task, svc.rename_task(path=f"/{board}/{column}/{task}", new_title=new_name)
    elif board and column:
        return Column, svc.rename_column(path=f"/{board}/{column}", new_name=new_name)
    elif board:
        return Board, svc.rename_board(path=f"/{board}", new_name=new_name)
    else:
        raise ValueError("Cannot rename without a board name: {}".format(path))