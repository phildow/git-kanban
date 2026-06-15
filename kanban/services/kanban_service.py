from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import re
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban_repository import KanbanRepository, ColumnNotFound
from services.git_service import GitService
from services.index_service import IndexService


# ── Params ────────────────────────────────────────────────────────────────────

@dataclass
class TaskCreateParams:
    # TODO: the title is supplied by the path, but should it be included here
    # title:      str
    assignee:   str | None = None
    priority:   str | None = None
    tags:       list[str] = field(default_factory=list)
    due_date:   datetime | None = None
    created_by: str | None = None

@dataclass
class TaskUpdateParams:
    title:      str | None = None
    assignee:   str | None = None
    priority:   str | None = None
    tags:       list[str] | None = None
    due_date:   datetime | None = None


# ── Return types ──────────────────────────────────────────────────────────────

@dataclass
class KanbanRoot:
    path:       Path           # .kanban/ directory
    git_init:   bool           # True if git repo was freshly created
    boards_dir: Path

@dataclass
class GitCommit:
    sha:         str

@dataclass
class KanbanStatus:
    user_context: UserContext
    board_count: int
    column_count: int
    task_count: int
    index_fresh: bool
    uncommitted_changes: bool

# ── KanbanService ─────────────────────────────────────────────────────────────

