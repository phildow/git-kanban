
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
    priority = getattr(args, "priority", None)
    return Priority(priority) if priority else None


def _build_task_filter(args: argparse.Namespace) -> TaskFilter:
    """Build a TaskFilter from parsed CLI/REPL filter arguments."""
    def _parse_date(s: str | None) -> datetime | None:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

    return TaskFilter(
        assigned_to=getattr(args, "assigned_to", None),
        priority=_parse_priority(args),
        tags=getattr(args, "tags", None) or [],
        due_before=_parse_date(getattr(args, "due_before", None)),
        due_after=_parse_date(getattr(args, "due_after", None)),
        created_by=getattr(args, "created_by", None),
    )

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def handle_list_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, list[Board | Column | Task]]:
    """
    List the contents at the path applying filters and sort.  This is
    the main entry point for all list/ls commands in the REPL, which pass a
    user-provided path that may be absolute or relative to the current
    context.
    """
    all_tasks = getattr(args, "all_tasks", False)
    path = getattr(args, "path", "") or ""

    board, column, _ = svc.path_components(path)

    filter = _build_task_filter(args)
    sort = getattr(args, "sort", None)
    reverse = getattr(args, "reverse", False)
    
    if all_tasks and board:
        return Task, svc.get_tasks(path=f"/{board}", filter=filter, sort=sort, reverse=reverse)
    elif all_tasks and not board:
        raise ValueError("Cannot list all tasks without a board name")
    
    if board and column:
        return Task, svc.get_tasks(path=f"/{board}/{column}", filter=filter, sort=sort, reverse=reverse)
    elif board and not column and all_tasks:
        return Task, svc.get_tasks(path=f"/{board}", filter=filter, sort=sort, reverse=reverse)
    elif board and not column and not all_tasks:
        return Column, svc.get_columns(board=board, sort=sort, reverse=reverse)
    elif not board and not column:
        return Board, svc.get_boards(sort=sort, reverse=reverse)
       

def handle_delete_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, Board | Column | Task] | tuple[None, None]:
    """
    Delete the entity at the given path.  This is the main entry point for
    all delete/rm commands in the REPL, which pass a user-provided path that
    may be absolute or relative to the current context.
    """
    path = getattr(args, "path", "") or ""
    force = getattr(args, "force", False)
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
    path = getattr(args, "path", "") or ""
    new_name = getattr(args, "new_name", None)

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