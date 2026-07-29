from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
import logging
import os
import re
import shlex
import subprocess
import tempfile
from uuid import uuid4

from ..index.query import SearchQuery, SortField
from ..models import Board, Column, Priority, Slug, Task, TaskFilter, UserContext
from ..models.priority import PRIORITY_ORDER
from ..protocols.completion_data_source import CompletionDataSource
from ..storage.base import KanbanRepository, ColumnNotFound, BoardNotFound, TaskNotFound, TaskAlreadyExists
from ..storage.seeds import BootstrapConfig, DEFAULT_COLUMNS
from ..services.git import GitService
from ..services.index import IndexService
from ..utils.str import slug_it


# ── Params ────────────────────────────────────────────────────────────────────

@dataclass
class TaskCreateParams:
    title:       str
    assigned_to: str | None = None
    priority:    Priority | None = None
    tags:        list[str] = field(default_factory=list)
    due_date:    datetime | None = None
    created_by:  str | None = None

@dataclass
class TaskUpdateParams:
    title:       str | None = None
    assigned_to: str | None = None
    priority:    Priority | None = None
    tags:        list[str] | None = None
    created_by:  str | None = None
    due_date:    datetime | None = None

@dataclass
class TaskUnsetParams:
    """
    Flags indicating which fields to clear on a task. Scalar fields are unset
    when their flag is True; tags listed in `tags` are removed from the task's
    tag list.
    """
    assigned_to: bool = False
    priority:    bool = False
    tags:        list[str] = field(default_factory=list)
    due_date:    bool = False
    created_by:  bool = False


# ── Return types ──────────────────────────────────────────────────────────────

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

# ── Private Utilities ─────────────────────────────────────────────────────────

def _task_matches_filter(task: Task, filter: TaskFilter) -> bool:
    """Return True if task satisfies all non-None criteria in filter."""
    if filter.assigned_to is not None and task.assigned_to != filter.assigned_to:
        return False
    if filter.priority is not None and task.priority != filter.priority:
        return False
    if filter.tags and not any(t in task.tags for t in filter.tags):
        return False
    if filter.created_by is not None and task.created_by != filter.created_by:
        return False
    if filter.due_before is not None and (task.due_date is None or task.due_date >= filter.due_before):
        return False
    if filter.due_after is not None and (task.due_date is None or task.due_date <= filter.due_after):
        return False
    if filter.exclude_columns and task.column in filter.exclude_columns:
        return False
    return True


_COMMENTS_HEADING_RE = re.compile(r"^# Comments\s*$", re.MULTILINE)


def _append_comment(body: str, comment: str) -> str:
    """
    Return `body` with `comment` appended under a `# Comments` heading.

    Trailing whitespace is stripped from the body before appending. If the body
    does not already contain a `# Comments` heading, one is inserted before the
    comment. An empty body results in a body that starts with the heading.
    """
    body = (body or "").rstrip()
    if _COMMENTS_HEADING_RE.search(body):
        return f"{body}\n\n{comment}" if body else comment
    if body:
        return f"{body}\n\n# Comments\n\n{comment}"
    return f"# Comments\n\n{comment}"


# ── KanbanService ─────────────────────────────────────────────────────────────

