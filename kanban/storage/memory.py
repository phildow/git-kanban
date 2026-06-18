from __future__ import annotations

from datetime import date, datetime, timedelta, UTC
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


class InMemoryRepository(KanbanRepository):
    """In-memory repository scaffold.

    Uses simple dict/list containers so behavior can be filled in incrementally
    without touching calling code.
    """

    def __init__(self) -> None:
        self._boards: dict[str, Board] = {}
        self._tasks_by_id: dict[UUID, Task] = {}
        self._task_locations: dict[UUID, tuple[str, str]] = {}
        self._task_filenames: dict[UUID, str] = {}
        self._config: dict[str, str] = {}

    @staticmethod
    def _to_kebab_case(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if not slug:
            raise ValueError("Task title must contain at least one alphanumeric character")
        return slug

    def _ensure_default_columns(self, board: str) -> None:
        """Ensure the standard column set exists for the target board."""
        default_columns = ["todo", "in-progress", "in-review", "done"]
        for column in default_columns:
            if not self.column_exists(board, column):
                self.create_column(board, column)
    
    
    # ---------------------------------------------------------------------------
    # Iniialization
    # ---------------------------------------------------------------------------

    
    def init_storage(self, default_board: str = "main") -> None:
        already_initialized = self.get_config("initialized") == "true"
        if already_initialized or self.board_exists(default_board):
           raise ValueError("Kanban is already initialized")

    def is_initialized(self) -> bool:
        """Return True if the repository is already initialized at the current path."""
        return self.get_config("initialized") == "true"

    # ---------------------------------------------------------------------------
    # Bootstrap (development-only)
    # ---------------------------------------------------------------------------

    # DEBUG ONLY
    def _bootstrap_board_tasks(
        self,
        *,
        board: str,
        tasks_per_column: int,
        title_template: str,
    ) -> list[Task]:
        """Seed tasks for each column in a board using a title template."""
        columns = self.list_columns(board)
        created: list[Task] = []
        
        assignees = ["alice", "bob", "carol", "dave"]
        priorities = ["low", "medium", "high"]
        tags = ["bug", "feature", "chore"]
        dates = [date.today() + timedelta(days=i) for i in range(1, 14)]

        for column in columns:
            for i in range(1, tasks_per_column + 1):
                title = title_template.format(column=column.name.capitalize(), i=i, board=board.capitalize)
                slug = self._to_kebab_case(title)
                task = Task(
                    id=uuid4(),
                    title=title,
                    slug=slug,
                    board=board,
                    column=column.name,
                    created_by=random.choice(assignees),
                    assignee=random.choice(assignees),
                    priority=random.choice(priorities),
                    due_date=random.choice(dates),
                    tags=[random.choice(tags)],
                )
                created.append(self.create_task(task, slug))

        return created
        
    def bootstrap(self, board: str = "main", tasks_per_column: int = 3) -> list[Task]:
        """
        Bootstrap the repository with a default board and columns if it is not already initialized.
        Returns the new KanbanRoot info if initialization was performed, or None if the repository was already initialized.
        
        Seed sample tasks across all columns for local development.
        
        Returns created tasks in creation order. Raises `BoardNotFound` when
        the requested board does not exist.
        
        When bootstrapping the default `main` board, also creates and seeds an
        `infra` board with the standard column set and distinct task names.
        """
        
        if tasks_per_column < 1:
            raise ValueError("tasks_per_column must be >= 1")

        created = self._bootstrap_board_tasks(
            board=board,
            tasks_per_column=tasks_per_column,
            title_template="{column} Task {i}",
        )

        if board != "main":
            return created

        secondary_board = "infra"
        if not self.board_exists(secondary_board):
            self.create_board(secondary_board)
        self._ensure_default_columns(secondary_board)

        created.extend(
            self._bootstrap_board_tasks(
                board=secondary_board,
                tasks_per_column=tasks_per_column,
                title_template="Infra {column} Work Item {i}",
            )
        )

        return created




    # Board operations
    def list_boards(self) -> list[Board]:
        return list(self._boards.values())

    def get_board(self, name: str) -> Board:
        board = self._boards.get(name)
        if board is None:
            raise BoardNotFound(name)
        return board

    def board_exists(self, name: str) -> bool:
        return name in self._boards

    def create_board(self, name: str) -> Board:
        if self.board_exists(name):
            raise BoardAlreadyExists(name)

        board = Board(name=name)
        self._boards[name] = board
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
        for column in board.columns:
            column.board = new_name
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

    # Column operations
    def list_columns(self, board: str) -> list[Column]:
        return list(self.get_board(board).columns)

    def get_column(self, board: str, name: str) -> Column:
        board_obj = self.get_board(board)
        for column in board_obj.columns:
            if column.name == name:
                return column
        raise ColumnNotFound(board, name)

    def column_exists(self, board: str, name: str) -> bool:
        board_obj = self.get_board(board)
        return any(column.name == name for column in board_obj.columns)

    def create_column(self, board: str, name: str) -> Column:
        board_obj = self.get_board(board)
        if any(column.name == name for column in board_obj.columns):
            raise ColumnAlreadyExists(board, name)

        column = Column(name=name, board=board, position=len(board_obj.columns))
        board_obj.columns.append(column)
        return column

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        board_obj = self.get_board(board)
        column = self.get_column(board, name)

        if new_name != name and any(c.name == new_name for c in board_obj.columns):
            raise ColumnAlreadyExists(board, new_name)

        if new_name == name:
            return column

        column.name = new_name

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
        board_obj = self.get_board(board)

        current_index = next((i for i, c in enumerate(board_obj.columns) if c.name == name), None)
        if current_index is None:
            raise ColumnNotFound(board, name)

        if not board_obj.columns:
            return board_obj.columns

        clamped_position = max(0, min(position, len(board_obj.columns) - 1))
        column = board_obj.columns.pop(current_index)
        board_obj.columns.insert(clamped_position, column)

        for i, col in enumerate(board_obj.columns):
            col.position = i

        return list(board_obj.columns)

    def delete_column(self, board: str, name: str) -> None:
        board_obj = self.get_board(board)

        index = next((i for i, c in enumerate(board_obj.columns) if c.name == name), None)
        if index is None:
            raise ColumnNotFound(board, name)

        board_obj.columns.pop(index)

        for i, col in enumerate(board_obj.columns):
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

    # Task operations
    def list_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
        filter: Optional[TaskFilter] = None,
    ) -> list[Task]:
        if board is not None:
            self.get_board(board)
            if column is not None:
                self.get_column(board, column)

        tasks: list[Task] = []
        for task_id, task in self._tasks_by_id.items():
            task_board, task_column = self._task_locations.get(task_id, (task.board, task.column))

            # Scope filtering
            if board is not None and task_board != board:
                continue
            if column is not None and task_column != column:
                continue

            # Optional metadata filtering
            if filter is not None:
                if filter.assignee is not None and task.assignee != filter.assignee:
                    continue
                if filter.priority is not None and task.priority != filter.priority:
                    continue
                if filter.tag is not None and filter.tag not in task.tags:
                    continue
                if filter.created_by is not None and task.created_by != filter.created_by:
                    continue
                if filter.due_before is not None and (
                    task.due_date is None or task.due_date >= filter.due_before
                ):
                    continue
                if filter.due_after is not None and (
                    task.due_date is None or task.due_date <= filter.due_after
                ):
                    continue

            tasks.append(task)

        return tasks

    def get_task_by_id(self, task_id: UUID) -> Task:
        task = self._tasks_by_id.get(task_id)
        if task is None:
            raise TaskNotFound(str(task_id))
        return task

    def find_tasks_by_title(self, title: str, board: Optional[str] = None) -> list[Task]:
        if board is not None:
            self.get_board(board)

        title_lower = title.lower()
        matches: list[Task] = []
        for task_id, task in self._tasks_by_id.items():
            task_board, _task_column = self._task_locations.get(task_id, (task.board, task.column))
            if board is not None and task_board != board:
                continue
            if task.title.lower() == title_lower:
                matches.append(task)
        return matches

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
            new_filename = self._to_kebab_case(task.title)
            if other_board == existing_board and other_column == existing_column and other_filename == new_filename:
                raise TaskAlreadyExists(existing_board, existing_column, new_filename)

        task.board = existing_board
        task.column = existing_column
        task.created_at = existing.created_at
        task.updated_at = datetime.now(UTC)

        self._tasks_by_id[task.id] = task
        self._task_locations[task.id] = (existing_board, existing_column)
        self._task_filenames[task.id] = self._to_kebab_case(task.title)
        task.slug = self._task_filenames[task.id]
        return task

    def move_task(self, task_id: UUID, dest_board: str, dest_column: str) -> Task:
        task = self._tasks_by_id.get(task_id)
        if task is None:
            raise TaskNotFound(str(task_id))

        self.get_board(dest_board)
        self.get_column(dest_board, dest_column)

        for other_id, other_task in self._tasks_by_id.items():
            if other_id == task_id:
                continue
            other_board, other_column = self._task_locations.get(other_id, (other_task.board, other_task.column))
            other_filename = self._task_filenames.get(other_id, "")
            task_filename = self._task_filenames.get(task_id, self._to_kebab_case(task.title))
            if other_board == dest_board and other_column == dest_column and other_filename == task_filename:
                raise TaskAlreadyExists(dest_board, dest_column, task_filename)

        task.board = dest_board
        task.column = dest_column
        task.updated_at = datetime.now(UTC)
        self._task_locations[task_id] = (dest_board, dest_column)
        task.slug = self._task_filenames.get(task_id, task.slug)
        return task

    def delete_task(self, task_id: UUID) -> None:
        if task_id not in self._tasks_by_id:
            raise TaskNotFound(str(task_id))

        del self._tasks_by_id[task_id]
        self._task_locations.pop(task_id, None)
        self._task_filenames.pop(task_id, None)

    # Search
    def search_tasks(self, query: str, filter: Optional[TaskFilter] = None) -> list[Task]:
        raise NotImplementedError()

    # Config
    def get_config(self, key: str) -> Optional[str]:
        return self._config.get(key)

    def set_config(self, key: str, value: str) -> None:
        self._config[key] = value

