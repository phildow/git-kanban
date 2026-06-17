
# TODO: add comment

from models import Board, Column, Task
from services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams

def handle_list(args: argparse.Namespace, svc: KanbanService) -> tuple[list[Board | Column | Task], type]:
    """
    List the contents at the path applying filters and sort.  This is
    the main entry point for all list/ls commands in the REPL, which pass a
    user-provided path that may be absolute or relative to the active
    context.
    """
    path = getattr(args, "path", "") or ""
    board, column, _ = svc.resolve_path_into_components(path)

    filter = getattr(args, "filter", None)
    sort = getattr(args, "sort", None)
    reverse = getattr(args, "reverse", False)
    
    if board and column:
        return svc.list_tasks(path=f"/{board}/{column}", filter=filter, sort=sort, reverse=reverse), Task
    elif board and not column:
        return svc.list_columns(board=board, sort=sort, reverse=reverse), Column
    elif not board and not column:
        return svc.list_boards(sort=sort, reverse=reverse), Board
       

def handle_delete(args: argparse.Namespace, svc: KanbanService) -> type:
    """
    Delete the entity at the given path.  This is the main entry point for
    all delete/rm commands in the REPL, which pass a user-provided path that
    may be absolute or relative to the active context.
    """
    path = getattr(args, "path", "") or ""
    board, column, task = svc.resolve_path_into_components(path)

    if board and column and task:
        svc.delete_task(path=f"/{board}/{column}/{task}")
        return Task
    elif board and column and not task:
        svc.delete_column(path=f"/{board}/{column}")
        return Column
    elif board and not column:
        svc.delete_board(board)
        return Board
    elif not board and not column:
        raise ValueError("Cannot delete without a board name: {}".format(path))

def repl_handle_move_task(args: argparse.Namespace, svc: KanbanService) -> None:
    """
    Move the entity at the given path to a new location.  This is the main
    entry point for all move commands in the REPL, which pass a user-provided
    path that may be absolute or relative to the active context.

    It is only possible to move a task to another column on the current board.
    
    """
    path = getattr(args, "path", "") or ""
    dest = getattr(args, "dest", "") or ""
    board, column, task = svc.resolve_path_into_components(path)
    dest_board, dest_column, dest_task = svc.resolve_path_into_components(dest)

    if board and column and task:
        svc.move_task(path=f"/{board}/{column}/{task}", dest_board=dest_board, dest_column=dest_column)
    elif board and column and not task:
        svc.move_column(path=f"/{board}/{column}", dest_board=dest_board)
    elif board and not column and not task:
        svc.move_task(path=f"{task}", dest_board=dest_board)
    elif not board and not column and not task:
        raise ValueError("Cannot move without a board name: {}".format(path))