from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import os
import re
import shlex
import subprocess
import tempfile
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import KanbanRepository, ColumnNotFound, BoardNotFound
from services.git import GitService
from services.index import IndexService


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

    def __init__(self, repository: KanbanRepository, index_service: IndexService, git_service: GitService, user_context: UserContext) -> None:
        """
        Assemble the facade from its domain services.  All services are
        injected rather than instantiated here so that the InMemoryRepository
        can be swapped in for tests without any other changes.
        """
        self.repository = repository
        self.index_service = index_service
        self.git_service = git_service
        self._user_context = user_context

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

        # TODO: Not intuitive at all. more like a create from path
        self.create_board("main")
        self.create_column("main/todo")
        self.create_column("main/in-progress")
        self.create_column("main/in-review")
        self.create_column("main/done")
        
        self.update_user_context(board="main", column="todo")
        self.set_config("initialized", "true")

        kanban_root = path / ".kanban"
        return KanbanRoot(
            path=kanban_root,
            git_init=False,
            boards_dir=kanban_root / "boards",
        )


    # ── User context ────────────────────────────────────────────────────────

    @property
    def user_context(self) -> UserContext:
        """Return the current user context without modifying it."""
        return self._user_context

    @property
    def working_path(self) -> Path:
        return self.user_context.path
    
    def update_user_context(self, board: str | None, column: str | None) -> UserContext:
        """Set the board/column context"""
        self._user_context.board = board
        self._user_context.column = column

    def clear_user_context(self) -> UserContext:
        """Clear the user context with initial default values."""
        self._user_context = UserContext()
        return self._user_context

    def resolve_path(self, path: str | None = None) -> Path:
        """
        Resolve a user-provided path into an absolute Path object.  
        The path may be absolute (starting with "/") or relative to the current user context.
        """
        # print(f"Resolving path: '{path}' with working path: '{self.working_path}'")
        if path.startswith("/"):
            return Path(path)
        else:
            return Path(self.working_path) / (path or "")

    def _resolve_path_into_components(self, path: str | None = None) -> tuple[str | None, str | None, str | None]:
        """Resolve a [BOARD/][COLUMN/]TITLE_OR_ID path into its components."""
        path = self.resolve_path(path)
        # print(f"Resolved path: {path}")
        parts = path.parts # ["/", board|None, column|None, title-or-id|None]
        return parts[1] if len(parts) > 1 else None, \
               parts[2] if len(parts) > 2 else None, \
               parts[3] if len(parts) > 3 else None

    # TODO: this will end up replacing the path in the promt
    def completions_for_path(self, text: str) -> list[str]:
        """Return a list of valid path completions for the given partial text."""
        
        board, column, title_or_id = self._resolve_path_into_components(text)

        if board and column and title_or_id:
            completions = [f"{t.title}" for t in self.repository.list_tasks(board=board, column=column) if t.title.startswith(title_or_id)]
        elif board and column:
            # check if column is complete or partial, and if partial, only return columns that match the partial
            # otherwise return all tasks in the column
            if self._column_exists(board, column):
                completions = [f"{t.title}" for t in self.repository.list_tasks(board=board, column=column) if t.title.startswith(column or "")]
            else:
                completions = [f"{c.name}/" for c in self.repository.list_columns(board) if c.name.startswith(column or "")]
        elif board:
            # check if board is complete or partial, and if partial, only return boards that match the partial
            # otherwise return all columns in the board
            if self._board_exists(board):
                completions = [f"{c.name}/" for c in self.repository.list_columns(board) if c.name.startswith(column or "")]
            else:
                completions = [f"{b.name}/" for b in self.repository.list_boards() if b.name.startswith(board or "")]
        else:
            completions = [f"{b.name}/" for b in self.repository.list_boards() if b.name.startswith(board or "")]

        return completions

    def _board_exists(self, board: str) -> bool:
        """Return True if the given board exists in the repository."""
        try:
            self.repository.get_board(board)
            return True
        except BoardNotFound:
            return False

    def _column_exists(self, board: str, column: str) -> bool:
        """Return True if the given column exists in the repository."""
        try:
            self.repository.get_column(board, column)
            return True
        except (BoardNotFound, ColumnNotFound):
            return False

    # TODO: rename to change_dir, because that's what it's doing
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
            return self.clear_user_context()

        if path is None:
            return self.user_context

        board: str | None = None
        column: str | None = None

        if "/" in path:
            board, column = path.split("/", 1)
            if not board or not column:
                raise ValueError("Path must be BOARD or BOARD/COLUMN")
        else:
            board = path
            active_board = self.user_context.board
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

        self.update_user_context(board=board, column=column)
        return self.user_context

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
        board = self.repository.rename_board(board, new_name)

        # Keep active context in sync.
        self._user_context.board = board.name

        return board

    def delete_board(self, board: str) -> None:
        """
        Recursively delete a board directory and remove it from .kanban/.order.
        Raises BoardNotFound if the board does not exist.  Also removes all
        index entries for tasks that belonged to the board and clears the active
        context if it pointed at the deleted board.
        """
        board = self.repository.delete_board(board)
        
        # Clear active context if it points to the deleted board.
        if self._user_context.board == name:
            self.clear_user_context()

        return board


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
        board, _, _ = self._resolve_path_into_components(board)
        return self.repository.list_columns(board)

    def create_column(self, path: str) -> Column:
        """
        Create a new column subdirectory for the provided path.  Raises
        BoardNotFound if the board does not exist and ColumnAlreadyExists if
        the column name is already taken within that board.  Appends the new
        column to the board's .order file and commits.
        """
        board, column, _ = self._resolve_path_into_components(path)
        return self.repository.create_column(board, column)

    def rename_column(self, path: str, new_name: str) -> Column:
        """
        Rename a column subdirectory and update the board's .order file.
        Raises BoardNotFound, ColumnNotFound, or ColumnAlreadyExists as
        appropriate.  Tasks inside the column are untouched; their paths
        update implicitly via the directory rename.  Updates the active
        context if the renamed column was the active one.
        """
        board, column, _ = self._resolve_path_into_components(path)
        renamed_column = self.repository.rename_column(board, column, new_name)

        # Update active context if it points at the renamed column.
        if self._user_context.board == board and self._user_context.column == column.name:
            self._user_context.column = renamed_column.name

        return renamed_column

    def reorder_column(self, path: str, position: int) -> list[Column]:
        """
        Move a column to the given 1-based position in the board's .order
        file.  Raises BoardNotFound or ColumnNotFound if either does not
        exist.  Position is clamped to the valid range rather than raising on
        out-of-bounds values.  Returns the full updated column list so the
        CLI can confirm the new order.
        """
        board, column, _ = self._resolve_path_into_components(path)
        return self.repository.reorder_column(board, column, position)  

    def delete_column(self, path: str) -> None:
        """
        Delete a column subdirectory and all tasks it contains.  Raises
        BoardNotFound or ColumnNotFound if either does not exist.  Removes
        all index entries for tasks in the column, updates the board's .order
        file, and clears the active context column if it pointed here.
        """
        board, column, _ = self._resolve_path_into_components(path)
        self.repository.delete_column(board, column)

        # If current context points at this column, clear column only.
        if self._user_context.board == board and self._user_context.column == column:
            self._user_context.column = None

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
        board, column, _ = self._resolve_path_into_components(path)
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
        board, column, title = self._resolve_path_into_components(path)

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
        location resolution to resolve_path, which applies the
        explicit → context → index-search chain and raises TaskNotFound or
        AmbiguousTaskReference if resolution fails.
        """
        board, column, title_or_id = self._resolve_path_into_components(path)
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
            self.index_service.update(updated)
            return updated
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

    def update_task(
        self,
        path: str,
        updates:     TaskUpdateParams,
    ) -> Task:
        """
        Apply TaskUpdateParams to an existing task's frontmatter and body,
        updating updated_at automatically.  If updates.title differs from the
        current title, the file is renamed to match the new slug.  Raises
        TaskNotFound or AmbiguousTaskReference via _resolve_path_into_components.
        Updates the index entry and commits.
        """
        board, column, title_or_id = self._resolve_path_into_components(path)
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
        board, column, title_or_id = self._resolve_path_into_components(path)
        _ = board, column, title_or_id, dest
        ...

    def delete_task(
        self,
        path: str,
    ) -> None:
        """
        Delete a task's .md file from disk.  Raises TaskNotFound or
        AmbiguousTaskReference via _resolve_path_into_components.  Removes the task's
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
        task first via _resolve_path_into_parts so that history follows the file
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

    def _to_kebab_case(self, text: str) -> str:
        """Convert free-form title text into a kebab-case filename slug."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if not slug:
            raise ValueError("Task title must contain at least one alphanumeric character")
        return slug

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
        ...