class KanbanService(CompletionDataSource):

    def __init__(self, repository: KanbanRepository, index_service: IndexService, git_service: GitService) -> None:
        """
        Assemble the facade from its domain services.  All services are
        injected rather than instantiated here so that the InMemoryRepository
        can be swapped in for tests without any other changes.
        """
        self.repository = repository
        self.index_service = index_service
        self.git_service = git_service
        self._user_context = UserContext()

        if self.is_initialized:
            # Load user context from userdata if available, else use defaults.
            user_board = self.get_userdata("user-context.board")
            self._user_context.board = Slug(user_board) if user_board else None

    @property
    def root(self) -> Path:
        """Return the root directory of the repository if initialized, or raise if not."""
        return self.repository.root

    @property
    def kanban_dir(self) -> Path | None:
        """Return the path to the .kanban directory if applicable for this repository type, else None."""
        return self.repository.kanban_dir

    # ------------------------------------------------------------------
    # Initialization (setup, bootstrap)
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """Return True if the repository is already initialized at the current path."""
        # Move path.exists() check to repository
        return self.repository.is_initialized

    def initialize_kanban(self, path: Path = Path("."), config: BootstrapConfig | None = None) -> bool:
        """
        Create the .kanban/ and .kanban-store/ directory skeleton, initialize git, and write the
        first commit.  Raises AlreadyInitialized if .kanban/ or .kanban-store/ already exists at
        path.  This is the only method that runs before the services are fully
        operational, so it orchestrates creation order directly: filesystem
        first, index second, git last.
        """

        self.repository.init_storage()
        self._bootstrap(config)

        if config is not None:
            default_board = config.get("usercontext", {}).get("board")
            self.update_user_context(board=Slug(default_board) if default_board else None)

        return True

    def _bootstrap(self, config: BootstrapConfig | None = None) -> None:
        """Create the default boards, columns, and tasks for a new repository."""
        if config is None:
            return
        
        now = datetime.now(timezone.utc)
        
        for board_config in config["boards"]:
            board_name = board_config["name"]
            board_slug = board_config["slug"]
            self.repository.create_board(board_name, board_slug)
            for col_config in board_config["columns"]:
                col_name = col_config["name"]
                col_slug = col_config["slug"]
                self.repository.create_column(board_slug, col_name, col_slug)
                for task_config in col_config.get("tasks", []):
                    task = Task(
                        id=uuid4(),
                        title=task_config["title"],
                        slug=task_config["slug"],
                        board=board_slug,
                        column=col_slug,
                        priority=Priority(p) if (p := task_config.get("priority")) else None,
                        assigned_to=task_config.get("assigned_to"),
                        body=task_config.get("body", ""),
                        created_at=now,
                        updated_at=now,
                    )
                    self.repository.create_task(task, task.slug)
        
    # ------------------------------------------------------------------
    # User Context
    # ------------------------------------------------------------------

    @property
    def user_context(self) -> UserContext:
        """Return the current user context without modifying it."""
        return self._user_context

    @property
    def working_path(self) -> Path:
        """Return the current working path based on the user context."""
        return self.user_context.path
    
    @property
    # TODO: should svc.working_board return the board object instead of just the slug?
    def working_board(self) -> Slug | None:
        """Return the current working board based on the user context."""
        return self.user_context.board
    
    @working_board.setter
    def working_board(self, value: Slug | None) -> None:
        """Set the current working board in the user context."""
        self.update_user_context(board=value)
        
    def update_user_context(self, board: Slug | None) -> UserContext:
        """Set the board context."""
        self._user_context.board = board
        self.set_userdata("user-context.board", str(board) if board else None)
        return self.user_context

    def clear_user_context(self) -> UserContext:
        """Clear the user context with initial default values."""
        self.update_user_context(board=None)
        return self.user_context

    # ------------------------------------------------------------------
    # Path Resolution and Completions
    # ------------------------------------------------------------------

    def _board_exists(self, board: Slug) -> bool:
        """Return True if the given board exists in the repository, False if not."""
        return self.repository.board_exists(board)

    def _column_exists(self, board: Slug, column: Slug) -> bool:
        """Return True if the given column exists in the repository, False if not."""
        return self.repository.column_exists(board, column)

    # TODO: revisit: if we have an active board always preface the path with it
    def resolve_path(self, path: str | None = None) -> Path:
        """
        Resolve a user-provided path into an absolute Path object.

        The path may be absolute (starting with "/") or relative to the
        current user context.  ".." moves up one level; navigating above
        root raises ValueError.  Multiple ".." segments are supported.
        """
        path = path or ""
        if path.startswith("/"):
            base = Path("/")
            rest = path.lstrip("/")
        else:
            base = self.working_path
            rest = path

        components = [c for c in rest.split("/") if c]
        resolved_path = base.joinpath(*components).resolve(strict=False)
        return resolved_path
        
    def path_components(self, path: str | Path | Slug | None = None) -> tuple[Slug | None, Slug | None, Slug | None]:
        """Resolve a [BOARD/][COLUMN/]TITLE path into its components."""
        # TODO: temporary until full path migration
        if isinstance(path, Path):
            path = str(path)

        path = self.resolve_path(path)
        parts = path.parts # ["/", board|None, column|None, title|None]
        return Slug(parts[1]) if len(parts) > 1 else None, \
               Slug(parts[2]) if len(parts) > 2 else None, \
               Slug(parts[3]) if len(parts) > 3 else None

    def change_dir(
        self,
        path:  str | None = None,
        clear: bool = False,
    ) -> UserContext:
        """
        Set or clear the current board/column context stored in .kanban/config.
        Validates that the referenced board (and column, if given) exist before
        writing.  No git commit — context is local working state.

        kanban use my-project/todo  →  change_dir(path="my-project/todo")
        kanban use my-project       →  change_dir(path="my-project")
        kanban use --clear          →  change_dir(clear=True)
        """

        path = self._strip_trailing_slash(path) if path else None
        
        # address the simplest cases first: 
        # no args, clear flag, or root path all reset to the default context

        if clear:
            return self.clear_user_context()
        if path == "/":
            return self.clear_user_context()
        if path is None:
            return self.user_context

        board, column, task = self.path_components(path)

        if task is not None:
            raise ValueError(f"Invalid path: {path} (cannot cd to a task)")
        if board is not None and not self._board_exists(board):
            raise BoardNotFound(board)
        if board is not None and column is not None and not self._column_exists(board, column):
            raise ColumnNotFound(board, column)
        
        return self.update_user_context(board=board)

    def set_board(self, slug: Slug) -> UserContext:
        """Set the current context to the given board, validating that it exists."""
        board = self.repository.get_board(slug)

        if not board:
            raise BoardNotFound(slug)

        self.working_board = board.slug
        return self.user_context

    # ── All Items ─────────────────────────────────────────────────────────────

    def get_list(
            self, 
            path: str | None = None, 
            filter: TaskFilter = TaskFilter(), 
            sort: str | None = "column", 
            reverse: bool = False
        ) -> tuple[type[Board], list[Board]] | tuple[type[Column], list[Column]] | tuple[type[Task], list[Task]]:
        """
        Return a list of boards, columns, or tasks based on the given path.
        If path is None, returns all boards.  If path is a board, returns all
        columns in that board.  If path is a board/column, returns all tasks in
        that column.  Applies filters and sort to tasks if applicable.

        The returned tuple pairs a type marker with a list of that type: one of
        (Board, list[Board]), (Column, list[Column]), or (Task, list[Task]).
        Callers can dispatch on the marker to know which branch was taken.
        """
        board, column, task = self.path_components(path)

        if task:
            raise ValueError(f"Invalid path: {path} (cannot list a task)")

        if board and column:
            return Task, self.get_tasks(path=Path(f"/{board}/{column}"), filter=filter, sort=sort, reverse=reverse)
        elif board:
            return Column, self.get_columns(board=board)
        else:
            return Board, self.get_boards()

    # ── Boards ────────────────────────────────────────────────────────────────

    def get_boards(self) -> list[Board]:
        """
        Return all boards in the repository, in the order recorded in
        .kanban-store/boards/.metadata.
        """
        return self.repository.get_boards()

    # TODO: Raise error if the board does not exist, rather than returning None.  
    # This is a service layer, so it should raise exceptions for invalid slugs/paths rather than returning None.
    def get_board(self, path: Path | Slug) -> Board | None:
        """Return the board for the given board path or slug, or None if not found."""
        board: Slug
        if isinstance(path, Path):
            board = Slug(str(path).lstrip("/"))
        else:
            board = path
        return self.repository.get_board(board)

    def create_board(
        self, 
        name: str, 
        columns: list[tuple[str, Slug]] = DEFAULT_COLUMNS
    ) -> Board:
        """
        Create a new board directory under .kanban/boards/.  Raises
        BoardAlreadyExists if a board with that name is already present.
        Appends the new board to .kanban-store/boards/.metadata and commits.
        """
        slug = slug_it(name)
        board = self.repository.create_board(name, slug)
    
        for col in columns:
            self.repository.create_column(board.slug, col[0], col[1])
            
        board.column_count = len(columns)

        return board

    def rename_board(self, path: Path | None, new_name: str) -> Board:
        """
        Rename a board directory and update .kanban-store/boards/.metadata in place.  Raises
        BoardNotFound if the source board does not exist, and BoardAlreadyExists
        if new_name is already taken.  All tasks within the board retain their
        UUIDs; only the directory name (and therefore the board's slug) changes.
        Updates the current context if the renamed board was the current one.
        """

        if path is None:
            old_board = self.working_board
        else:
            old_board, _, _ = self.path_components(path)

        if old_board is None:
            raise ValueError("No board specified and no board in context")
        
        new_slug = slug_it(new_name)
        board = self.repository.rename_board(old_board, new_name, new_slug=new_slug)

        # Keep current context in sync.
        if self.working_board == old_board:
            self.working_board = board.slug

        # Update index entries for tasks in the renamed board.
        for task in self.get_tasks(Path(f"/{board.slug}")):
            self.index_service.upsert_task(task)

        return board

    def delete_board(self, path: Path | None) -> Board:
        """
        Recursively delete a board directory and remove it from .kanban-store/boards/.metadata.
        Raises BoardNotFound if the board does not exist.  Also removes all
        index entries for tasks that belonged to the board and clears the current
        context if it pointed at the deleted board.  Returns the deleted Board.
        """

        if path is None:
            board = self.working_board
        else:
            board, _, _ = self.path_components(path)
        
        if board is None:
            raise ValueError("No board specified and no board in context")

        deleted_board = self.repository.get_board(board)
        tasks = self.get_tasks(path)
        self.repository.delete_board(board)

        # Clear current context if it points to the deleted board.
        if self.working_board == board:
            self.clear_user_context()

        # Remove all index entries for tasks in the deleted board.
        for task in tasks:
            self.index_service.remove_task(task)

        return deleted_board


    # ── Columns ───────────────────────────────────────────────────────────────

    def get_columns(
        self,
        board:   Path | Slug | None = None,
    ) -> list[Column]:
        """
        Return all columns for the given board, in the order recorded in the
        board's .metadata file.  Falls back to the current context board if
        board is None; raises NoBoardInContext if neither is set.
        """
        if board is None:
            board = self.working_board
        if board is None:
            raise ValueError("No board specified and no board in context")
        
        board, _, _ = self.path_components(board)

        if board is None:
            raise ValueError("No board specified and no board in context")        
        
        return self.repository.get_columns(board)

    def get_column(self, path: Path | Slug) -> Column:
        """Return a single column resolved from a board/column path."""
        board, column, task = self.path_components(path)

        if board is None or column is None or task is not None:
            raise ValueError(f"Invalid column path: {path}")

        return self.repository.get_column(board, column)

    def create_column(self, path: Path | None, title: str) -> Column:
        """
        Create a new column subdirectory for the provided board path and title.  Raises
        BoardNotFound if the board does not exist and ColumnAlreadyExists if
        the column name is already taken within that board.  Appends the new
        column to the board's .metadata file and commits.
        """
        if path is None:
            board = self.working_board
        else:
            board, _, _ = self.path_components(path)

        if board is None:
            raise ValueError("No board specified and no board in context")

        slug = slug_it(title)
        return self.repository.create_column(board, title, slug)

    def rename_column(self, path: Path | Slug, new_name: str) -> Column:
        """
        Rename a column subdirectory and update the board's .metadata file.
        Raises BoardNotFound, ColumnNotFound, or ColumnAlreadyExists as
        appropriate.  Tasks inside the column are untouched; their paths
        update implicitly via the directory rename.  Updates the current
        context if the renamed column was the current one.
        """
        board, column, _ = self.path_components(path)

        if board is None or column is None:
            raise ValueError(f"Invalid column path: {path}")

        new_slug = slug_it(new_name)
        renamed_column = self.repository.rename_column(board, column, new_name, new_slug=new_slug)

        # Update index entries for tasks in the renamed column.
        for task in self.get_tasks(Path(f"/{board}/{new_slug}")):
            self.index_service.upsert_task(task)

        return renamed_column

    def reorder_column(self, path: Path | Slug, position: int) -> list[Column]:
        """
        Move a column to the given 1-based position in the board's .metadata
        file.  Raises BoardNotFound or ColumnNotFound if either does not
        exist.  Position is clamped to the valid range rather than raising on
        out-of-bounds values.  Returns the full updated column list so the
        CLI can confirm the new order.
        """
        board, column, _ = self.path_components(path)

        if board is None or column is None:
            raise ValueError(f"Invalid column path: {path}")
        
        return self.repository.reorder_column(board, column, position)  

    def delete_column(self, path: Path | Slug) -> Column:
        """
        Delete a column subdirectory and all tasks it contains.  Raises
        BoardNotFound or ColumnNotFound if either does not exist.  Removes
        all index entries for tasks in the column, updates the board's .metadata
        file, and clears the current context column if it pointed here.
        Returns the deleted Column.
        """
        board, column, _ = self.path_components(path)

        if board is None or column is None:
            raise ValueError(f"Invalid column path: {path}")

        deleted_column = self.repository.get_column(board, column)
        tasks = self.get_tasks(deleted_column.path)
        self.repository.delete_column(board, column)

        # Remove all index entries for tasks in the deleted column.
        for task in tasks:
            self.index_service.remove_task(task)

        return deleted_column


    # ── Tasks ─────────────────────────────────────────────────────────────────

    def _resolve_task_path(self, path: Path | Slug) -> Path:
        """
        Resolve a task target into a fully-qualified /board/column/task Path.

        A Path (supplied by the CLI) is already fully qualified and is returned
        unchanged. A bare Slug (supplied by the REPL) names a task by its slug
        alone; the column that contains it is located first, within the active
        board, and a full Path is constructed from board, column, and slug.

        A slug that embeds a slash is treated as an explicit column/task (or
        /board/column/task) path and resolved directly, so REPL users can still
        override the active context with a fully-typed path.

        Raises TaskNotFound if a bare slug matches no task in the active board.
        """
        if isinstance(path, Path):
            return path

        if "/" in path:
            return Path(path)

        board = self.working_board
        if board is None:
            raise ValueError(f"No active board; cannot resolve task '{path}' by slug alone")

        for task in self.get_tasks(Path(f"/{board}")):
            if task.slug == path:
                return Path(f"/{board}/{task.column}/{task.slug}")

        raise TaskNotFound(path)

    def get_tasks(
        self,
        path:    Path | None = None,
        filter:  TaskFilter = TaskFilter(),
        sort:    str | None = "column",
        reverse: bool = False,
    ) -> list[Task]:
        """
        Return tasks for the given board/column, applying filters and sort in
        the service layer rather than in the repository. When path is omitted,
        the current working board is used if available; otherwise all tasks are
        returned. Omitting a column returns tasks across all columns of the
        selected board. sort accepts "title", "priority", "due-date",
        "created-at", "updated-at", or "created-by".  The default "column"
        sort orders tasks by their column's position and then by each task's
        position within its column.
        """
        if path is None and self.working_board is not None:
            path = Path(f"/{self.working_board}")

        board, column, _ = self.path_components(path)
        tasks = self.repository.get_tasks(board=board, column=column)

        if filter:
            tasks = [t for t in tasks if _task_matches_filter(t, filter)]

        if sort is None or sort == "column":
            positions = self._column_task_positions(tasks)
            return sorted(tasks, key=lambda t: positions.get((t.board, t.column, t.slug), (2**31, 2**31)), reverse=reverse)

        def _value(task: Task):
            if sort == "title":
                return task.title.lower()
            if sort == "priority":
                return PRIORITY_ORDER.get(task.priority, -1) if task.priority is not None else -1
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

    def _column_task_positions(
        self,
        tasks: list[Task],
    ) -> dict[tuple[Slug, Slug, Slug], tuple[int, int]]:
        """
        Build a lookup of (board, column, task_slug) -> (column_position, task_position).

        Column position is the column's ordering within the board (see
        Column.position). Task position is the index of the task in its
        column's stored task order, so tasks retain the order the user
        arranged them in.
        """
        positions: dict[tuple[Slug, Slug, Slug], tuple[int, int]] = {}
        boards = {t.board for t in tasks if t.board}
        for board in boards:
            for col in self.get_columns(board):
                col_tasks = self.repository.get_tasks(board=board, column=col.slug)
                for idx, task in enumerate(col_tasks):
                    positions[(board, col.slug, task.slug)] = (col.position, idx)
        return positions

    def create_task(
        self,
        path: Path | Slug,
        params: TaskCreateParams,
    ) -> Task:
        """
        Write a new .md file into board/column/ with a generated UUID and the
        provided metadata as frontmatter.  Raises BoardNotFound or ColumnNotFound
        if the target location does not exist, and TaskAlreadyExists if a file
        with the same title slug is already present in that column.  Updates the
        index and commits.
        """
        slug = slug_it(params.title)
        board, column, _ = self.path_components(path)

        if board is None or column is None:
            raise ValueError(f"No working board/column and no explicit path provided: {path}")

        # Task slugs are unique board-wide, not merely within a column, so the
        # slug can address a task from any column of the board.
        existing = next((t for t in self.get_tasks(Path(f"/{board}")) if t.slug == slug), None)
        if existing is not None:
            raise TaskAlreadyExists(board, existing.column, params.title)

        assigned_to: str | None
        priority: Priority | None
        title: str
        tags: list[str]
        due_date: datetime | None
        created_by: str | None

        title = params.title
        assigned_to = params.assigned_to
        priority = params.priority
        tags = params.tags or []
        due_date = params.due_date
        created_by = params.created_by

        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        task = Task(
            id=uuid4(),
            title=title,
            slug=slug,
            board=board,
            column=column,
            assigned_to=assigned_to,
            priority=priority,
            tags=tags,
            due_date=due_date,
            created_by=created_by,
            body="# Description\n\n",
        )
        filename = task.slug
        created_task = self.repository.create_task(task, filename)
        self.index_service.upsert_task(created_task)
        return created_task

    def get_task(
        self,
        path: Path | Slug,
    ) -> Task:
        """
        Resolve and return a single task.  Accepts a fully-qualified Path (from
        the CLI) or a bare task Slug (from the REPL); the latter is resolved to
        its column within the active board by _resolve_task_path.  Raises
        TaskNotFound if resolution fails.
        """
        resolved_path = self._resolve_task_path(path)
        board, column, title = self.path_components(resolved_path)

        if board is None or column is None:
            raise ValueError(f"No working board/column and no explicit path provided: {path}")
        if title is None:
            raise ValueError(f"No task title provided in path: {path}")

        return self.repository.get_task(board, column, title)

    def rename_task(
        self,
        path: Path | Slug,
        new_title: str,
    ) -> Task:
        """
        Rename a task's .md file and update its frontmatter.  Accepts a
        fully-qualified Path (from the CLI) or a bare task Slug (from the REPL).
        Raises BoardNotFound, ColumnNotFound, or TaskNotFound if the task cannot
        be resolved, and TaskAlreadyExists if the new title slug is already taken
        in that column.  Updates the index and commits.
        """
        resolved_path = self._resolve_task_path(path)
        board, column, title = self.path_components(resolved_path)
        if board is None or column is None or title is None:
            raise ValueError(f"Unable to locate task at: {path}")

        task = self.get_task(resolved_path)
        slug = task.slug

        new_slug = slug_it(new_title)
        task.title = new_title
        task.slug = new_slug

        renamed_task = self.repository.update_task(task, slug=slug)
        self.index_service.upsert_task(renamed_task)
        return renamed_task

    def edit_task(
        self,
        path: Path | Slug,
    ) -> Task:
        """Open the task's body in an editor and apply the edited content back
        to the task.  Frontmatter fields (id, title, slug, board, column,
        assigned_to, priority, due_date, tags, created_by, created_at,
        updated_at) are preserved unchanged.  Accepts a fully-qualified Path
        (from the CLI) or a bare task Slug (from the REPL).  Raises TaskNotFound
        if the task cannot be resolved.  Updates the index and commits.
        """
        task = self.get_task(path)

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".md",
                prefix="kanban-task-",
                delete=False,
            ) as tmp:
                tmp.write(task.body or "")
                tmp.flush()
                tmp_path = tmp.name

            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
            editor_cmd = shlex.split(editor)
            subprocess.run([*editor_cmd, tmp_path], check=True)

            with open(tmp_path, "r", encoding="utf-8") as f:
                task.body = f.read()

            updated = self.repository.update_task(task, slug=task.slug)
            self.index_service.upsert_task(updated)
            return updated
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

    def update_task(
        self,
        path:     Path | Slug,
        updates:  TaskUpdateParams,
    ) -> Task:
        """
        Apply TaskUpdateParams to an existing task's frontmatter and body,
        updating updated_at automatically.  Accepts a fully-qualified Path (from
        the CLI) or a bare task Slug (from the REPL).  If updates.title differs
        from the current title, the file is renamed to match the new slug.
        Raises TaskNotFound if the task cannot be resolved. Updates the index
        entry and commits.
        """
        task = self.get_task(path)

        # TODO: how do we handle removing a field?
        # If the user wants to remove a due date, for example, they would have to pass in updates.due_date = None, but that is indistinguishable from "don't change the due date".
        # We could use a sentinel value or a separate "remove" flag for each field, but that seems cumbersome.  For now, we will just treat None as "don't change".

        due_date = updates.due_date
        slug = task.slug

        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        if updates.title and updates.title != task.title:
            task.title = updates.title
            task.slug = slug_it(updates.title)
        if updates.assigned_to is not None:
            task.assigned_to = updates.assigned_to
        if updates.priority is not None:
            task.priority = updates.priority
        if updates.tags is not None:
            task.tags = list(set(task.tags) | set(updates.tags))
        if updates.due_date is not None:
            task.due_date = due_date
        if updates.created_by is not None:
            task.created_by = updates.created_by

        updated = self.repository.update_task(task, slug=slug)
        self.index_service.upsert_task(updated)
        return updated

    def unset_task(
        self,
        path:   Path | Slug,
        unsets: TaskUnsetParams,
    ) -> Task:
        """
        Clear fields on an existing task. Scalar fields (assigned_to, priority,
        due_date, created_by) are cleared when the corresponding flag is True.
        Tags listed in `unsets.tags` are removed from the task's tag list.
        Accepts a fully-qualified Path (from the CLI) or a bare task Slug (from
        the REPL). Raises TaskNotFound if the task cannot be resolved. Updates
        the index entry and commits.
        """
        task = self.get_task(path)
        slug = task.slug

        if unsets.assigned_to:
            task.assigned_to = None
        if unsets.priority:
            task.priority = None
        if unsets.due_date:
            task.due_date = None
        if unsets.created_by:
            task.created_by = None
        if unsets.tags:
            task.tags = list(set(task.tags) - set(unsets.tags))

        updated = self.repository.update_task(task, slug=slug)
        self.index_service.upsert_task(updated)
        return updated

    def move_task(
        self,
        path:   Path | Slug,
        column: Slug,
    ) -> Task:
        """
        Move a task's .md file to a new column within the same board.  Accepts a
        fully-qualified Path (from the CLI) or a bare task Slug (from the REPL).
        Validates that the destination column exists before moving.
        Raises TaskNotFound, BoardNotFound, or ColumnNotFound as appropriate.
        Updates the index and commits.
        """
        task = self.get_task(path)
        result = self.repository.move_task(task, column)
        self.index_service.upsert_task(result)
        return result

    def reorder_task(
        self,
        path: Path | Slug,
        op:   str,
    ) -> Task:
        """
        Bump a task's priority up/down or to top/bottom.  Accepts a
        fully-qualified Path (from the CLI) or a bare task Slug (from the REPL).
        Validates that the new priority is valid.  Raises TaskNotFound if the
        task cannot be resolved.  Updates the index and commits.
        """
        task = self.get_task(path)
        result = self.repository.reorder_task(task, op)
        self.index_service.upsert_task(result)
        return result

    def delete_task(
        self,
        path: Path | Slug,
    ) -> Task:
        """
        Delete a task's .md file from disk.  Accepts a fully-qualified Path (from
        the CLI) or a bare task Slug (from the REPL).  Raises TaskNotFound if the
        task cannot be resolved.  Removes the task's index entry and commits.
        Returns the deleted Task.
        """
        task = self.get_task(path)
        self.repository.delete_task(task)
        self.index_service.remove_task(task)
        return task

    def assign_task(
        self,
        path: Path | Slug,
        user: str,
    ) -> Task:
        """
        Assign a task to a user.  Accepts a fully-qualified Path (from the CLI)
        or a bare task Slug (from the REPL).  Raises TaskNotFound if the task
        cannot be resolved.  Updates the index and commits.
        """
        return self.update_task(path, TaskUpdateParams(assigned_to=user))

    def tag_task(
        self,
        path: Path | Slug,
        tag:  str,
    ) -> Task:
        """
        Add a tag to a task.  Accepts a fully-qualified Path (from the CLI) or a
        bare task Slug (from the REPL).  The tag is added via set union so it
        will not be duplicated if the task already has it.  Raises TaskNotFound
        if the task cannot be resolved.  Updates the index and commits.
        """
        return self.update_task(path, TaskUpdateParams(tags=[tag]))

    def untag_task(
        self,
        path: Path | Slug,
        tag:  str,
    ) -> Task:
        """
        Remove a tag from a task.  Accepts a fully-qualified Path (from the
        CLI) or a bare task Slug (from the REPL).  The tag is removed via set
        difference; removing a tag that is not present is a no-op.  Raises
        TaskNotFound if the task cannot be resolved.  Updates the index and
        commits.
        """
        return self.unset_task(path, TaskUnsetParams(tags=[tag]))

    def comment_task(
        self,
        path:    Path | Slug,
        comment: str,
    ) -> Task:
        """
        Append a comment to a task's body under a `# Comments` heading. If the
        task body does not already contain a `# Comments` heading, one is
        added before the comment. Accepts a fully-qualified Path (from the CLI)
        or a bare task Slug (from the REPL). Raises TaskNotFound if the task
        cannot be resolved. Updates the index and commits.
        """
        task = self.get_task(path)
        task.body = _append_comment(task.body, comment)
        updated = self.repository.update_task(task, slug=task.slug)
        self.index_service.upsert_task(updated)
        return updated

    # ── Search ────────────────────────────────────────────────────────────────

    def get_tags(
        self,
        board:   Slug | None = None
        ) -> list[str]:
        """
        Return a list of all unique tags across tasks in the repository, or
        scoped to a single board if board is provided.
        """
        return self.index_service.list_tags(board=board)

    def get_assigned_tos(
        self,
        board:   Slug | None = None
        ) -> list[str]:
        """
        Return a list of all unique assigned_to values across tasks in the repository, or
        scoped to a single board if board is provided.
        """
        return self.index_service.list_assigned_to(board=board)

    def search(
        self,
        query:   str,
        filter:  TaskFilter = TaskFilter(),
        board:   Slug | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Task]:
        """
        Full-text search across task titles and bodies, narrowed by any
        TaskFilter provided.  Scoped to a single board if board is given,
        otherwise searches the whole repository.  Rebuilds the index first
        to guarantee fresh results, then delegates to the index service.
        When sort is omitted, results are ordered by column position then by
        each task's position within its column.
        """
        self.index_service.rebuild()

        search_query = SearchQuery(
            text=query,
            board=board,
            assigned_to=filter.assigned_to,
            priority=filter.priority,
            tags=tuple(filter.tags),
            created_by=filter.created_by,
            due_before=filter.due_before.date() if filter.due_before else None,
            due_after=filter.due_after.date() if filter.due_after else None,
            sort=SortField(sort) if sort else SortField.TITLE,
            reverse=reverse,
        )

        results = self.index_service.search(search_query)
        tasks = [result.task for result in results]

        if sort is None:
            positions = self._column_task_positions(tasks)
            tasks = sorted(tasks, key=lambda t: positions.get((t.board, t.column, t.slug), (2**31, 2**31)), reverse=reverse)

        return tasks

    # ── Git ───────────────────────────────────────────────────────────────────

    def log(
        self,
        path:   Path = Path("/"),
        limit:  int = 20,
    ) -> list[GitCommit]:
        """
        Return structured commit history, optionally scoped to a board, column,
        or specific task by UUID.  When title is provided, resolves the
        task first via _resolve_path_into_parts so that history follows the file
        through any renames.  Delegates path filtering to GitService.
        """
        raise NotImplementedError()

    def squash(self, board: Slug | None = None) -> GitCommit:
        """
        Collapse all commits since the last squash (or since init) into one.
        Scoped to a single board if provided.  Returns the new squash commit.
        """
        raise NotImplementedError()


    # ── Config ────────────────────────────────────────────────────────────────

    def get_config(self, keypath: str) -> str | None:
        """
        Read a configuration value from .kanban/.config.  Raises
        InvalidConfigKey if the key is not supported and ConfigKeyNotSet if
        the key is valid but has not been assigned a value.
        """
        return self.repository.get_config(keypath)

    def set_config(self, keypath: str, value: str) -> str | None:
        """
        Persist a configuration value to .kanban/.config under the given key.
        Raises InvalidConfigKey if the key is not in the supported set.  No
        git commit — config is local working state, like current context.
        """
        self.repository.set_config(keypath, value)
        return self.get_config(keypath)

    # ── Userdata ──────────────────────────────────────────────────────────────

    def get_userdata(self, keypath: str) -> str | None:
        """
        Read a userdata value from .kanban/userdata.  Raises UserdataKeyNotSet
        if the key does not exist.
        """
        return self.repository.get_userdata(keypath)

    def set_userdata(self, keypath: str, value: str | None) -> None:
        """
        Persist arbitrary user data to .kanban/userdata under the given key.
        This is separate from config in that it's not intended for structured
        application settings, but rather for users to store custom data like
        API keys or snippets.  No git commit — userdata is local working state.
        """
        self.repository.set_userdata(keypath, value)

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> KanbanStatus:
        """
        Snapshot of the repository: current context, board/column/task counts,
        index freshness, and whether there are uncommitted changes in git.
        """
        raise NotImplementedError()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _strip_trailing_slash(self, path: str) -> str:
        """Return a path token without trailing slashes."""
        if path == "/":
            return path
        return path.rstrip("/")

    def _commit(self, type: str, scope: str, description: str) -> None:
        """Compose a structured commit message and delegate to GitService."""
        raise NotImplementedError()