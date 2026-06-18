from __future__ import annotations

from pathlib import Path
from typing import Optional
from uuid import UUID

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import KanbanRepository


class FilesystemRepository(KanbanRepository):
    """Filesystem-backed repository scaffold.

    This class is intentionally scaffold-only for now. Each method is wired
    with the final interface and can be incrementally implemented.
    """

    def __init__(self, root: Path = Path(".")) -> None:
        self.root = root

    # Bootstrap
    def init_storage(self, default_board: str = "main") -> None:
        raise NotImplementedError()

    def is_initialized(self) -> bool:
        raise NotImplementedError()

    # Board operations
    def list_boards(self) -> list[Board]:
        raise NotImplementedError()

    def get_board(self, name: str) -> Board:
        raise NotImplementedError()

    def board_exists(self, name: str) -> bool:
        raise NotImplementedError()

    def create_board(self, name: str) -> Board:
        raise NotImplementedError()

    def rename_board(self, name: str, new_name: str) -> Board:
        raise NotImplementedError()

    def delete_board(self, name: str) -> None:
        raise NotImplementedError()

    # Column operations
    def list_columns(self, board: str) -> list[Column]:
        raise NotImplementedError()

    def get_column(self, board: str, name: str) -> Column:
        raise NotImplementedError()

    def column_exists(self, board: str, name: str) -> bool:
        raise NotImplementedError()

    def create_column(self, board: str, name: str) -> Column:
        raise NotImplementedError()

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        raise NotImplementedError()

    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        raise NotImplementedError()

    def delete_column(self, board: str, name: str) -> None:
        raise NotImplementedError()

    # Task operations
    def list_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
        filter: Optional[TaskFilter] = None,
    ) -> list[Task]:
        raise NotImplementedError()

    def get_task_by_id(self, task_id: UUID) -> Task:
        raise NotImplementedError()

    def find_tasks_by_title(self, title: str, board: Optional[str] = None) -> list[Task]:
        raise NotImplementedError()

    def get_task(self, board: str, column: str, filename: str) -> Task:
        raise NotImplementedError()

    def task_exists(self, board: str, column: str, filename: str) -> bool:
        raise NotImplementedError()

    def create_task(self, task: Task, filename: str) -> Task:
        raise NotImplementedError()

    def update_task(self, task: Task) -> Task:
        raise NotImplementedError()

    def move_task(self, task_id: UUID, dest_board: str, dest_column: str) -> Task:
        raise NotImplementedError()

    def delete_task(self, task_id: UUID) -> None:
        raise NotImplementedError()

    # Search
    def search_tasks(self, query: str, filter: Optional[TaskFilter] = None) -> list[Task]:
        raise NotImplementedError()

    # Config
    def get_config(self, key: str) -> Optional[str]:
        raise NotImplementedError()

    def set_config(self, key: str, value: str) -> None:
        raise NotImplementedError()
