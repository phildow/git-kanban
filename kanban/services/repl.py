
from models import Board, Column, Task
from services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams

def handle_list(args: argparse.Namespace, svc: KanbanService) -> list[Board | Column | Task]:
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
        return svc.list_tasks(path=f"{board}/{column}", filter=filter, sort=sort, reverse=reverse), Task
    elif board and not column:
        return svc.list_columns(board=board, sort=sort, reverse=reverse), Column
    elif not board and not column:
        return svc.list_boards(sort=sort, reverse=reverse), Board
       