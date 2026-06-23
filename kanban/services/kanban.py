from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timezone
import os
import re
import shlex
import subprocess
import tempfile
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import KanbanRepository, ColumnNotFound, BoardNotFound
from storage.seeds import BootstrapConfig
from services.git import GitService
from services.index import IndexService
from utils.str import kebab_case


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
    created_by: str | None = None
    due_date:   datetime | None = None


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

# ── Filtering ─────────────────────────────────────────────────────────────────

def _task_matches_filter(task: Task, filter: TaskFilter) -> bool:
    """Return True if task satisfies all non-None criteria in filter."""
    if filter.assignee is not None and task.assignee != filter.assignee:
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
    return True


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
        self._user_context = UserContext()

        if self.is_initialized:
            # Load user context from userdata if available, else use defaults.
            self._user_context.board = self.get_userdata("user-context.board")
            self._user_context.column = self.get_userdata("user-context.column")

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
            default_column = config.get("usercontext", {}).get("column")
            self.update_user_context(board=default_board, column=default_column)

        return True

    def _bootstrap(self, config: BootstrapConfig | None = None) -> None:
        """Create the default boards, columns, and tasks for a new repository."""
        if config is None:
            return
        
        now = datetime.now(timezone.utc)
        
        for board_config in config["boards"]:
            board = board_config["name"]
            self.repository.create_board(board)
            for col in board_config["columns"]:
                self.repository.create_column(board, col)
            for task_config in board_config["tasks"]:
                task = Task(
                    id=uuid4(),
                    title=task_config["title"],
                    slug=task_config["slug"],
                    board=board,
                    column=task_config["column"],
                    priority=task_config.get("priority"),
                    assignee=task_config.get("assignee"),
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
        return self.user_context.path
    
    @property
    def working_board(self) -> str | None:
        return self.user_context.board
    
    @property
    def working_column(self) -> str | None:
        return self.user_context.column
    
    def update_user_context(self, board: str | None, column: str | None) -> UserContext:
        """Set the board/column context"""
        self._user_context.board = board
        self._user_context.column = column
        self.set_userdata("user-context.board", board)
        self.set_userdata("user-context.column", column)
        return self._user_context

    def clear_user_context(self) -> UserContext:
        """Clear the user context with initial default values."""
        self._user_context = UserContext()
        self.set_userdata("user-context.board", None)
        self.set_userdata("user-context.column", None)
        return self._user_context

    # ------------------------------------------------------------------
    # Path Resolution and Completions
    # ------------------------------------------------------------------

    def _board_exists(self, board: str) -> bool:
        """Return True if the given board exists in the repository, False if not."""
        return self.repository.board_exists(board)

    def _column_exists(self, board: str, column: str) -> bool:
        """Return True if the given column exists in the repository, False if not."""
        return self.repository.column_exists(board, column)

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
        
    def path_components(self, path: str | None = None) -> tuple[str | None, str | None, str | None]:
        """Resolve a [BOARD/][COLUMN/]TITLE path into its components."""
        path = self.resolve_path(path)
        parts = path.parts # ["/", board|None, column|None, title|None]
        return parts[1] if len(parts) > 1 else None, \
               parts[2] if len(parts) > 2 else None, \
               parts[3] if len(parts) > 3 else None

    def change_dir(
        self,
        path: str | None = None,
        clear:  bool = False,
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

        if task:
            raise ValueError(f"Invalid path: {path} (cannot cd to a task)")
        if board and not self._board_exists(board):
            raise BoardNotFound(board)
        if column and not self._column_exists(board, column):
            raise ColumnNotFound(board, column)
        
        return self.update_user_context(board=board, column=column)

    def set_board(self, board: str) -> UserContext:
        """Set the current context to the given board, validating that it exists."""
        board = board.strip("/")
        board = self.repository.get_board(board)

        if not board:
            raise BoardNotFound(board)

        self.update_user_context(board=board.name, column=None)
        return self.user_context

    def set_column(self, column: str) -> UserContext:
        """Set the current context to the given column, validating that it exists."""
        board = self.user_context.board

        if not board:
            raise ValueError("Current board has not been set; cannot change column")
        column = column.strip("/")
        column = self.repository.get_column(board, column)

        if not column:
            raise ColumnNotFound(board, column)

        self.update_user_context(board=board, column=column.name)
        return self.user_context

    # ── Boards ────────────────────────────────────────────────────────────────

    def get_boards(
        self,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Board]:
        """
        Return all boards in the repository.  sort accepts "title"; omitting
        it preserves the order recorded in .kanban-store/boards/.metadata.  reverse flips
        whichever ordering is in effect.
        """
        return self.repository.get_boards()

    def create_board(self, path: str, columns = ["todo", "in-progress", "in-review", "done"]) -> Board:
        """
        Create a new board directory under .kanban/boards/.  Raises
        BoardAlreadyExists if a board with that name is already present.
        Appends the new board to .kanban-store/boards/.metadata and commits.
        """
        board, _, _ = self.path_components(path)
        board = self.repository.create_board(board)
    
        columns = [self.repository.create_column(board.name, col) for col in columns]
        board.columns = columns

        return board

    def rename_board(self, path: str, new_name: str) -> Board:
        """
        Rename a board directory and update .kanban-store/boards/.metadata in place.  Raises
        BoardNotFound if the source board does not exist, and BoardAlreadyExists
        if new_name is already taken.  All tasks within the board retain their
        UUIDs; only the directory name (and therefore the board's slug) changes.
        Updates the current context if the renamed board was the current one.
        """
        old_board, _, _ = self.path_components(path)
        board = self.repository.rename_board(old_board, new_name)

        # Keep current context in sync.
        if self._user_context.board == old_board:
            self._user_context.board = board.name

        # Update index entries for tasks in the renamed board.
        for task in self.get_tasks(f"/{board.name}"):
            self.index_service.update_task(task)

        return board

    def delete_board(self, path: str) -> None:
        """
        Recursively delete a board directory and remove it from .kanban-store/boards/.metadata.
        Raises BoardNotFound if the board does not exist.  Also removes all
        index entries for tasks that belonged to the board and clears the current
        context if it pointed at the deleted board.
        """

        # TODO: do not allow the user to delete a board that has tasks in it, or at least require a --force flag
        # TODO: do not allow the user to delete a board that is the current context

        board, _, _ = self.path_components(path)
        tasks = self.get_tasks(path)
        self.repository.delete_board(board)
        
        # Clear current context if it points to the deleted board.
        if self._user_context.board == board:
            self.clear_user_context()

        # Remove all index entries for tasks in the deleted board.
        for task in tasks:
            self.index_service.delete_task(task)

        return board


    # ── Columns ───────────────────────────────────────────────────────────────

    def get_columns(
        self,
        board:   str | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Column]:
        """
        Return all columns for the given board.  Falls back to the current
        context board if board is None; raises NoBoardInContext if neither is
        set.  sort accepts "title"; omitting it preserves the order in the
        board's .metadata file.
        """
        board, _, _ = self.path_components(board)
        return self.repository.get_columns(board)

    def create_column(self, path: str) -> Column:
        """
        Create a new column subdirectory for the provided path.  Raises
        BoardNotFound if the board does not exist and ColumnAlreadyExists if
        the column name is already taken within that board.  Appends the new
        column to the board's .metadata file and commits.
        """
        board, column, _ = self.path_components(path)
        return self.repository.create_column(board, column)

    def rename_column(self, path: str, new_name: str) -> Column:
        """
        Rename a column subdirectory and update the board's .metadata file.
        Raises BoardNotFound, ColumnNotFound, or ColumnAlreadyExists as
        appropriate.  Tasks inside the column are untouched; their paths
        update implicitly via the directory rename.  Updates the current
        context if the renamed column was the current one.
        """
        board, column, _ = self.path_components(path)
        renamed_column = self.repository.rename_column(board, column, new_name)

        # Update current context if it points at the renamed column.
        if self._user_context.board == board and self._user_context.column == column:
            self._user_context.column = renamed_column.name

        # Update index entries for tasks in the renamed column.
        for task in self.get_tasks(f"{board}/{new_name}"):
            self.index_service.update_task(task)

        return renamed_column

    def reorder_column(self, path: str, position: int) -> list[Column]:
        """
        Move a column to the given 1-based position in the board's .metadata
        file.  Raises BoardNotFound or ColumnNotFound if either does not
        exist.  Position is clamped to the valid range rather than raising on
        out-of-bounds values.  Returns the full updated column list so the
        CLI can confirm the new order.
        """
        board, column, _ = self.path_components(path)
        return self.repository.reorder_column(board, column, position)  

    def delete_column(self, path: str) -> None:
        """
        Delete a column subdirectory and all tasks it contains.  Raises
        BoardNotFound or ColumnNotFound if either does not exist.  Removes
        all index entries for tasks in the column, updates the board's .metadata
        file, and clears the current context column if it pointed here.
        """
        board, column, _ = self.path_components(path)
        tasks = self.get_tasks(path)
        self.repository.delete_column(board, column)

        # If current context points at this column, clear column only.
        if self._user_context.board == board and self._user_context.column == column:
            self._user_context.column = None

        # Remove all index entries for tasks in the deleted column.
        for task in tasks:
            self.index_service.delete_task(task)

        return None


    # ── Tasks ─────────────────────────────────────────────────────────────────

    def get_tasks(
        self,
        path:    str | None = None,
        filter:  TaskFilter = TaskFilter(),
        sort:    str | None = "column",
        reverse: bool = False,
    ) -> list[Task]:
        """
        Return tasks for the given board/column, applying filters and sort in
        the service layer rather than in the repository.  board and column both
        fall back to the current context; omitting column returns tasks across
        all columns of the board.  sort accepts "title", "priority", "due-date",
        "created-at", "updated-at", or "created-by".
        """
        board, column, _ = self.path_components(path)
        tasks = self.repository.get_tasks(board=board, column=column)

        if filter:
            tasks = [t for t in tasks if _task_matches_filter(t, filter)]

        if not sort:
            return tasks

        def _value(task: Task):
            if sort == "title":
                return task.title.lower()
            if sort == "column":
                return (task.column or "").lower()
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
        board, column, title = self.path_components(path)

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
            slug=kebab_case(title),
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
        self.index_service.update_task(created_task)
        return created_task

    def get_task(
        self,
        path: str,
    ) -> Task:
        """
        Resolve and return a single task by title slug.  Delegates
        location resolution to resolve_path, which applies the
        explicit → context → index-search chain and raises TaskNotFound or
        AmbiguousTaskReference if resolution fails.
        """
        board, column, title = self.path_components(path)
        filename = kebab_case(title)
        return self.repository.get_task(board, column, filename)

    def edit_task(
        self,
        path: str,
    ) -> Task:
        """Open's the task's .md file in an editor, then reads the updated 
        content and metadata and applies changes to the task.  Raises 
        TaskNotFound or AmbiguousTaskReference if the task cannot be resolved.  
        Updates the index and commits."""
        task = self.get_task(path)
        markdown = self._task_to_markdown(task)

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".md",
                prefix="kanban-task-",
                delete=False,
            ) as tmp:
                tmp.write(markdown)
                tmp.flush()
                tmp_path = tmp.name

            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
            editor_cmd = shlex.split(editor)
            subprocess.run([*editor_cmd, tmp_path], check=True)

            with open(tmp_path, "r", encoding="utf-8") as f:
                edited_text = f.read()

            edited_task = self._task_from_markdown(edited_text, original=task)
            updated = self.repository.update_task(edited_task)
            self.index_service.update_task(updated)
            return updated
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

    def update_task(
        self,
        path:     str,
        updates:  TaskUpdateParams,
    ) -> Task:
        """
        Apply TaskUpdateParams to an existing task's frontmatter and body,
        updating updated_at automatically.  If updates.title differs from the
        current title, the file is renamed to match the new slug.  Raises
        TaskNotFound or AmbiguousTaskReference via path_components.
        Updates the index entry and commits.
        """
        task = self.get_task(path)

        # TODO: how do we handle removing a field?
        # If the user wants to remove a due date, for example, they would have to pass in updates.due_date = None, but that is indistinguishable from "don't change the due date".
        # We could use a sentinel value or a separate "remove" flag for each field, but that seems cumbersome.  For now, we will just treat None as "don't change".

        due_date = updates.due_date

        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        if updates.title and updates.title != task.title:
            task.title = updates.title
            task.slug = kebab_case(updates.title)
        if updates.assignee is not None:
            task.assignee = updates.assignee
        if updates.priority is not None:
            task.priority = updates.priority
        if updates.tags is not None:
            task.tags = updates.tags
        if updates.due_date is not None:
            task.due_date = due_date
        if updates.created_by is not None:
            task.created_by = updates.created_by

        updated = self.repository.update_task(task)
        self.index_service.update_task(updated)
        return updated

    def move_task(
        self,
        path:   str,
        dest:   str,
    ) -> Task:
        """
        Move a task's .md file to a new board/column location.  dest may be
        "<board>/<column>" or bare "<column>", in which case the source board
        is assumed.  Validates that the destination column exists before moving.
        Raises TaskNotFound, AmbiguousTaskReference, BoardNotFound, or
        ColumnNotFound as appropriate.  Updates the index and commits.
        """
        dest_board, dest_column, dest_title = self.path_components(dest)
        task = self.get_task(path)

        #TODO: dest_title should never be none in this case?

        repo_dest = Path(dest_board) / dest_column
        if dest_title:
            repo_dest = repo_dest / dest_title
        result = self.repository.move_task(task, repo_dest)
        self.index_service.update_task(result)
        return result

    def delete_task(
        self,
        path: str,
    ) -> None:
        """
        Delete a task's .md file from disk.  Raises TaskNotFound or
        AmbiguousTaskReference via path_components.  Removes the task's
        index entry and commits.
        """
        task = self.get_task(path)
        self.repository.delete_task(task)
        self.index_service.delete_task(task)
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
        title:       str | None = None,
        limit:       int = 20,
    ) -> list[GitCommit]:
        """
        Return structured commit history, optionally scoped to a board, column,
        or specific task by UUID.  When title is provided, resolves the
        task first via _resolve_path_into_parts so that history follows the file
        through any renames.  Delegates path filtering to GitService.
        """
        raise NotImplementedError()

    def squash(self, board: str | None = None) -> GitCommit:
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

    def set_config(self, keypath: str, value: str) -> None:
        """
        Persist a configuration value to .kanban/.config under the given key.
        Raises InvalidConfigKey if the key is not in the supported set.  No
        git commit — config is local working state, like current context.
        """
        self.repository.set_config(keypath, value)

    # ── Userdata ──────────────────────────────────────────────────────────────

    def get_userdata(self, keypath: str) -> str | None:
        """
        Read a userdata value from .kanban/userdata.  Raises UserdataKeyNotSet
        if the key does not exist.
        """
        return self.repository.get_userdata(keypath)

    def set_userdata(self, keypath: str, value: str) -> None:
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

    def _task_to_markdown(self, task: Task) -> str:
        """Serialize a task to editable markdown with YAML-like frontmatter."""
        tags = ", ".join(task.tags or [])
        due_date = task.due_date.isoformat() if task.due_date else ""
        created_at = task.created_at.isoformat() if task.created_at else ""
        updated_at = task.updated_at.isoformat() if task.updated_at else ""

        lines = [
            "---",
            f"id: {task.id}",
            f"title: {task.title}",
            f"board: {task.board or ''}",
            f"column: {task.column or ''}",
            f"assignee: {task.assignee or ''}",
            f"priority: {task.priority or ''}",
            f"due_date: {due_date}",
            f"tags: {tags}",
            f"created_by: {task.created_by or ''}",
            f"created_at: {created_at}",
            f"updated_at: {updated_at}",
            "---",
            task.body or "",
        ]
        return "\n".join(lines)

    def _task_from_markdown(self, content: str, *, original: Task) -> Task:
        """Parse editable markdown frontmatter/body back into a Task."""
        lines = content.splitlines()
        if len(lines) < 3 or lines[0].strip() != "---":
            raise ValueError("Edited task markdown must start with frontmatter delimiter '---'")

        end_idx: int | None = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            raise ValueError("Edited task markdown frontmatter is missing closing delimiter '---'")

        frontmatter: dict[str, str] = {}
        for line in lines[1:end_idx]:
            if not line.strip() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

        body = "\n".join(lines[end_idx + 1:]).strip("\n")

        title = frontmatter.get("title", original.title).strip() or original.title
        assignee = frontmatter.get("assignee", "") or None
        priority = frontmatter.get("priority", "") or None
        created_by = frontmatter.get("created_by", "") or None

        due_date_raw = frontmatter.get("due_date", "").strip()
        due_date: datetime | None = None
        if due_date_raw:
            due_date = datetime.fromisoformat(due_date_raw)

        tags_raw = frontmatter.get("tags", "")
        tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]

        return Task(
            id=original.id,
            title=title,
            slug=original.slug,
            board=original.board,
            column=original.column,
            created_by=created_by,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
            tags=tags,
            created_at=original.created_at,
            updated_at=original.updated_at,
            body=body,
        )

    def _commit(self, type: str, scope: str, description: str) -> None:
        """Compose a structured commit message and delegate to GitService."""
        raise NotImplementedError()