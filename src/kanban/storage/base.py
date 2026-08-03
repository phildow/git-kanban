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
from pathlib import Path

from ..models import Board, Column, Slug, Task


# ---------------------------------------------------------------------------
# Repository exceptions
#
# Domain services catch these and re-raise as domain exceptions when
# appropriate. They are never surfaced directly to the CLI.
# ---------------------------------------------------------------------------

class RepositoryError(Exception):
    """Base class for all repository exceptions."""


class RepositoryAlreadyInitialized(RepositoryError):
    """Raised when an attempt is made to initialize an already-initialized repository."""
    def __init__(self, path: Path):
        super().__init__(f"Repository already initialized at {path}")
        self.path = path

class BoardNotFound(RepositoryError):
    """Raised when a board lookup fails."""
    def __init__(self, name: str):
        super().__init__(f"Board not found: /{name}")
        self.name = name

class BoardAlreadyExists(RepositoryError):
    """Raised when a board creation fails due to a name collision."""
    def __init__(self, name: str):
        super().__init__(f"Board already exists: /{name}")
        self.name = name

class ColumnNotFound(RepositoryError):
    """Raised when a column lookup fails."""
    def __init__(self, board: str, name: str):
        super().__init__(f"Column not found: /{board}/{name}")
        self.board = board
        self.name = name

class ColumnAlreadyExists(RepositoryError):
    """Raised when a column creation fails due to a name collision."""
    def __init__(self, board: str, name: str):
        super().__init__(f"Column already exists: /{board}/{name}")
        self.board = board
        self.name = name

class TaskNotFound(RepositoryError):
    """Raised when a task lookup fails."""
    def __init__(self, identifier: str):
        super().__init__(f"Task not found: {identifier}")
        self.identifier = identifier

class TaskAlreadyExists(RepositoryError):
    """Raised when a task creation fails due to a name collision."""
    def __init__(self, board: str, column: str, title: str):
        super().__init__(f"Task already exists: /{board}/{column}/{title}")
        self.board = board
        self.column = column
        self.title = title

# ---------------------------------------------------------------------------
# Ordering helpers
# ---------------------------------------------------------------------------

