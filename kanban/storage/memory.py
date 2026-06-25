from __future__ import annotations

from datetime import date, datetime, timedelta, UTC
from pathlib import Path
import random
import re
from typing import Optional
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import (
    KanbanRepository,
    BoardNotFound,
    BoardAlreadyExists,
    ColumnNotFound,
    ColumnAlreadyExists,
    TaskNotFound,
    TaskAlreadyExists,
)
from utils.str import kebab_case


class InMemoryRepository(KanbanRepository):
    """
    In-memory repository scaffold.

    Uses simple dict/list containers so behavior can be filled in incrementally
    without touching calling code.
    """

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._boards: dict[str, Board] = {}
        self._columns: dict[str, list[Column]] = {}
        self._tasks_by_id: dict[UUID, Task] = {}
        self._task_locations: dict[UUID, tuple[str, str]] = {}
        self._task_filenames: dict[UUID, str] = {}
        self._config: dict[str, str] = {}
        self._userdata: dict[str, str] = {}

        self._is_initialized = False

    # ------------------------------------------------------------------
    # Filepaths
    # ------------------------------------------------------------------

    @property
    def kanban_dir(self) -> Path | None:
        return None

    @property
    def userdata_file(self) -> Path | None:
        return None

    # ---------------------------------------------------------------------------
    # Initialization (setup)
    # ---------------------------------------------------------------------------
    
    def init_storage(self) -> None:
        if self.is_initialized:
           raise ValueError("Kanban is already initialized")
        else:
            self._is_initialized = True
        
    @property
    def is_initialized(self) -> bool:
        """Return True if the repository is already initialized at the current path."""
        return self._is_initialized

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    def get_boards(self) -> list[Board]:
        return list(self._boards.values())

    def get_board(self, name: str) -> Board:
        board = self._boards.get(name)
        if board is None:
            raise BoardNotFound(name)
        return board

    def board_exists(self, name: str) -> bool:
        return name in self._boards

    def create_board(self, name: str) -> Board:
        slug = kebab_case(name)
        uuid = uuid4()

        if self.board_exists(name):
            raise BoardAlreadyExists(name)

        board = Board(id=uuid, name=name, slug=slug)
        self._boards[name] = board
        self._columns[name] = []
        return board

    def rename_board(self, name: str, new_name: str) -> Board:
        board = self._boards.get(name)
        if board is None:
            raise BoardNotFound(name)
        if new_name != name and self.board_exists(new_name):
            raise BoardAlreadyExists(new_name)

        # No-op rename is valid and keeps insertion order intact.
        if new_name == name:
            return board

        # Remove and reinsert under new key to preserve relative order.
        del self._boards[name]
        board.name = new_name
        columns = self._columns.pop(name, [])
        for column in columns:
            column.board = new_name
        self._columns[new_name] = columns
        self._boards[new_name] = board

        # Update board part of task locations.
        for task_id, (task_board, task_column) in list(self._task_locations.items()):
            if task_board == name:
                self._task_locations[task_id] = (new_name, task_column)

        # Keep Task.board in sync for tasks that carry location fields.
        for task in self._tasks_by_id.values():
            if task.board == name:
                task.board = new_name

        return board

    def delete_board(self, name: str) -> None:
        if not self.board_exists(name):
            raise BoardNotFound(name)

        del self._boards[name]
        self._columns.pop(name, None)

        # Remove all tasks belonging to this board.
        ids_to_delete = [
            task_id
            for task_id, (task_board, _task_column) in self._task_locations.items()
            if task_board == name
        ]
        for task_id in ids_to_delete:
            del self._tasks_by_id[task_id]
            self._task_locations.pop(task_id, None)
            self._task_filenames.pop(task_id, None)

    # ------------------------------------------------------------------
    # Columns operations
    # ------------------------------------------------------------------

    def get_columns(self, board: str) -> list[Column]:
        self.get_board(board)
        return list(self._columns.get(board, []))

    def get_column(self, board: str, name: str) -> Column:
        self.get_board(board)
        for column in self._columns.get(board, []):
            if column.name == name:
                return column
        raise ColumnNotFound(board, name)

    def column_exists(self, board: str, name: str) -> bool:
        self.get_board(board)
        return any(column.name == name for column in self._columns.get(board, []))

    def create_column(self, board: str, name: str) -> Column:
        slug = kebab_case(name)
        self.get_board(board)
        columns = self._columns.setdefault(board, [])
        if any(column.name == name for column in columns):
            raise ColumnAlreadyExists(board, name)

        column = Column(id=uuid4(), name=name, slug=slug, board=board, position=len(columns))
        columns.append(column)
        return column

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        self.get_board(board)
        column = self.get_column(board, name)
        columns = self._columns.get(board, [])

        if new_name != name and any(c.name == new_name for c in columns):
            raise ColumnAlreadyExists(board, new_name)

        if new_name == name:
            return column

        column.name = new_name
        column.slug = kebab_case(new_name)

        # Keep location index in sync.
        for task_id, (task_board, task_column) in list(self._task_locations.items()):
            if task_board == board and task_column == name:
                self._task_locations[task_id] = (board, new_name)

        # Keep Task.column in sync when present.
        for task in self._tasks_by_id.values():
            if task.board == board and task.column == name:
                task.column = new_name

        return column

    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        self.get_board(board)
        columns = self._columns.get(board, [])

        current_index = next((i for i, c in enumerate(columns) if c.name == name), None)
        if current_index is None:
            raise ColumnNotFound(board, name)

        if not columns:
            return columns

        clamped_position = max(0, min(position, len(columns) - 1))
        column = columns.pop(current_index)
        columns.insert(clamped_position, column)

        for i, col in enumerate(columns):
            col.position = i

        return list(columns)

    def delete_column(self, board: str, name: str) -> None:
        self.get_board(board)
        columns = self._columns.get(board, [])

        index = next((i for i, c in enumerate(columns) if c.name == name), None)
        if index is None:
            raise ColumnNotFound(board, name)

        columns.pop(index)

        for i, col in enumerate(columns):
            col.position = i

        # Remove tasks in this column.
        ids_to_delete = [
            task_id
            for task_id, (task_board, task_column) in self._task_locations.items()
            if task_board == board and task_column == name
        ]
        for task_id in ids_to_delete:
            del self._tasks_by_id[task_id]
            self._task_locations.pop(task_id, None)
            self._task_filenames.pop(task_id, None)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def get_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
    ) -> list[Task]:
        if board is not None:
            self.get_board(board)
            if column is not None:
                self.get_column(board, column)

        tasks: list[Task] = []
        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            if board is not None and task_board != board:
                continue
            if column is not None and task_column != column:
                continue
            tasks.append(task)

        return tasks

    def get_task(self, board: str, column: str, filename: str) -> Task:
        self.get_board(board)
        self.get_column(board, column)

        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            task_filename = self._task_filenames.get(task_id)
            if task_board == board and task_column == column and task_filename == filename:
                return task

        raise TaskNotFound(f"{board}/{column}/{filename}")

    def task_exists(self, board: str, column: str, filename: str) -> bool:
        self.get_board(board)
        self.get_column(board, column)

        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            task_filename = self._task_filenames.get(task_id)
            if task_board == board and task_column == column and task_filename == filename:
                return True
        return False

    def create_task(self, task: Task, filename: str) -> Task:
        if task.board is None:
            raise BoardNotFound("None")
        if task.column is None:
            raise ColumnNotFound(task.board, "None")

        self.get_board(task.board)
        self.get_column(task.board, task.column)

        if self.task_exists(task.board, task.column, filename):
            raise TaskAlreadyExists(task.board, task.column, filename)

        now = datetime.now(UTC)
        if task.created_at is None:
            task.created_at = now
        if task.updated_at is None:
            task.updated_at = task.created_at

        self._tasks_by_id[task.id] = task
        self._task_locations[task.id] = (task.board, task.column)
        self._task_filenames[task.id] = filename
        task.slug = filename
        return task

    def update_task(self, task: Task) -> Task:
        existing = self._tasks_by_id.get(task.id)
        if existing is None:
            raise TaskNotFound(str(task.id))

        existing_board, existing_column = self._task_locations.get(task.id, (existing.board, existing.column))
        if existing_board is None or existing_column is None:
            raise TaskNotFound(str(task.id))

        # board/column are read-only for update; check title collision in current location
        for other_id, other_task in self._tasks_by_id.items():
            if other_id == task.id:
                continue
            other_board, other_column = self._task_locations.get(other_id, (other_task.board, other_task.column))
            other_filename = self._task_filenames.get(other_id, "")
            new_filename = kebab_case(task.title)
            if other_board == existing_board and other_column == existing_column and other_filename == new_filename:
                raise TaskAlreadyExists(existing_board, existing_column, new_filename)

        task.board = existing_board
        task.column = existing_column
        task.created_at = existing.created_at
        task.updated_at = datetime.now(UTC)

        self._tasks_by_id[task.id] = task
        self._task_locations[task.id] = (existing_board, existing_column)
        self._task_filenames[task.id] = kebab_case(task.title)
        task.slug = self._task_filenames[task.id]
        return task

    def move_task(self, task: Task, column: str) -> Task:
        stored = self._tasks_by_id.get(task.id)
        if stored is None:
            raise TaskNotFound(str(task.id))

        self.get_column(task.board, column)

        if stored.column != column:
            slug = self._task_filenames.get(task.id, task.slug)
            for other_id, other_task in self._tasks_by_id.items():
                if other_id == task.id:
                    continue
                other_column = self._task_locations.get(other_id, (None, other_task.column))[1]
                if other_task.board == task.board and other_column == column and self._task_filenames.get(other_id) == slug:
                    raise TaskAlreadyExists(task.board, column, slug)

            stored.column = column
            self._task_locations[task.id] = (task.board, column)

        stored.updated_at = datetime.now(UTC)
        return stored

    def delete_task(self, task: Task) -> None:
        task_id = task.id
        if task_id not in self._tasks_by_id:
            raise TaskNotFound(str(task_id))

        del self._tasks_by_id[task_id]
        self._task_locations.pop(task_id, None)
        self._task_filenames.pop(task_id, None)

    # ------------------------------------------------------------------
    # Config, user data, and metadata
    # ------------------------------------------------------------------

    # Config

    def get_config(self, keypath: str) -> str | None:
        return self._config.get(keypath)

    def set_config(self, keypath: str, value: str | None) -> None:
        if value is None:
            self._config.pop(keypath, None)
        else:
            self._config[keypath] = value

    # User data
    
    def get_userdata(self, keypath: str) -> str | None:
        return self._userdata.get(keypath)

    def set_userdata(self, keypath: str, value: str | None) -> None:
        if value is None:
            self._userdata.pop(keypath, None)
        else:
            self._userdata[keypath] = value
