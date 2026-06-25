
"""
A service that provides handlers for REPL commands that reuse the same logic as the CLI handlers, 
but with a different interface for passing arguments and rendering results.

Designed to keep the base handlers lean. The main entry points for the REPL are in repl/handlers.py, 
which call into this service as needed to perform more complex operations.
"""

import argparse
from datetime import datetime, timezone

from models import Board, Column, Task, TaskFilter
from services.kanban import KanbanService
from utils.shell import prompt_for_confirmation

def _build_task_filter(args: argparse.Namespace) -> TaskFilter:
    """Build a TaskFilter from parsed CLI/REPL filter arguments."""
    def _parse_date(s: str | None) -> datetime | None:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

    return TaskFilter(
        assigned_to=getattr(args, "assigned_to", None),
        priority=getattr(args, "priority", None),
        tags=getattr(args, "tags", None) or [],
        due_before=_parse_date(getattr(args, "due_before", None)),
        due_after=_parse_date(getattr(args, "due_after", None)),
        created_by=getattr(args, "created-by", None),
    )


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
       

def handle_delete_helper(args: argparse.Namespace, svc: KanbanService) -> type:
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
            svc.delete_task(path=f"/{board}/{column}/{task}")
            return Task
    elif board and column:
        if _confirm(f"Are you sure you want to delete the column '{column}'?"):
            svc.delete_column(path=f"/{board}/{column}")
            return Column
    elif board:
        if _confirm(f"Are you sure you want to delete the board '{board}'?"):
            svc.delete_board(board)
            return Board
    else:
        raise ValueError("Cannot delete without a board name: {}".format(path))

    # User declined deletion
    return None
    

def handle_move_helper(args: argparse.Namespace, svc: KanbanService) -> tuple[type, Task | Column | Board]:
    """
    Move the entity at the given path to a new location.  This is the main
    entry point for all move commands in the REPL, which pass a user-provided
    path that may be absolute or relative to the current context.

    It is only possible to move a task to another column on the current board.
    
    """
    path = getattr(args, "path", "") or ""
    dest = getattr(args, "dest", "") or ""
    board, column, task = svc.path_components(path)
    dest_board, dest_column, dest_task = svc.path_components(dest)

    if board and column and task:
        svc.move_task(path=f"/{board}/{column}/{task}", dest_board=dest_board, dest_column=dest_column)
        return Task, svc.get_task(path=f"/{board}/{column}/{task}")
    elif board and column and not task:
        svc.move_column(path=f"/{board}/{column}", dest_board=dest_board)
        return Column, svc.get_column(path=f"/{board}/{column}")
    elif board and not column and not task:
        svc.move_task(path=f"/{board}/{task}", dest_board=dest_board)
        return Task, svc.get_task(path=f"/{board}/{task}")
    elif not board and not column and not task:
        raise ValueError("Cannot move without a board name: {}".format(path))
    