def relative_task_index(
    order:         list[str],
    current_index: int,
    op:            str,
    entry:         str | None,
    identifier:    str,
) -> int:
    """
    Return the index the entry at `current_index` takes when moved `above` or
    `below` `entry`, another entry of the same `order`.

    The result is an index into the order with the moving entry removed, which
    is where both repositories insert it.  What an entry is named is the
    implementation's — a filename on disk, a slug in memory — so the caller
    names it, and `identifier` names it again for the error.

    Raises ValueError when no entry is given to position against, and
    TaskNotFound when it is not one this order holds.
    """
    if entry is None:
        raise ValueError(f"Operation '{op}' requires a task to position against")

    # Positioning a task against itself leaves it where it is.
    if entry == order[current_index]:
        return current_index

    if entry not in order:
        raise TaskNotFound(identifier)

    index = order.index(entry)
    if index > current_index:
        index -= 1

    return index if op == "above" else index + 1


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

    @abstractmethod
    def __init__(self, root: Path) -> None:
        """Initialize the repository. `path` is the root directory for all storage operations."""
        self.root = root

    @property
    @abstractmethod
    def kanban_dir(self) -> Path | None:
        """
        Return the path to the .kanban directory if applicable for this repository type, else None.

        The KanbanService uses this to determine whether to look for a Git repository and config file.
        """
        return None

    @property
    @abstractmethod
    def userdata_file(self) -> Path | None:
        """
        Return the path to the userdata file if applicable for this repository type, else None.
        """
        return None

    # ------------------------------------------------------------------
    # Initialization (Setup)
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """
        Return True if the repository is already initialized at the current path.

        Only the store must exist for a repository to be considered initialized;
        local data is optional.
        """
        return False

    @property
    @abstractmethod
    def has_local_data(self) -> bool:
        """Return True if local data storage exists, or False when the repository has none."""
        return False

    @abstractmethod
    def init_storage(self) -> None:
        """
        Initialize the kanban store for first use. Called by the KanbanService when
        creating a new repository.

        The store holds the boards, columns, and tasks and is the only storage
        required for kanban to operate.

        Do not create the default board/column structure here; the service handles that.
        This method is for storage-specific initialization, such as creating necessary
        directories or files.

        Raises RepositoryAlreadyInitialized when the store already exists.
        """

    @abstractmethod
    def init_local_data(self) -> None:
        """
        Initialize local data storage: config, user data, history, and the index cache.

        Config is written with the default value of every setting that has one
        (see `models.config.CONFIG_DEFAULTS`); a setting already carrying a value
        keeps it.

        Local data is machine-local, disposable, and not required for kanban to
        operate, so implementations are idempotent and never raise when the local
        data already exists.
        """

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    @abstractmethod
    def get_boards(self) -> list[Board]:
        """
        Return all boards, each populated with their ordered column list.

        Returns an empty list when no boards exist.
        """

    @abstractmethod
    def get_board(self, slug: Slug) -> Board:
        """
        Return the Board with its ordered column list.

        Raises BoardNotFound if the board does not exist.
        """

    @abstractmethod
    def board_exists(self, slug: Slug) -> bool:
        """Return True when a board with this slug exists, else False."""

    @abstractmethod
    def create_board(self, name: str, slug: Slug) -> Board:
        """
        Create and return an empty board (no columns).
        
        Raises BoardAlreadyExists if the name is taken.
        """

    @abstractmethod
    def rename_board(self, slug: Slug, new_name: str, new_slug: Slug) -> Board:
        """
        Rename a board and return the updated Board.

        All tasks' board references are updated to match.

        Raises BoardNotFound if the board does not exist.
        Raises BoardAlreadyExists if new_name is taken.
        """

    @abstractmethod
    def delete_board(self, slug: Slug) -> None:
        """
        Delete a board and all its columns and tasks.

        Raises BoardNotFound if the board does not exist.
        """

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------

    @abstractmethod
    def get_columns(self, board: Slug) -> list[Column]:
        """
        Return columns for the given board in display order.

        Raises BoardNotFound if the board does not exist.
        Returns an empty list when the board has no columns.
        """

    @abstractmethod
    def get_column(self, board: Slug, slug: Slug) -> Column:
        """
        Return a single Column by board and column name.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        """

    @abstractmethod
    def column_exists(self, board: Slug, slug: Slug) -> bool:
        """
        Return True when the named column exists on the board, else False.

        Raises BoardNotFound if the board does not exist.
        """

    @abstractmethod
    def create_column(self, board: Slug, name: str, slug: Slug, role: str | None = None) -> Column:
        """
        Append a column to the end of the board's column list and return it.

        `role` marks a column the application treats specially — currently only
        `archive` — and is stored with the column, so it survives a rename.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnAlreadyExists if the name is taken on that board.
        """

    @abstractmethod
    def rename_column(self, board: Slug, slug: Slug, new_name: str, new_slug: Slug) -> Column:
        """
        Rename a column and return the updated Column.

        All tasks in this column have their column reference updated.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        Raises ColumnAlreadyExists if new_name is taken on that board.
        """

    @abstractmethod
    def reorder_column(self, board: Slug, slug: Slug, position: int) -> list[Column]:
        """
        Move the column to the given 0-based position and return the full
        updated column list in new display order.

        Position is clamped to [0, len(columns) - 1].

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        """

    @abstractmethod
    def delete_column(self, board: Slug, slug: Slug) -> None:
        """
        Delete a column and all its tasks.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist.
        """

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    @abstractmethod
    def get_tasks(self, board: Slug | None = None, column: Slug | None = None) -> list[Task]:
        """
        Return tasks matching the given scope.

        `board` and `column` narrow the scope:
        - Both None  → search all boards and columns.
        - board only → search all columns within that board.
        - Both set   → search only that specific column.

        Raises BoardNotFound if the named board does not exist.
        Raises ColumnNotFound if the named column does not exist on that board.
        Returns an empty list when the scope contains no matching tasks.
        """

    @abstractmethod
    def get_task(self, board: Slug, column: Slug, filename: Slug) -> Task:
        """
        Return a single task by its exact board/column/filename path.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        Raises TaskNotFound if no task with this filename exists in that column.
        """

    # TODO: unused
    @abstractmethod
    def task_exists(self, board: Slug, column: Slug, slug: Slug) -> bool:
        """
        Return True when a task at this exact path exists, else False.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        """
        
    @abstractmethod
    def create_task(self, task: Task, slug: Slug) -> Task:
        """
        Persist a new task and return it with any storage-assigned fields
        populated (e.g. created_at / updated_at if the caller left them None).

        The `task.id` must be set by the caller before calling this method.
        The `task.board` and `task.column` must reference an existing board
        and column.
        `slug` is the storage slug (kebab-case) derived from title.

        Raises BoardNotFound if the board does not exist.
        Raises ColumnNotFound if the column does not exist on that board.
        Raises TaskAlreadyExists if a task with the same slug already
        exists in that column. (Slugs must be unique within a column directory.)
        """

    @abstractmethod
    def update_task(self, task: Task, slug: Slug) -> Task:
        """
        Overwrite an existing task's mutable fields (title, assigned_to,
        priority, due_date, tags, body) and return the updated Task.

        Locates the task by the slug. If the title has changed, the
        underlying filename is renamed to match.

        `task.board` and `task.column` are treated as read-only here;
        use move_task to change location.

        If the task title has changed, it is the caller's responsibility 
        to update `task.slug` to the new slug

        `updated_at` is set to the current UTC time by the repository.

        Raises TaskNotFound if no task with `task.id` exists.
        Raises TaskAlreadyExists if the new title collides with an existing
        task in the same column.
        """

    @abstractmethod
    def move_task(self, task: Task, column: Slug) -> Task:
        """
        Move a task to a different column within the same board
        and return the updated Task.

        Moving to the same column the task is already in is a no-op for the
        file; only ``updated_at`` is refreshed.

        The task's UUID, slug, and all other metadata are preserved.
        ``updated_at`` is always refreshed.

        Raises TaskNotFound if the task does not exist.
        Raises ColumnNotFound if the destination column does not exist.
        Raises TaskAlreadyExists if a task with the same slug already
        exists in the destination column.
        """

    @abstractmethod
    def reorder_task(self, task: Task, op: str, relative_to: Slug | None = None) -> Task:
        """
        Move a task within its column: `up`, `down`, `top`, `bottom`, or
        `above`/`below` the task named by `relative_to`.

        Validates the operation. Raises ValueError for an unknown op or for a
        relative op given no `relative_to`, and TaskNotFound if the task — or
        the task it is positioned against — does not exist.
        """

    @abstractmethod
    def delete_task(self, task: Task) -> None:
        """
        Delete a task.

        Raises TaskNotFound if the task does not exist.
        """

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    @abstractmethod
    def get_config(self, keypath: str) -> str | None:
        """
        Return the value for the given config key, or None if not set.

        Config is stored in `.kanban/config`.
        """

    @abstractmethod
    def set_config(self, keypath: str, value: str | None) -> None:
        """Set a config key to the given value."""

    # ------------------------------------------------------------------
    # Additional userdata storage (not required for core functionality)
    # ------------------------------------------------------------------

    @abstractmethod
    def get_userdata(self, keypath: str) -> str | None:
        """
        Return the value for the given userdata key, or None if not set.

        Userdata is stored in `userdata` and is intended for arbitrary
        key-value pairs that are not part of the core kanban data model but
        may be useful for extensions or integrations.
        """
        return None

    @abstractmethod
    def set_userdata(self, keypath: str, value: str | None) -> None:
        """
        Set a userdata key to the given value.

        Userdata is stored in `userdata` and is intended for arbitrary
        key-value pairs that are not part of the core kanban data model but
        may be useful for extensions or integrations.
        """
        return None