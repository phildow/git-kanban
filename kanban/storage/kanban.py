"""
kanban/repository.py

Abstract base class for the Kanban repository layer.

All domain services depend on this interface only. Concrete implementations
(FilesystemRepository, InMemoryRepository) are injected at startup — nothing
in the domain layer imports a concrete class.

Conventions
-----------
- Methods return domain dataclasses (Task, Board, Column) or None/lists thereof.
- Raise repository exceptions (BoardNotFound, TaskNotFound, etc.) on lookup
  failures, never return None for a required entity.
- Raise Duplicate* exceptions on create/rename collisions.
- Callers are responsible for sequencing calls that must be atomic. The
  repository makes no transactional guarantees across calls.
- `board-name` and `column-name` are the human-readable slug used as the
  directory name (e.g. "my-project", "in-progress"). They are the stable
  address within a board; renaming a column changes its slug.
- Tasks preserve their UUID across renames and moves. The filename is derived from the
  title but is not the source of truth for identity.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from models import UserContext, Board, Column, Task, TaskFilter


# ---------------------------------------------------------------------------
# Repository exceptions
#
# Domain services catch these and re-raise as domain exceptions when
# appropriate. They are never surfaced directly to the CLI.
# ---------------------------------------------------------------------------

class RepositoryError(Exception):
    """Base class for all repository exceptions."""


class BoardNotFound(RepositoryError):
    def __init__(self, name: str):
        super().__init__(f"Board not found: {name!r}")
        self.name = name


class BoardAlreadyExists(RepositoryError):
    def __init__(self, name: str):
        super().__init__(f"Board already exists: {name!r}")
        self.name = name


class ColumnNotFound(RepositoryError):
    def __init__(self, board: str, name: str):
        super().__init__(f"Column not found: {board!r}/{name!r}")
        self.board = board
        self.name = name


class ColumnAlreadyExists(RepositoryError):
    def __init__(self, board: str, name: str):
        super().__init__(f"Column already exists: {board!r}/{name!r}")
        self.board = board
        self.name = name


class TaskNotFound(RepositoryError):
    def __init__(self, identifier: str):
        super().__init__(f"Task not found: {identifier!r}")
        self.identifier = identifier


class TaskAlreadyExists(RepositoryError):
    def __init__(self, board: str, column: str, title: str):
        super().__init__(f"Task already exists: {board!r}/{column!r}/{title!r}")
        self.board = board
        self.column = column
        self.title = title


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class KanbanRepository(ABC):
    """
    Storage-agnostic interface for all kanban persistence operations.

    Implementors must provide every abstract method. The two concrete
    implementations are:

    - FilesystemRepository  — production; boards/columns/tasks on disk,
                              SQLite cache for search.
    - InMemoryRepository    — testing; all state in dicts/lists,
                              no I/O whatsoever.
    """

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    @abstractmethod
    def init(self, default_board: str = "main") -> None:
        """Initialize repository state for first use.

        Implementations should create the default board, set current context,
        and persist any internal initialized sentinel.

        Raises ValueError when already initialized.
        """

    @abstractmethod
    def is_initialized(self) -> bool:
        """Return True if the repository is already initialized at the current path."""
        return False

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    @abstractmethod
    def list_boards(self) -> list[Board]:
        """
        Return all boards, each populated with their ordered column list.

        Returns an empty list when no boards exist.
        """

    @abstractmethod
    def get_board(self, name: str) -> Board:
        """
        Return the Board with its ordered column list.

        Raises BoardNotFound if the board does not exist.
        """

    @abstractmethod
    def board_exists(self, name: str) -> bool:
        """Return True when a board with this name exists, else False."""

    @abstractmethod
    def create_board(self, name: str) -> Board:
        """
        Create and return an empty board (no columns).

        Raises BoardAlreadyExists if the name is taken.
        """

    @abstractmethod
    def rename_board(self, name: str, new_name: str) -> Board:
        """
        Rename a board and return the updated Board.

        All tasks' board references are updated to match.

        Raises BoardNotFound if the board does not exist.
        Raises BoardAlreadyExists if new_name is taken.
        """

    @abstractmethod
    def delete_board(self, name: str) -> None:
        """
        Delete a board and all its columns and tasks.

        Raises BoardNotFound if the board does not exist.
        """

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    @abstractmethod
    def list_columns(self, board: str) -> list[Column]:
        """
        Return columns for the given board in display order.

        Raises BoardNotFound if the board does not exist.
        Returns an empty list when the board has no columns.
        """

    @abstractmethod
    def get_column(self, board: str, name: str) -> Column:
        """
        Return a single Column by board and column name.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        """

    @abstractmethod
    def column_exists(self, board: str, name: str) -> bool:
        """
        Return True when the named column exists on the board, else False.

        Raises BoardNotFound if the board does not exist.
        """

    @abstractmethod
    def create_column(self, board: str, name: str) -> Column:
        """
        Append a column to the end of the board's column list and return it.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnAlreadyExists if the name is taken on that board.
        """

    @abstractmethod
    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        """
        Rename a column and return the updated Column.

        All tasks in this column have their column reference updated.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        Raises ColumnAlreadyExists if new_name is taken on that board.
        """

    @abstractmethod
    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        """
        Move the column to the given 0-based position and return the full
        updated column list in new display order.

        Position is clamped to [0, len(columns) - 1].

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        """

    @abstractmethod
    def delete_column(self, board: str, name: str) -> None:
        """
        Delete a column and all its tasks.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        """

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    @abstractmethod
    def list_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
        filter: Optional[TaskFilter] = None,
    ) -> list[Task]:
        """
        Return tasks matching the given scope and optional filter.

        `board` and `column` narrow the scope before the filter is applied:
        - Both None  → search all boards and columns.
        - board only → search all columns within that board.
        - Both set   → search only that specific column.

        Raises BoardNotFound if the named board does not exist.
        Raises ColumnNotFound if the named column does not exist on that board.
        Returns an empty list when the scope contains no matching tasks.
        """

    @abstractmethod
    def get_task_by_id(self, task_id: UUID) -> Task:
        """
        Return a single task by its UUID.

        Raises TaskNotFound if no task with this UUID exists anywhere.
        """

    @abstractmethod
    def find_tasks_by_title(
        self,
        title: str,
        board: Optional[str] = None,
    ) -> list[Task]:
        """
        Return all tasks whose title matches `title` (case-insensitive,
        exact match), optionally scoped to a single board.

        Used by the path-resolution step when a full <board>/<column>/<title>
        path is not given. Callers must handle ambiguity (multiple results)
        by surfacing an error.

        Returns an empty list when no match is found.
        """

    @abstractmethod
    def get_task(self, board: str, column: str, filename: str) -> Task:
        """
        Return a single task by its exact board/column/filename path.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        Raises TaskNotFound if no task with this filename exists in that column.
        """

    @abstractmethod
    def task_exists(self, board: str, column: str, filename: str) -> bool:
        """
        Return True when a task at this exact path exists, else False.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        """

    @abstractmethod
    def create_task(self, task: Task, filename: str) -> Task:
        """
        Persist a new task and return it with any storage-assigned fields
        populated (e.g. created_at / updated_at if the caller left them None).

        The `task.id` must be set by the caller before calling this method.
        The `task.board` and `task.column` must reference an existing board
        and column.
        `filename` is the storage slug (kebab-case) derived from title.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        Raises TaskAlreadyExists if a task with the same filename already
        exists in that column. (Filenames must be unique within a column directory.)
        """

    @abstractmethod
    def update_task(self, task: Task) -> Task:
        """
        Overwrite an existing task's mutable fields (title, assignee,
        priority, due_date, tags, body) and return the updated Task.

        Locates the task by `task.id`. If the title has changed, the
        underlying filename is renamed to match.

        `task.board` and `task.column` are treated as read-only here;
        use move_task to change location.

        `updated_at` is set to the current UTC time by the repository.

        Raises TaskNotFound if no task with `task.id` exists.
        Raises TaskAlreadyExists if the new title collides with an existing
        task in the same column.
        """

    @abstractmethod
    def move_task(
        self,
        task_id: UUID,
        dest_board: str,
        dest_column: str,
    ) -> Task:
        """
        Move a task to a different column (on the same or different board)
        and return the updated Task.

        The task's UUID and all metadata are preserved. `updated_at` is
        refreshed.

        Raises TaskNotFound if no task with `task_id` exists.
        Raises BoardNotFound if `dest_board` does not exist.
        Raises ColumnNotFound if `dest_column` does not exist on `dest_board`.
        Raises TaskAlreadyExists if a task with the same title already exists
        in the destination column.
        """

    @abstractmethod
    def delete_task(self, task_id: UUID) -> None:
        """
        Delete a task by UUID.

        Raises TaskNotFound if no task with this UUID exists.
        """

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @abstractmethod
    def search_tasks(
        self,
        query: str,
        filter: Optional[TaskFilter] = None,
    ) -> list[Task]:
        """
        Full-text search across task titles and bodies, returning tasks
        ranked by relevance.

        `filter` narrows results by metadata fields before ranking.

        The FilesystemRepository starts with a linear scan of markdown files;
        this is later backed by the SQLite FTS5 cache when the data model
        stabilises. The InMemoryRepository may do a simple substring match.

        Returns an empty list when no tasks match.
        """

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @abstractmethod
    def get_config(self, key: str) -> Optional[str]:
        """
        Return the value for the given config key, or None if not set.

        Config is stored in `.kanban/.config`.
        """

    @abstractmethod
    def set_config(self, key: str, value: str) -> None:
        """Set a config key to the given value."""

