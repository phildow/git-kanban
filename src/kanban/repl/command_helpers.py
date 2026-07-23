
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

def parse_priority(args: argparse.Namespace) -> Priority | None:
    """Return the --priority argument as a Priority, or None if not provided."""
    priority = args.priority
    return Priority(priority) if priority else None


def build_task_filter(args: argparse.Namespace) -> TaskFilter:
    """Build a TaskFilter from parsed CLI/REPL filter arguments."""
    def _parse_date(s: str | None) -> datetime | None:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

    return TaskFilter(
        assigned_to=args.assigned_to,
        priority=parse_priority(args),
        tags=args.tags or [],
        due_before=_parse_date(args.due_before),
        due_after=_parse_date(args.due_after),
        created_by=args.created_by,
        exclude_columns=args.exclude_columns or [],
    )


def handle_task_list_helper(args: argparse.Namespace, svc: KanbanService) -> list[Task]:
    """
    Return tasks scoped by path (a board or board/column path).  This is
    the main entry point for the `tasks` command in the REPL.  When path is
    omitted, falls back to every task in the active board (all columns),
    raising if no board is active.
    """
    path = args.column
    filter = build_task_filter(args)
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
    all delete/rm commands in the REPL, which pass a user-provided path or a flag
    to delete the active board.  Returns a tuple of (entity_type, deleted_entity) 
    or (None, None) if the user declines deletion.
    """

    # args.path | args.board (flag to rename active board)

    force = args.force

    def _confirm(message: str) -> bool:
        return force or prompt_for_confirmation(message)

    if args.board:
        if _confirm(f"Are you sure you want to delete the board '{args.board}'?"):
            return Board, svc.delete_board(path=None)
    elif args.path is not None:
        board, column, task = svc.path_components(args.path)
        if board and column and task:
            if _confirm(f"Are you sure you want to delete the task '{task}'?"):
                return Task, svc.delete_task(path=f"/{board}/{column}/{task}")
        elif board and column:
            if _confirm(f"Are you sure you want to delete the column '{column}'?"):
                return Column, svc.delete_column(path=f"/{board}/{column}")
        else:
            raise ValueError("Delete expects either -b/--board or a COLUMN[/TASK] path")
    else:
        raise ValueError("Delete expects either -b/--board or a COLUMN[/TASK] path")

    # User declined deletion
    return None, None
    

def handle_rename_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, Board | Column | Task]:
    """
    Rename the entity at the given path to a new name.  This is the main
    entry point for all rename commands in the REPL, which pass a user-provided
    """

    # args.path | args.board (flag to rename active board)
    # args.new_name
    
    new_name = args.new_name

    if not new_name:
        raise ValueError("New name must be provided for rename operation")
    
    if args.board:
        return Board, svc.rename_board(path=None, new_name=new_name)

    if args.path is None:
        raise ValueError("Rename expects either -b/--board or a COLUMN[/TASK] path")

    # TODO: move to service method that can route a path preoperly

    board, column, task = svc.path_components(args.path)

    if board and column and task:
        return Task, svc.rename_task(path=f"/{board}/{column}/{task}", new_title=new_name)
    elif board and column:
        return Column, svc.rename_column(path=f"/{board}/{column}", new_name=new_name)
    else:
        raise ValueError("Rename expects either -b/--board or a COLUMN[/TASK] path")