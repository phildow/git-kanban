from __future__ import annotations

from datetime import datetime, UTC
from hashlib import new
from os import name
from pathlib import Path
from uuid import UUID, uuid4

from models import Slug, Task, Board, Column
from storage.kanban import (
    KanbanRepository,
    BoardNotFound,
    BoardAlreadyExists,
    ColumnNotFound,
    ColumnAlreadyExists,
    RepositoryAlreadyInitialized,
    TaskNotFound,
    TaskAlreadyExists,
)


class InMemoryRepository(KanbanRepository):
    """
    In-memory repository scaffold.

    Uses simple dict/list containers so behavior can be filled in incrementally
    without touching calling code.
    """

    def __init__(self, root: Path = Path(".")) -> None:
        super().__init__(root)
        self._boards: dict[str, Board] = {}
        self._columns: dict[str, list[Column]] = {}
        self._tasks_by_id: dict[UUID, Task] = {}
        self._task_locations: dict[UUID, tuple[str, str]] = {}
        self._task_filenames: dict[UUID, str] = {}
        self._task_order: dict[tuple[str, str], list[str]] = {}
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

    def get_board(self, slug: Slug) -> Board:
        board = self._boards.get(slug)
        if board is None:
            raise BoardNotFound(slug)
        return board

    def board_exists(self, slug: Slug) -> bool:
        return slug in self._boards

    def create_board(self, name: str, slug: Slug) -> Board:
        uuid = uuid4()

        if self.board_exists(slug):
            raise BoardAlreadyExists(slug)

        board = Board(id=uuid, name=name, slug=slug)
        self._boards[slug] = board
        self._columns[slug] = []
        return board

    def rename_board(self, slug: Slug, new_name: str, new_slug: Slug) -> Board:
        board = self._boards.get(slug)
        if board is None:
            raise BoardNotFound(slug)
        if new_slug != slug and self.board_exists(new_slug):
            raise BoardAlreadyExists(new_slug)

        # No-op rename is valid and keeps insertion order intact.
        if new_name == board.name:
            return board

        # Remove and reinsert under new key to preserve relative order.
        del self._boards[slug]
        board.name = new_name
        board.slug = new_slug
        columns = self._columns.pop(slug, [])
        for column in columns:
            column.board = new_slug
        self._columns[new_slug] = columns
        self._boards[new_slug] = board

        # Update board part of task locations.
        for task_id, (task_board, task_column) in list(self._task_locations.items()):
            if task_board == slug:
                self._task_locations[task_id] = (new_slug, task_column)

        # Keep Task.board in sync for tasks that carry location fields.
        for task in self._tasks_by_id.values():
            if task.board == slug:
                task.board = new_slug

        # Remap task order keys to the new board slug.
        for (order_board, order_column) in list(self._task_order.keys()):
            if order_board == slug:
                self._task_order[(new_slug, order_column)] = self._task_order.pop((order_board, order_column))

        return board

    def delete_board(self, slug: Slug) -> None:
        if not self.board_exists(slug):
            raise BoardNotFound(slug)

        del self._boards[slug]
        self._columns.pop(slug, None)

        # Remove all tasks belonging to this board.
        ids_to_delete = [
            task_id
            for task_id, (task_board, _task_column) in self._task_locations.items()
            if task_board == slug
        ]
        for task_id in ids_to_delete:
            del self._tasks_by_id[task_id]
            self._task_locations.pop(task_id, None)
            self._task_filenames.pop(task_id, None)

        for key in [k for k in self._task_order if k[0] == slug]:
            del self._task_order[key]

    # ------------------------------------------------------------------
    # Columns operations
    # ------------------------------------------------------------------

    def get_columns(self, board: Slug) -> list[Column]:
        self.get_board(board)
        return list(self._columns.get(board, []))

    def get_column(self, board: Slug, slug: Slug) -> Column:
        self.get_board(board)
        
        for column in self._columns.get(board, []):
            if column.slug == slug:
                return column
        
        raise ColumnNotFound(board, slug)

    def column_exists(self, board: Slug, slug: Slug) -> bool:
        self.get_board(board)
        return any(column.slug == slug for column in self._columns.get(board, []))

    def create_column(self, board: Slug, name: str, slug: Slug) -> Column:
        self.get_board(board)
        columns = self._columns.setdefault(board, [])
        
        if any(column.name == name for column in columns):
            raise ColumnAlreadyExists(board, name)

        column = Column(id=uuid4(), name=name, slug=slug, board=board, position=len(columns))
        columns.append(column)
        
        return column

    def rename_column(self, board: Slug, slug: Slug, new_name: str, new_slug: Slug) -> Column:
        self.get_board(board)
        column = self.get_column(board, slug)
        columns = self._columns.get(board, [])

        if new_name != column.name and any(c.name == new_name for c in columns):
            raise ColumnAlreadyExists(board, new_name)

        if new_name == column.name:
            return column

        column.name = new_name
        column.slug = new_slug

        # Keep location index in sync.
        for task_id, (task_board, task_column) in list(self._task_locations.items()):
            if task_board == board and task_column == slug:
                self._task_locations[task_id] = (board, new_slug)

        # Keep Task.column in sync when present.
        for task in self._tasks_by_id.values():
            if task.board == board and task.column == slug:
                task.column = new_slug

        # Remap task order key to the new column slug.
        if (board, slug) in self._task_order:
            self._task_order[(board, new_slug)] = self._task_order.pop((board, slug))

        return column

    def reorder_column(self, board: Slug, slug: Slug, position: int) -> list[Column]:
        self.get_board(board)
        columns = self._columns.get(board, [])

        current_index = next((i for i, c in enumerate(columns) if c.slug == slug), None)
        if current_index is None:
            raise ColumnNotFound(board, slug)

        if not columns:
            return columns

        clamped_position = max(0, min(position, len(columns) - 1))
        column = columns.pop(current_index)
        columns.insert(clamped_position, column)

        for i, col in enumerate(columns):
            col.position = i

        return list(columns)

    def delete_column(self, board: Slug, slug: Slug) -> None:
        self.get_board(board)
        columns = self._columns.get(board, [])

        index = next((i for i, c in enumerate(columns) if c.slug == slug), None)
        if index is None:
            raise ColumnNotFound(board, slug)

        columns.pop(index)

        for i, col in enumerate(columns):
            col.position = i

        # Remove tasks in this column.
        ids_to_delete = [
            task_id
            for task_id, (task_board, task_column) in self._task_locations.items()
            if task_board == board and task_column == slug
        ]
        for task_id in ids_to_delete:
            del self._tasks_by_id[task_id]
            self._task_locations.pop(task_id, None)
            self._task_filenames.pop(task_id, None)

        self._task_order.pop((board, slug), None)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    def get_tasks(self, board: Slug | None = None, column: Slug | None = None) -> list[Task]:
        if board is not None:
            self.get_board(board)
            if column is not None:
                self.get_column(board, column)

        # Build a lookup: (board, column, slug) → Task for ordered retrieval.
        by_location: dict[tuple[str, str, str], Task] = {}
        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            task_slug = self._task_filenames.get(task_id, task.slug)
            by_location[(task_board, task_column, task_slug)] = task

        boards = [board] if board is not None else list(self._boards)
        tasks: list[Task] = []
        for b in boards:
            columns = [column] if column is not None else [c.slug for c in self._columns.get(b, [])]
            for col in columns:
                for slug in self._task_order.get((b, col), []):
                    task = by_location.get((b, col, slug))
                    if task is not None:
                        tasks.append(task)

        return tasks

    def get_task(self, board: Slug, column: Slug, filename: Slug) -> Task:
        self.get_board(board)
        self.get_column(board, column)

        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            task_filename = self._task_filenames.get(task_id)
            if task_board == board and task_column == column and task_filename == filename:
                return task

        raise TaskNotFound(f"{board}/{column}/{filename}")

    def task_exists(self, board: Slug, column: Slug, filename: Slug) -> bool:
        self.get_board(board)
        self.get_column(board, column)

        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))
            task_filename = self._task_filenames.get(task_id)
            if task_board == board and task_column == column and task_filename == filename:
                return True
        return False

    def create_task(self, task: Task, slug: Slug) -> Task:
        if task.board is None:
            raise BoardNotFound("None")
        if task.column is None:
            raise ColumnNotFound(task.board, "None")

        self.get_board(task.board)
        self.get_column(task.board, task.column)

        if self.task_exists(task.board, task.column, slug):
            raise TaskAlreadyExists(task.board, task.column, slug)

        now = datetime.now(UTC)
        if task.created_at is None:
            task.created_at = now
        if task.updated_at is None:
            task.updated_at = task.created_at

        self._tasks_by_id[task.id] = task
        self._task_locations[task.id] = (task.board, task.column)
        self._task_filenames[task.id] = slug
        task.slug = slug
        self._task_order.setdefault((task.board, task.column), []).append(slug)
        return task

    def update_task(self, task: Task, slug: Slug) -> Task:
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
            new_filename = task.slug
            if other_board == existing_board and other_column == existing_column and other_filename == new_filename:
                raise TaskAlreadyExists(existing_board, existing_column, new_filename)

        task.board = existing_board
        task.column = existing_column
        task.created_at = existing.created_at
        task.updated_at = datetime.now(UTC)

        old_slug = self._task_filenames.get(task.id)
        self._tasks_by_id[task.id] = task
        self._task_locations[task.id] = (existing_board, existing_column)
        self._task_filenames[task.id] = task.slug
        task.slug = self._task_filenames[task.id]

        if old_slug is not None and old_slug != task.slug:
            order = self._task_order.get((existing_board, existing_column), [])
            if old_slug in order:
                order[order.index(old_slug)] = task.slug

        return task

    def move_task(self, task: Task, column: Slug) -> Task:
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

            src_order = self._task_order.get((task.board, stored.column), [])
            if slug in src_order:
                src_order.remove(slug)
            self._task_order.setdefault((task.board, column), []).append(slug)

            stored.column = column
            self._task_locations[task.id] = (task.board, column)

        stored.updated_at = datetime.now(UTC)
        return stored

    def reorder_task(self, task: Task, op: str) -> Task:
        stored = self._tasks_by_id.get(task.id)
        if stored is None:
            raise TaskNotFound(str(task.id))

        board = stored.board
        column = stored.column
        if board is None or column is None:
            raise TaskNotFound(str(task.id))

        slug = self._task_filenames.get(task.id, task.slug)
        order = self._task_order.get((board, column), [])

        if slug not in order:
            raise TaskNotFound(f"{board}/{column}/{slug}")

        current_index = order.index(slug)

        if op == "up":
            new_index = max(0, current_index - 1)
        elif op == "down":
            new_index = min(len(order) - 1, current_index + 1)
        elif op == "top":
            new_index = 0
        elif op == "bottom":
            new_index = len(order) - 1
        else:
            raise ValueError(f"Invalid operation '{op}': must be one of 'up', 'down', 'top', 'bottom'")

        if new_index != current_index:
            order.insert(new_index, order.pop(current_index))

        stored.updated_at = datetime.now(UTC)
        return stored
    
    def delete_task(self, task: Task) -> None:
        task_id = task.id
        if task_id not in self._tasks_by_id:
            raise TaskNotFound(str(task_id))

        board, column = self._task_locations.get(task_id, (task.board, task.column))
        slug = self._task_filenames.get(task_id, task.slug)
        order = self._task_order.get((board, column), [])
        if slug in order:
            order.remove(slug)

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