class KanbanService:

    # def __getattribute__(self, name: str):
    #     """Intercept attribute access and wrap callables with debug logging.

    #     For non-dunder callables, this returns a wrapper that prints the
    #     method name plus positional/keyword arguments before delegating to the
    #     original bound method. Non-callable attributes and dunder attributes
    #     are returned unchanged.
    #     """
    #     attr = object.__getattribute__(self, name)

    #     if name.startswith("__"):
    #         return attr 
    #     if callable(attr):
    #         def _wrapped(*_args, **_kwargs):
    #             print(f"Service method '{name}' called with args: {_args}, kwargs: {_kwargs}")
    #             return attr(*_args, **_kwargs)

    #         return _wrapped
        
    #     return attr

    def __init__(self, repository: KanbanRepository, index_service: IndexService, git_service: GitService) -> None:
        """
        Assemble the facade from its domain services.  All services are
        injected rather than instantiated here so that the InMemoryRepository
        can be swapped in for tests without any other changes.
        """
        self.repository = repository
        self.index_service = index_service
        self.git_service = git_service

    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def init(self, path: Path = Path(".")) -> KanbanRoot:
        """
        Create the .kanban/ directory skeleton, initialize git, and write the
        first commit.  Raises AlreadyInitialized if .kanban/ already exists at
        path.  This is the only method that runs before the services are fully
        operational, so it orchestrates creation order directly: filesystem
        first, index second, git last.
        """
        self.repository.init(default_board="main")

        self.create_board("main")
        self.create_column("main/todo")
        self.create_column("main/in-progress")
        self.create_column("main/in-review")
        self.create_column("main/done")
        self.set_user_context(board="main", column="todo")
        self.set_config("initialized", "true")

        kanban_root = path / ".kanban"
        return KanbanRoot(
            path=kanban_root,
            git_init=False,
            boards_dir=kanban_root / "boards",
        )


    # ── Active context ────────────────────────────────────────────────────────

    def use(
        self,
        path: str | None = None,
        clear:  bool = False,
    ) -> UserContext:
        """
        Set or clear the active board/column context stored in .kanban/.config.
        Validates that the referenced board (and column, if given) exist before
        writing.  No git commit — context is local working state.

        kanban use my-project/todo  →  use(path="my-project/todo")
        kanban use my-project       →  use(path="my-project")
        kanban use --clear          →  use(clear=True)
        """
        if clear:
            return self.repository.clear_user_context()

        if path is None:
            return self.repository.get_user_context()

        board: str | None = None
        column: str | None = None

        if "/" in path:
            board, column = path.split("/", 1)
            if not board or not column:
                raise ValueError("Path must be BOARD or BOARD/COLUMN")
        else:
            board = path
            active_board = self.repository.get_user_context().board
            if active_board:
                try:
                    self.repository.get_column(active_board, path)
                    board = active_board
                    column = path
                except ColumnNotFound:
                    column = None

        self.repository.get_board(board)
        if column is not None:
            self.repository.get_column(board, column)

        return self.repository.set_user_context(board=board, column=column)

    def get_user_context(self) -> UserContext:
        """Return the current active context without modifying it."""
        return self.repository.get_user_context()

    def set_user_context(self, board: str | None, column: str | None) -> UserContext:
        """Set active board/column context by delegating to the repository."""
        return self.repository.set_user_context(board=board, column=column)


    # ── Boards ────────────────────────────────────────────────────────────────

    def list_boards(
        self,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Board]:
        """
        Return all boards in the repository.  sort accepts "title"; omitting
        it preserves the order recorded in .kanban/.order.  reverse flips
        whichever ordering is in effect.
        """
        return self.repository.list_boards()

    def create_board(self, name: str) -> Board:
        """
        Create a new board directory under .kanban/boards/.  Raises
        BoardAlreadyExists if a board with that name is already present.
        Appends the new board to .kanban/.order and commits.
        """
        return self.repository.create_board(name)

    def rename_board(self, board: str, new_name: str) -> Board:
        """
        Rename a board directory and update .kanban/.order in place.  Raises
        BoardNotFound if the source board does not exist, and BoardAlreadyExists
        if new_name is already taken.  All tasks within the board retain their
        UUIDs; only the directory name (and therefore the board's slug) changes.
        Updates the active context if the renamed board was the active one.
        """
        return self.repository.rename_board(board, new_name)

    def delete_board(self, board: str) -> None:
        """
        Recursively delete a board directory and remove it from .kanban/.order.
        Raises BoardNotFound if the board does not exist.  Also removes all
        index entries for tasks that belonged to the board and clears the active
        context if it pointed at the deleted board.
        """
        return self.repository.delete_board(board)


    # ── Columns ───────────────────────────────────────────────────────────────

    def list_columns(
        self,
        board:   str | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Column]:
        """
        Return all columns for the given board.  Falls back to the active
        context board if board is None; raises NoBoardInContext if neither is
        set.  sort accepts "title"; omitting it preserves the order in the
        board's .order file.
        """
        board = self._resolve_board(board)
        return self.repository.list_columns(board)

    def create_column(self, path: str) -> Column:
        """
        Create a new column subdirectory for the provided path.  Raises
        BoardNotFound if the board does not exist and ColumnAlreadyExists if
        the column name is already taken within that board.  Appends the new
        column to the board's .order file and commits.
        """
        board, column = self._resolve_column_path(path)
        return self.repository.create_column(board, column)

    def rename_column(self, path: str, new_name: str) -> Column:
        """
        Rename a column subdirectory and update the board's .order file.
        Raises BoardNotFound, ColumnNotFound, or ColumnAlreadyExists as
        appropriate.  Tasks inside the column are untouched; their paths
        update implicitly via the directory rename.  Updates the active
        context if the renamed column was the active one.
        """
        board, column = self._resolve_column_path(path)
        return self.repository.rename_column(board, column, new_name)

    def reorder_column(self, path: str, position: int) -> list[Column]:
        """
        Move a column to the given 1-based position in the board's .order
        file.  Raises BoardNotFound or ColumnNotFound if either does not
        exist.  Position is clamped to the valid range rather than raising on
        out-of-bounds values.  Returns the full updated column list so the
        CLI can confirm the new order.
        """
        board, column = self._resolve_column_path(path)
        return self.repository.reorder_column(board, column, position)  

    def delete_column(self, path: str) -> None:
        """
        Delete a column subdirectory and all tasks it contains.  Raises
        BoardNotFound or ColumnNotFound if either does not exist.  Removes
        all index entries for tasks in the column, updates the board's .order
        file, and clears the active context column if it pointed here.
        """
        board, column = self._resolve_column_path(path)
        return self.repository.delete_column(board, column)
        return None


    # ── Tasks ─────────────────────────────────────────────────────────────────

    def list_tasks(
        self,
        path:    str | None = None,
        filter:  TaskFilter = TaskFilter(),
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Task]:
        """
        Return tasks for the given board/column, applying filters and sort in
        the service layer rather than in the repository.  board and column both
        fall back to the active context; omitting column returns tasks across
        all columns of the board.  sort accepts "title", "priority", "due-date",
        "created-at", "updated-at", or "created-by".
        """
        board, column = self._resolve_task_list_scope(path)
        tasks = self.repository.list_tasks(board=board, column=column, filter=filter)

        if not sort:
            return tasks

        def _value(task: Task):
            if sort == "title":
                return task.title.lower()
            if sort == "priority":
                priority_rank = {"low": 0, "medium": 1, "high": 2}
                return priority_rank.get((task.priority or "").lower(), -1)
            if sort == "due-date":
                return task.due_date
            if sort == "created-at":
                return task.created_at
            if sort == "updated-at":
                return task.updated_at
            if sort == "created-by":
                return (task.created_by or "").lower()
            return task.title.lower()

        return sorted(tasks, key=lambda task: (_value(task) is None, _value(task)), reverse=reverse)

    def create_task(
        self,
        path: str,
        params: TaskCreateParams,
    ) -> Task:
        """
        Write a new .md file into board/column/ with a generated UUID and the
        provided metadata as frontmatter.  Raises BoardNotFound or ColumnNotFound
        if the target location does not exist, and TaskAlreadyExists if a file
        with the same title slug is already present in that column.  Updates the
        index and commits.
        """
        board, column, title = self._resolve_task_path(path)

        assignee: str | None
        priority: str | None
        tags: list[str]
        due_date: datetime | None
        created_by: str | None

        # if params.title and params.title != title:
        #    raise ValueError("Task title in params does not match task path title")
        assignee = params.assignee
        priority = params.priority
        tags = params.tags or []
        due_date = params.due_date
        created_by = params.created_by

        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        task = Task(
            id=uuid4(),
            title=title,
            slug=self._to_kebab_case(title),
            board=board,
            column=column,
            assignee=assignee,
            priority=priority,
            tags=tags,
            due_date=due_date,
            created_by=created_by,
        )
        filename = task.slug
        created_task = self.repository.create_task(task, filename)
        self.index_service.update(created_task)
        return created_task

    def get_task(
        self,
        path: str,
    ) -> Task:
        """
        Resolve and return a single task by title slug or UUID.  Delegates
        location resolution to _resolve_task_path, which applies the
        explicit → context → index-search chain and raises TaskNotFound or
        AmbiguousTaskReference if resolution fails.
        """
        board, column, title_or_id = self._resolve_task_path(path)
        task_id: UUID | None = None
        try:
            task_id = UUID(title_or_id)
        except ValueError:
            task_id = None

        if task_id is not None:
            task = self.repository.get_task_by_id(task_id)
            if task.board != board or task.column != column:
                raise ValueError(f"Task not found in scope: {board}/{column}/{title_or_id}")
            return task

        filename = self._to_kebab_case(title_or_id)
        return self.repository.get_task(board, column, filename)

    def edit_task(
        self,
        path: str,
    ) -> Task:
        """Open's the task's .md file in an editor, then reads the updated 
        content and metadata and applies changes to the task.  Raises 
        TaskNotFound or AmbiguousTaskReference if the task cannot be resolved.  
        Updates the index and commits."""
        board, column, title_or_id = self._resolve_task_path(path)
        _ = board, column, title_or_id
        ...

    def update_task(
        self,
        path: str,
        updates:     TaskUpdateParams,
    ) -> Task:
        """
        Apply TaskUpdateParams to an existing task's frontmatter and body,
        updating updated_at automatically.  If updates.title differs from the
        current title, the file is renamed to match the new slug.  Raises
        TaskNotFound or AmbiguousTaskReference via _resolve_task_path.
        Updates the index entry and commits.
        """
        board, column, title_or_id = self._resolve_task_path(path)
        _ = board, column, title_or_id, updates
        ...

    def move_task(
        self,
        path:        str,
        dest:        str,
    ) -> Task:
        """
        Move a task's .md file to a new board/column location.  dest may be
        "<board>/<column>" or bare "<column>", in which case the source board
        is assumed.  Validates that the destination column exists before moving.
        Raises TaskNotFound, AmbiguousTaskReference, BoardNotFound, or
        ColumnNotFound as appropriate.  Updates the index and commits.
        """
        board, column, title_or_id = self._resolve_task_path(path)
        _ = board, column, title_or_id, dest
        ...

    def delete_task(
        self,
        path: str,
    ) -> None:
        """
        Delete a task's .md file from disk.  Raises TaskNotFound or
        AmbiguousTaskReference via _resolve_task_path.  Removes the task's
        index entry and commits.
        """
        task = self.get_task(path)
        self.repository.delete_task(task.id)
        self.index_service.delete(task)
        return None


    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query:   str,
        filter:  TaskFilter = TaskFilter(),
        board:   str | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Task]:
        """
        Full-text search across task titles and bodies, narrowed by any
        TaskFilter provided.  Scoped to a single board if board is given,
        otherwise searches the whole repository.  Delegates to SearchService,
        which uses the index when available and falls back to a filesystem scan
        when the index is stale or absent.
        """
        self.index_service.rebuild()


    # ── Git ───────────────────────────────────────────────────────────────────

    def log(
        self,
        board:       str | None = None,
        column:      str | None = None,
        title_or_id: str | None = None,
        limit:       int = 20,
    ) -> list[GitCommit]:
        """
        Return structured commit history, optionally scoped to a board, column,
        or specific task by UUID.  When title_or_id is provided, resolves the
        task first via _resolve_task_path so that history follows the file
        through any renames.  Delegates path filtering to GitService.
        """
        ...

    def squash(self, board: str | None = None) -> GitCommit:
        """
        Collapse all commits since the last squash (or since init) into one.
        Scoped to a single board if provided.  Returns the new squash commit.
        """
        ...


    # ── Config ────────────────────────────────────────────────────────────────

    def set_config(self, key: str, value: str) -> None:
        """
        Persist a configuration value to .kanban/.config under the given key.
        Raises InvalidConfigKey if the key is not in the supported set.  No
        git commit — config is local working state, like active context.
        """
        self.repository.set_config(key, value)


    def get_config(self, key: str) -> str:
        """
        Read a configuration value from .kanban/.config.  Raises
        InvalidConfigKey if the key is not supported and ConfigKeyNotSet if
        the key is valid but has not been assigned a value.
        """
        ...


    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> KanbanStatus:
        """
        Snapshot of the repository: active context, board/column/task counts,
        index freshness, and whether there are uncommitted changes in git.
        """
        ...


    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve_board(self, board: str | None) -> str:
        """Return explicit board or fall back to active context board."""
        if board:
            return board

        context_board = self.get_user_context().board
        if context_board:
            return context_board

        raise ValueError("Board is required and no active board is set")

    def _resolve_board_and_column(
        self,
        board: str | None,
        column: str | None,
    ) -> tuple[str, str]:
        context = self.get_user_context()
        board = board or context.board
        column = column or context.column

        if not board:
            raise ValueError("Board is required and no active board is set")
        if not column:
            raise ValueError("Column is required and no active column is set")

        return board, column

    def _resolve_column_path(self, path: str) -> tuple[str, str]:
        """Resolve [BOARD/]COLUMN path using explicit board or active context."""
        if not path:
            raise ValueError("Column path is required")

        if "/" in path:
            board, column = path.split("/", 1)
        else:
            board, column = None, path

        board = self._resolve_board(board)
        if not column:
            raise ValueError("Column is required")

        return board, column

    def _resolve_task_list_scope(self, path: str | None) -> tuple[str, str | None]:
        """Resolve optional [BOARD/COLUMN] scope for task listing."""
        if not path:
            return self._resolve_board(None), None

        if "/" in path:
            board, column = path.split("/", 1)
            return self._resolve_board(board), column

        return self._resolve_board(path), None

    def _resolve_task_path(self, path: str) -> tuple[str, str, str]:
        """Resolve [BOARD/COLUMN/]TASK path using explicit values and user context."""
        if not path:
            raise ValueError("Task path is required")

        parts = path.split("/")
        if len(parts) == 1:
            board = None
            column = None
            title_or_id = parts[0]
        elif len(parts) == 2:
            board = None
            column = parts[0]
            title_or_id = parts[1]
        else:
            board = parts[0]
            column = parts[1]
            title_or_id = "/".join(parts[2:])

        board, column = self._resolve_board_and_column(board, column)
        if not title_or_id:
            raise ValueError("Task title or id is required")

        return board, column, title_or_id

    def _to_kebab_case(self, text: str) -> str:
        """Convert free-form title text into a kebab-case filename slug."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if not slug:
            raise ValueError("Task title must contain at least one alphanumeric character")
        return slug

    def _commit(self, type: str, scope: str, description: str) -> None:
        """Compose a structured commit message and delegate to GitService."""
        ...