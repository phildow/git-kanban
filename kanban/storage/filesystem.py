from __future__ import annotations

from pathlib import Path
import shutil
from typing import Optional
from uuid import UUID

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import KanbanRepository, BoardNotFound, BoardAlreadyExists, ColumnAlreadyExists, ColumnNotFound


class FilesystemRepository(KanbanRepository):
    """Filesystem-backed repository scaffold.

    This class is intentionally scaffold-only for now. Each method is wired
    with the final interface and can be incrementally implemented.
    """

    def __init__(self, root: Path) -> None:
        super().__init__(root)

    # ------------------------------------------------------------------
    # Filepaths
    # ------------------------------------------------------------------

    @property
    def kanban_dir(self) -> Path:
        return self.root / ".kanban"

    @property
    def kanban_store_dir(self) -> Path:
        return self.root / ".kanban-store"

    @property
    def boards_dir(self) -> Path:
        return self.kanban_store_dir / "boards"
    
    @property
    def config_file(self) -> Path:
        return self.kanban_dir / "config"

    @property
    def index_file(self) -> Path:
        return self.kanban_dir / "index.db"

    # ------------------------------------------------------------------
    # Bootstrap and initialization
    # ------------------------------------------------------------------

    # Bootstrap
    def init_storage(self, default_board: str = "main") -> None:
        if self.is_initialized:
            raise ValueError("Kanban is already initialized")

        kanban_dir = self.kanban_dir
        kanban_dir.mkdir()
            
        kanban_store_dir = self.kanban_store_dir
        kanban_store_dir.mkdir()
        
        self.config_file.touch()
        self.index_file.touch()

        boards_dir = self.boards_dir
        boards_dir.mkdir()
        (boards_dir / ".metadata").touch()

    def bootstrap(self) -> list[Task]:
        raise NotImplementedError()

    @property
    def is_initialized(self) -> bool:
        return self.kanban_dir.exists() and self.kanban_store_dir.exists()

    # Board operations
    def get_boards(self) -> list[Board]:
        return [
            Board(name=entry.name)
            for entry in sorted(self.boards_dir.iterdir())
            if entry.is_dir() and not entry.name.startswith(".")
        ]

    def get_board(self, name: str) -> Board:
        board_path = self.boards_dir / name
        if not board_path.is_dir() or name.startswith("."):
            raise BoardNotFound(name)
        return Board(name=name)

    def board_exists(self, name: str) -> bool:
        board_path = self.boards_dir / name
        return board_path.is_dir() and not name.startswith(".")

    def create_board(self, name: str) -> Board:
        if self.board_exists(name):
            raise BoardAlreadyExists(name)
        (self.boards_dir / name).mkdir()
        return Board(name=name, columns=[])

    def rename_board(self, name: str, new_name: str) -> Board:
        if not self.board_exists(name):
            raise BoardNotFound(name)
        if self.board_exists(new_name):
            raise BoardAlreadyExists(new_name)
        (self.boards_dir / name).rename(self.boards_dir / new_name)
        return Board(name=new_name)

    def delete_board(self, name: str) -> None:
        if not self.board_exists(name):
            raise BoardNotFound(name)
        shutil.rmtree(self.boards_dir / name)

    # Column operations
    def get_columns(self, board: str) -> list[Column]:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        board_path = self.boards_dir / board
        return [
            Column(name=entry.name, board=board, position=i)
            for i, entry in enumerate(sorted(board_path.iterdir()))
            if entry.is_dir() and not entry.name.startswith(".")
        ]

    # TODO: implement sorted in a metadata file to avoid relying on filesystem ordering
    def get_column(self, board: str, name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        if not column_path.is_dir() or name.startswith("."):
            raise ColumnNotFound(board, name)
        task_count = sum(
            1 for e in column_path.iterdir()
            if e.is_file() and not e.name.startswith(".")
        )
        siblings = sorted(
            e.name for e in (self.boards_dir / board).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )
        position = siblings.index(name)
        return Column(name=name, board=board, position=position, task_count=task_count)

    def column_exists(self, board: str, name: str) -> bool:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        return column_path.is_dir() and not name.startswith(".")

    def create_column(self, board: str, name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        if column_path.exists():
            raise ColumnAlreadyExists(board, name)
        column_path.mkdir()
        position = len([e for e in (self.boards_dir / board).iterdir() if e.is_dir() and not e.name.startswith(".")]) - 1
        return Column(name=name, board=board, position=position)

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, name):
            raise ColumnNotFound(board, name)
        if self.column_exists(board, new_name):
            raise ColumnAlreadyExists(board, new_name)
        (self.boards_dir / board / name).rename(self.boards_dir / board / new_name)
        return self.get_column(board, new_name)

    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        raise NotImplementedError()

    def delete_column(self, board: str, name: str) -> None:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, name):
            raise ColumnNotFound(board, name)
        shutil.rmtree(self.boards_dir / board / name)

    # Task operations
    def get_tasks(
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
