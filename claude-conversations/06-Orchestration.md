# Orchestration

Date: 20260614_040242

ID: db37f80e-e277-4d3b-918f-2c80754447f9


**User**: [2026-06-14 02:26:23]

Let's take a closer look at the KanbanServices orchestration layer

---


**Claude**: [2026-06-14 02:27:34]

 I'll read the frontend design skill before we dive in, though this is primarily a backend/architecture discussion. Let me think through the KanbanService design carefully.

Let me first make sure I understand the full picture before laying out the design.

The design module is loaded. Now let me think carefully about the `KanbanService` orchestration layer — its responsibilities, method surface, error handling contracts, and how it sequences operations across domain services and git.

Here's a thorough breakdown of the `KanbanService` design.

---

## Responsibilities

The facade owns exactly three things: **sequencing**, **cross-domain validation**, and **partial-failure handling**. Everything else belongs in a domain service or the CLI.

- It composes operations (call `TaskService.create`, then `IndexService.update`, then `GitService.commit`) but never performs them directly
- It enforces invariants that span services (e.g. "the destination column must exist before moving a task")
- It translates domain exceptions into a result that the CLI can display, without letting storage or git exceptions leak upward
- It never formats output — it returns domain dataclasses; the CLI layer renders them

---

## Method surface

The facade method per CLI command is a natural fit. Each method follows the same internal contract: validate → delegate → index → commit.

```python
class KanbanService:
    def __init__(
        self,
        board_service: BoardService,
        task_service: TaskService,
        search_service: SearchService,
        index_service: IndexService,
        git_service: GitService,
    ): ...

    # --- Board ---
    def create_board(self, name: str) -> Board: ...
    def rename_board(self, board: str, new_name: str) -> Board: ...
    def delete_board(self, board: str) -> None: ...
    def list_boards(self, sort: str | None, reverse: bool) -> list[Board]: ...

    # --- Column ---
    def create_column(self, board: str, column: str) -> Column: ...
    def rename_column(self, board: str, column: str, new_name: str) -> Column: ...
    def reorder_column(self, board: str, column: str, position: int) -> list[Column]: ...
    def delete_column(self, board: str, column: str) -> None: ...
    def list_columns(self, board: str, sort: str | None, reverse: bool) -> list[Column]: ...

    # --- Task ---
    def create_task(self, board: str, column: str, title: str, **metadata) -> Task: ...
    def show_task(self, board: str, column: str, title_or_id: str) -> Task: ...
    def edit_task(self, board: str, column: str, title_or_id: str, **updates) -> Task: ...
    def move_task(self, board: str, column: str, title_or_id: str, dest: str) -> Task: ...
    def delete_task(self, board: str, column: str, title_or_id: str) -> None: ...
    def list_tasks(self, board: str, column: str | None, filters: TaskFilters) -> list[Task]: ...

    # --- Search ---
    def search(self, query: str, filters: TaskFilters) -> list[Task]: ...

    # --- Git ---
    def log(self, board: str | None, column: str | None, task_id: str | None, limit: int) -> list[GitCommit]: ...
    def squash(self, board: str | None) -> None: ...

    # --- Status / config ---
    def status(self) -> KanbanStatus: ...
    def set_config(self, key: str, value: str) -> None: ...
    def get_config(self, key: str) -> str: ...
```

The `**metadata` / `**updates` patterns should be typed through a `TaskCreateParams` / `TaskUpdateParams` dataclass rather than raw kwargs — this keeps the CLI→facade contract explicit and avoids positional-argument drift as fields are added.

---

## Path resolution

Path resolution happens **entirely inside the facade**, not in the CLI and not in domain services. The three-step resolution rule (explicit → active context → index search) is a coordinating concern:

```python
def _resolve_task_location(
    self,
    board: str | None,
    column: str | None,
    title_or_id: str,
) -> tuple[str, str, Task]:
    if board and column:
        # Explicit — delegate directly
        task = self.task_service.get(board, column, title_or_id)
        return board, column, task

    ctx = self._active_context()
    effective_board = board or ctx.board

    # Index search, scoped to board if known
    results = self.index_service.find(title_or_id, board=effective_board)
    if len(results) == 0:
        raise TaskNotFound(title_or_id)
    if len(results) > 1:
        raise AmbiguousTaskReference(title_or_id, results)

    hit = results[0]
    return hit.board, hit.column, hit
```

The active context (the `.config` file tracking `use <board>/<column>`) is read here too, not in the domain services.

---

## Operation sequence

Every mutating method follows the same four-phase pattern. Here's `move_task` as a worked example because it touches the most concerns:

```python
def move_task(
    self,
    board: str | None,
    column: str | None,
    title_or_id: str,
    dest: str,
) -> Task:
    # 1. Resolve source
    src_board, src_col, task = self._resolve_task_location(board, column, title_or_id)

    # 2. Parse and validate destination
    dest_board, dest_col = self._parse_dest(dest, fallback_board=src_board)
    if not self.board_service.column_exists(dest_board, dest_col):
        raise ColumnNotFound(f"{dest_board}/{dest_col}")

    # 3. Delegate to domain service
    moved_task = self.task_service.move(
        src_board, src_col, task.id, dest_board, dest_col
    )

    # 4. Update index
    self.index_service.update(moved_task)

    # 5. Commit
    self.git_service.commit(
        f"task: move '{task.title}' "
        f"from {src_board}/{src_col} to {dest_board}/{dest_col}"
    )

    return moved_task
```

The domain service handles the file rename/move atomically. The facade never touches the filesystem.

---

## Error handling and partial failure

The key contract: **domain exceptions propagate up; storage and git exceptions are caught and wrapped**.

```python
class KanbanError(Exception): ...
class PartialFailure(KanbanError):
    """Operation succeeded but a secondary step (index/git) failed."""
    def __init__(self, result, failed_step: str, cause: Exception): ...
```

The facade wraps git and index calls:

```python
    # After task_service.move() succeeds:
    try:
        self.index_service.update(moved_task)
    except Exception as e:
        # Index is a cache — stale is recoverable, not fatal
        logger.warning("Index update failed: %s", e)

    try:
        self.git_service.commit(message)
    except Exception as e:
        # Git failure: operation succeeded but history is incomplete
        raise PartialFailure(moved_task, "git commit", e) from e
```

The CLI decides whether to surface a `PartialFailure` as a warning (and still return exit 0 with the result) or as an error. The domain result is always included in the exception so the CLI has something to render.

---

## Git commit message composition

Commit messages are composed in the facade, not in `GitService` (which only knows how to commit) and not in domain services (which don't know about git). A structured format keeps `kanban log` parseable:

```
<type>(<scope>): <description>

type:  board | column | task | config
scope: <board>[/<column>]
```

Examples:
```
task(ops/todo): create 'Fix login bug'
task(my-project/in-progress): move from my-project/todo
column(ops): rename 'todo' → 'backlog'
board: delete 'ops'
```

The facade holds a private `_commit_message(type, scope, description)` helper. This makes `kanban squash` trivial to implement — the `GitService` just soft-resets and re-commits with a summary derived from the individual messages.

---

## Cross-cutting concerns the facade owns

| Concern | Handled by |
|---|---|
| Active context read/write (`kanban use`) | Facade reads `.config`; delegates write to `ConfigService` or directly |
| Ambiguous reference errors | Facade after index search returns >1 hit |
| Board/column existence pre-checks | Facade before calling `TaskService.move` or `TaskService.create` |
| Index staleness detection | `IndexService.find()` can return a `stale=True` flag; facade triggers a rescan |
| `--quiet` flag | Facade is unaware — CLI suppresses output; facade always returns the domain object |
| Formatting | Facade never touches it — always returns dataclasses |

---

## What the facade explicitly does not do

- It does not parse CLI flags — those arrive as already-parsed Python values
- It does not format output strings
- It does not know about `argparse`, `rich`, or any TUI framework
- It does not hold retry logic (that belongs in `GitService` if needed)
- It does not own the repository — that is injected into domain services at startup

This keeps the facade honest: when the TUI lands, it calls exactly the same `KanbanService` methods with the same signatures, and the only new code is the TUI rendering layer.

---


**User**: [2026-06-14 03:44:40]

The python definition for the `KanbanService` looks good but is missing some commands. Add methods to handle the `init` and `use`  commands

---


**Claude**: [2026-06-14 03:45:02]

 Looking at the CLI spec:

```
kanban init
kanban use <board>/<column>
kanban use <board>
kanban use --clear
```

These two commands are interesting because they sit slightly outside the normal CRUD pattern — `init` is a one-time bootstrap, and `use` manages persistent context state rather than domain objects. Here's how they fit into the facade:

```python
class KanbanService:
    def __init__(
        self,
        board_service: BoardService,
        task_service: TaskService,
        search_service: SearchService,
        index_service: IndexService,
        git_service: GitService,
    ): ...

    # --- Init ---
    def init(self, path: Path) -> KanbanRoot: ...

    # --- Context ---
    def use(
        self,
        board: str | None = None,
        column: str | None = None,
        clear: bool = False,
    ) -> ActiveContext: ...
```

---

## `init`

```python
def init(self, path: Path) -> KanbanRoot:
```

`init` is the only method that creates the root `.kanban/` structure itself, so it runs before any services can operate normally. Its job is to:

1. Check the target path doesn't already contain a `.kanban/` directory — raise `AlreadyInitialized` if so
2. Delegate to `BoardService` (or a dedicated bootstrap helper) to create the directory skeleton: `.kanban/`, `boards/`, `.config`, `.order`, `.index.db`
3. Call `GitService.init()` to initialize the git repo (or detect an existing one and just stage the new files)
4. Commit the initial state: `"chore: initialize kanban repository"`
5. Return a `KanbanRoot` dataclass describing what was created

The `path` argument lets the CLI pass `cwd` by default but allow `kanban init ./my-project` as a future affordance. The facade shouldn't assume it always operates on the process's working directory.

One subtlety: `init` can't follow the normal four-phase sequence (validate → delegate → index → commit) because the index doesn't exist yet. It's the one method where the facade must orchestrate creation order explicitly — filesystem first, git last, index bootstrapped in between.

---

## `use`

```python
def use(
    self,
    board: str | None = None,
    column: str | None = None,
    clear: bool = False,
) -> ActiveContext:
```

`use` is a context mutation, not a domain mutation — it writes to `.kanban/.config` and nothing else. No index update, no git commit. The three call shapes map cleanly onto the single signature:

| CLI invocation | `board` | `column` | `clear` |
|---|---|---|---|
| `kanban use my-project/todo` | `"my-project"` | `"todo"` | `False` |
| `kanban use my-project` | `"my-project"` | `None` | `False` |
| `kanban use --clear` | `None` | `None` | `True` |

The facade's responsibilities here:

1. If `clear=True`, wipe both fields in `.config` and return an empty `ActiveContext` — no validation needed
2. Otherwise, validate that the referenced board exists (raise `BoardNotFound` if not), and if a column is given, that it exists too (raise `ColumnNotFound`)
3. Write the new context to `.config` via whatever owns config persistence — this could live in `ConfigService` or a thin `ContextRepository`, but the facade doesn't do the file write directly
4. Return the new `ActiveContext` so the CLI can confirm: `Now using my-project/todo`

No git commit here — context is local working state, not part of the project history. This is the same reasoning as `.gitignore`-ing editor settings: the active board is your personal cursor, not a project artifact. You may want to add `.kanban/.config` to `.gitignore` during `init` for exactly this reason.

The `ActiveContext` return type (rather than `None`) is important — the CLI needs something to render, and returning the object keeps the facade testable without inspecting filesystem side effects.

---


**User**: [2026-06-14 03:48:36]

Show me the method surface for the KanbanService including the `init` and `use` commands

---


**Claude**: [2026-06-14 03:49:15]

```python
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


# ── Params ────────────────────────────────────────────────────────────────────

@dataclass
class TaskFilters:
    assignee:   str | None = None
    priority:   str | None = None          # "low" | "medium" | "high"
    tag:        str | None = None
    due_before: datetime | None = None
    due_after:  datetime | None = None
    created_by: str | None = None

@dataclass
class TaskCreateParams:
    title:      str
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
class ActiveContext:
    board:  str | None
    column: str | None

    @property
    def is_empty(self) -> bool:
        return self.board is None and self.column is None


# ── KanbanService ─────────────────────────────────────────────────────────────

class KanbanService:

    def __init__(
        self,
        board_service:  BoardService,
        task_service:   TaskService,
        search_service: SearchService,
        index_service:  IndexService,
        git_service:    GitService,
    ) -> None: ...


    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def init(self, path: Path = Path(".")) -> KanbanRoot:
        """
        Create the .kanban/ directory skeleton, initialize git, and write the
        first commit.  Raises AlreadyInitialized if .kanban/ already exists at
        path.  This is the only method that runs before the services are fully
        operational, so it orchestrates creation order directly: filesystem
        first, index second, git last.
        """
        ...

    # ── Active context ─────────────────────────────────────────────────────────

    def use(
        self,
        board:  str | None = None,
        column: str | None = None,
        clear:  bool = False,
    ) -> ActiveContext:
        """
        Set or clear the active board/column context stored in .kanban/.config.
        Validates that the referenced board (and column, if given) exist before
        writing.  No git commit — context is local working state.

        kanban use my-project/todo  →  use(board="my-project", column="todo")
        kanban use my-project       →  use(board="my-project")
        kanban use --clear          →  use(clear=True)
        """
        ...

    def get_context(self) -> ActiveContext:
        """Return the current active context without modifying it."""
        ...


    # ── Boards ────────────────────────────────────────────────────────────────

    def list_boards(
        self,
        sort:    str | None = None,   # "title"
        reverse: bool = False,
    ) -> list[Board]: ...

    def create_board(self, name: str) -> Board: ...

    def rename_board(self, board: str, new_name: str) -> Board: ...

    def delete_board(self, board: str) -> None: ...


    # ── Columns ───────────────────────────────────────────────────────────────

    def list_columns(
        self,
        board:   str | None = None,   # falls back to active context
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Column]: ...

    def create_column(self, board: str, column: str) -> Column: ...

    def rename_column(self, board: str, column: str, new_name: str) -> Column: ...

    def reorder_column(self, board: str, column: str, position: int) -> list[Column]:
        """Returns the full updated column order for the board."""
        ...

    def delete_column(self, board: str, column: str) -> None: ...


    # ── Tasks ─────────────────────────────────────────────────────────────────

    def list_tasks(
        self,
        board:   str | None = None,
        column:  str | None = None,
        filters: TaskFilters = TaskFilters(),
        sort:    str | None = None,   # "title"|"priority"|"due-date"|"created-at"|"updated-at"|"created-by"
        reverse: bool = False,
    ) -> list[Task]: ...

    def create_task(
        self,
        board:  str,
        column: str,
        params: TaskCreateParams,
    ) -> Task: ...

    def show_task(
        self,
        title_or_id: str,
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task: ...

    def edit_task(
        self,
        title_or_id: str,
        updates:     TaskUpdateParams,
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task: ...

    def move_task(
        self,
        title_or_id: str,
        dest:        str,             # "<board>/<column>" or "<column>"
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task: ...

    def delete_task(
        self,
        title_or_id: str,
        board:       str | None = None,
        column:      str | None = None,
    ) -> None: ...


    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query:   str,
        filters: TaskFilters = TaskFilters(),
        board:   str | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Task]: ...


    # ── Git ───────────────────────────────────────────────────────────────────

    def log(
        self,
        board:       str | None = None,
        column:      str | None = None,
        title_or_id: str | None = None,
        limit:       int = 20,
    ) -> list[GitCommit]: ...

    def squash(self, board: str | None = None) -> GitCommit:
        """
        Collapse all commits since the last squash (or since init) into one.
        Scoped to a single board if provided.  Returns the new squash commit.
        """
        ...


    # ── Config ────────────────────────────────────────────────────────────────

    def set_config(self, key: str, value: str) -> None: ...

    def get_config(self, key: str) -> str: ...


    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> KanbanStatus:
        """
        Snapshot of the repository: active context, board/column/task counts,
        index freshness, and whether there are uncommitted changes in git.
        """
        ...


    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve_task_location(
        self,
        title_or_id: str,
        board:       str | None,
        column:      str | None,
    ) -> tuple[str, str, Task]:
        """
        Explicit path → active context → index search.
        Raises TaskNotFound or AmbiguousTaskReference.
        """
        ...

    def _resolve_board(self, board: str | None) -> str:
        """Return explicit board or fall back to active context board."""
        ...

    def _commit(self, type: str, scope: str, description: str) -> None:
        """Compose a structured commit message and delegate to GitService."""
        ...
```

A few design decisions worth calling out:

**Argument order on task methods.** The optional `board` and `column` are at the end, not the front. This is intentional — `title_or_id` is the required discriminator; the location arguments are resolution hints that default to context. It makes call sites read naturally: `service.show_task("fix-login-bug")` for the common case, `service.show_task("fix-login-bug", board="ops", column="todo")` when you need to be explicit.

**`TaskCreateParams` vs `TaskUpdateParams` are separate types.** `create` requires `title`; `edit` makes it optional (a rename). Keeping them distinct makes the type signatures honest and prevents passing a half-constructed create params to an edit call by accident.

**`squash` returns `GitCommit`.** The CLI needs something to render ("Squashed 14 commits → abc1234"), and returning the new commit object keeps the facade testable without inspecting git state directly.

**`get_context` alongside `use`.** The CLI needs to display current context for `kanban status` and for showing the prompt hint in the TUI. A read-only getter prevents it from having to call `use()` with no arguments and guess at the semantics.

---


**User**: [2026-06-14 03:51:30]

Good. Add a docstring to each method that does not already have one

---


**Claude**: [2026-06-14 03:52:15]

 ```python
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime


# ── Params ────────────────────────────────────────────────────────────────────

@dataclass
class TaskFilters:
    assignee:   str | None = None
    priority:   str | None = None          # "low" | "medium" | "high"
    tag:        str | None = None
    due_before: datetime | None = None
    due_after:  datetime | None = None
    created_by: str | None = None

@dataclass
class TaskCreateParams:
    title:      str
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
class ActiveContext:
    board:  str | None
    column: str | None

    @property
    def is_empty(self) -> bool:
        return self.board is None and self.column is None


# ── KanbanService ─────────────────────────────────────────────────────────────

class KanbanService:

    def __init__(
        self,
        board_service:  BoardService,
        task_service:   TaskService,
        search_service: SearchService,
        index_service:  IndexService,
        git_service:    GitService,
    ) -> None:
        """
        Assemble the facade from its domain services.  All services are
        injected rather than instantiated here so that the InMemoryRepository
        can be swapped in for tests without any other changes.
        """
        ...


    # ── Bootstrap ─────────────────────────────────────────────────────────────

    def init(self, path: Path = Path(".")) -> KanbanRoot:
        """
        Create the .kanban/ directory skeleton, initialize git, and write the
        first commit.  Raises AlreadyInitialized if .kanban/ already exists at
        path.  This is the only method that runs before the services are fully
        operational, so it orchestrates creation order directly: filesystem
        first, index second, git last.
        """
        ...


    # ── Active context ────────────────────────────────────────────────────────

    def use(
        self,
        board:  str | None = None,
        column: str | None = None,
        clear:  bool = False,
    ) -> ActiveContext:
        """
        Set or clear the active board/column context stored in .kanban/.config.
        Validates that the referenced board (and column, if given) exist before
        writing.  No git commit — context is local working state.

        kanban use my-project/todo  →  use(board="my-project", column="todo")
        kanban use my-project       →  use(board="my-project")
        kanban use --clear          →  use(clear=True)
        """
        ...

    def get_context(self) -> ActiveContext:
        """Return the current active context without modifying it."""
        ...


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
        ...

    def create_board(self, name: str) -> Board:
        """
        Create a new board directory under .kanban/boards/.  Raises
        BoardAlreadyExists if a board with that name is already present.
        Appends the new board to .kanban/.order and commits.
        """
        ...

    def rename_board(self, board: str, new_name: str) -> Board:
        """
        Rename a board directory and update .kanban/.order in place.  Raises
        BoardNotFound if the source board does not exist, and BoardAlreadyExists
        if new_name is already taken.  All tasks within the board retain their
        UUIDs; only the directory name (and therefore the board's slug) changes.
        Updates the active context if the renamed board was the active one.
        """
        ...

    def delete_board(self, board: str) -> None:
        """
        Recursively delete a board directory and remove it from .kanban/.order.
        Raises BoardNotFound if the board does not exist.  Also removes all
        index entries for tasks that belonged to the board and clears the active
        context if it pointed at the deleted board.
        """
        ...


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
        ...

    def create_column(self, board: str, column: str) -> Column:
        """
        Create a new column subdirectory inside the given board.  Raises
        BoardNotFound if the board does not exist and ColumnAlreadyExists if
        the column name is already taken within that board.  Appends the new
        column to the board's .order file and commits.
        """
        ...

    def rename_column(self, board: str, column: str, new_name: str) -> Column:
        """
        Rename a column subdirectory and update the board's .order file.
        Raises BoardNotFound, ColumnNotFound, or ColumnAlreadyExists as
        appropriate.  Tasks inside the column are untouched; their paths
        update implicitly via the directory rename.  Updates the active
        context if the renamed column was the active one.
        """
        ...

    def reorder_column(self, board: str, column: str, position: int) -> list[Column]:
        """
        Move a column to the given 1-based position in the board's .order
        file.  Raises BoardNotFound or ColumnNotFound if either does not
        exist.  Position is clamped to the valid range rather than raising on
        out-of-bounds values.  Returns the full updated column list so the
        CLI can confirm the new order.
        """
        ...

    def delete_column(self, board: str, column: str) -> None:
        """
        Delete a column subdirectory and all tasks it contains.  Raises
        BoardNotFound or ColumnNotFound if either does not exist.  Removes
        all index entries for tasks in the column, updates the board's .order
        file, and clears the active context column if it pointed here.
        """
        ...


    # ── Tasks ─────────────────────────────────────────────────────────────────

    def list_tasks(
        self,
        board:   str | None = None,
        column:  str | None = None,
        filters: TaskFilters = TaskFilters(),
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
        ...

    def create_task(
        self,
        board:  str,
        column: str,
        params: TaskCreateParams,
    ) -> Task:
        """
        Write a new .md file into board/column/ with a generated UUID and the
        provided metadata as frontmatter.  Raises BoardNotFound or ColumnNotFound
        if the target location does not exist, and TaskAlreadyExists if a file
        with the same title slug is already present in that column.  Updates the
        index and commits.
        """
        ...

    def show_task(
        self,
        title_or_id: str,
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task:
        """
        Resolve and return a single task by title slug or UUID.  Delegates
        location resolution to _resolve_task_location, which applies the
        explicit → context → index-search chain and raises TaskNotFound or
        AmbiguousTaskReference if resolution fails.
        """
        ...

    def edit_task(
        self,
        title_or_id: str,
        updates:     TaskUpdateParams,
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task:
        """
        Apply TaskUpdateParams to an existing task's frontmatter and body,
        updating updated_at automatically.  If updates.title differs from the
        current title, the file is renamed to match the new slug.  Raises
        TaskNotFound or AmbiguousTaskReference via _resolve_task_location.
        Updates the index entry and commits.
        """
        ...

    def move_task(
        self,
        title_or_id: str,
        dest:        str,
        board:       str | None = None,
        column:      str | None = None,
    ) -> Task:
        """
        Move a task's .md file to a new board/column location.  dest may be
        "<board>/<column>" or bare "<column>", in which case the source board
        is assumed.  Validates that the destination column exists before moving.
        Raises TaskNotFound, AmbiguousTaskReference, BoardNotFound, or
        ColumnNotFound as appropriate.  Updates the index and commits.
        """
        ...

    def delete_task(
        self,
        title_or_id: str,
        board:       str | None = None,
        column:      str | None = None,
    ) -> None:
        """
        Delete a task's .md file from disk.  Raises TaskNotFound or
        AmbiguousTaskReference via _resolve_task_location.  Removes the task's
        index entry and commits.
        """
        ...


    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query:   str,
        filters: TaskFilters = TaskFilters(),
        board:   str | None = None,
        sort:    str | None = None,
        reverse: bool = False,
    ) -> list[Task]:
        """
        Full-text search across task titles and bodies, narrowed by any
        TaskFilters provided.  Scoped to a single board if board is given,
        otherwise searches the whole repository.  Delegates to SearchService,
        which uses the index when available and falls back to a filesystem scan
        when the index is stale or absent.
        """
        ...


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
        task first via _resolve_task_location so that history follows the file
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
        ...

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

    def _resolve_task_location(
        self,
        title_or_id: str,
        board:       str | None,
        column:      str | None,
    ) -> tuple[str, str, Task]:
        """
        Explicit path → active context → index search.
        Raises TaskNotFound or AmbiguousTaskReference.
        """
        ...

    def _resolve_board(self, board: str | None) -> str:
        """Return explicit board or fall back to active context board."""
        ...

    def _commit(self, type: str, scope: str, description: str) -> None:
        """Compose a structured commit message and delegate to GitService."""
        ...
```

---


**User**: [2026-06-14 04:02:12]

What options are there for getting from the parsed arguments to concrete calls on the kanban service?

---


**Claude**: [2026-06-14 04:02:42]

 There are three main approaches, each with a different philosophy about where the mapping from "parsed args" to "service call" lives.

---

## Option 1: Direct dispatch in each subcommand handler

Each subcommand gets its own function that receives the parsed namespace and calls the service directly.

```python
def cmd_task_create(args: argparse.Namespace, svc: KanbanService) -> None:
    task = svc.create_task(
        board=args.board,
        column=args.column,
        params=TaskCreateParams(
            title=args.title,
            assignee=args.assignee,
            priority=args.priority,
            tags=args.tag or [],
            due_date=args.due_date,
            created_by=args.created_by,
        ),
    )
    render_task(task, format=args.format)

def cmd_task_move(args: argparse.Namespace, svc: KanbanService) -> None:
    task = svc.move_task(
        title_or_id=args.task,
        dest=args.dest,
        board=args.board,
        column=args.column,
    )
    render_task(task, format=args.format)
```

The parser registers these at definition time:

```python
p = subparsers.add_parser("create")
p.set_defaults(func=cmd_task_create)
```

Dispatch is then a single line in `main`:

```python
args = parser.parse_args()
args.func(args, svc)
```

**Strengths**: obvious, linear, easy to trace. Each handler is independently testable — pass a namespace, get output. No indirection.

**Weaknesses**: the `args` namespace is stringly-typed and its shape is implicit. A typo in `args.assignee` fails at runtime. As the command count grows, the handler file grows with it, and there's no structural enforcement that every command has a handler.

---

## Option 2: Command objects (the command pattern)

Each subcommand is a class that owns both its argument registration and its execution. A base class provides the interface.

```python
class Command(ABC):
    name: str
    help: str

    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None: ...

    @abstractmethod
    def execute(self, args: argparse.Namespace, svc: KanbanService) -> None: ...


class TaskCreateCommand(Command):
    name = "create"
    help = "Create a new task"

    def add_arguments(self, parser):
        parser.add_argument("title")
        parser.add_argument("--assignee")
        parser.add_argument("--priority", choices=["low", "medium", "high"])
        parser.add_argument("--tag", action="append")
        parser.add_argument("--due-date", type=parse_date)
        parser.add_argument("--created-by")

    def execute(self, args, svc):
        task = svc.create_task(
            board=args.board,
            column=args.column,
            params=TaskCreateParams(
                title=args.title,
                assignee=args.assignee,
                priority=args.priority,
                tags=args.tag or [],
                due_date=args.due_date,
                created_by=args.created_by,
            ),
        )
        render_task(task, format=args.format)
```

Registration becomes a loop:

```python
TASK_COMMANDS = [TaskCreateCommand(), TaskMoveCommand(), TaskDeleteCommand(), ...]

task_sub = task_parser.add_subparsers()
for cmd in TASK_COMMANDS:
    p = task_sub.add_parser(cmd.name, help=cmd.help)
    cmd.add_arguments(p)
    p.set_defaults(func=cmd.execute)
```

**Strengths**: argument registration and execution live together — you can't accidentally add a flag without handling it, or handle a flag that isn't registered. Each command is a natural unit of testing. Easy to discover all commands programmatically (useful for generating docs or shell completions).

**Weaknesses**: more ceremony for simple commands. The `add_arguments` / `execute` split still passes the stringly-typed namespace across the boundary, so you haven't fully escaped the runtime-failure risk.

---

## Option 3: Typed argument adapters (namespace → params dataclass)

This is an evolution of either option above. The key insight is that the `argparse.Namespace` is the untrusted boundary — you validate and convert it into a typed params object immediately, and everything downstream works with the typed object.

```python
@dataclass
class TaskCreateArgs:
    board:      str
    column:     str
    title:      str
    assignee:   str | None
    priority:   str | None
    tags:       list[str]
    due_date:   datetime | None
    created_by: str | None

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "TaskCreateArgs":
        return cls(
            board=args.board,
            column=args.column,
            title=args.title,
            assignee=args.assignee,
            priority=args.priority,
            tags=args.tag or [],
            due_date=args.due_date,
            created_by=args.created_by,
        )

    def to_service_params(self) -> tuple[str, str, TaskCreateParams]:
        return self.board, self.column, TaskCreateParams(
            title=self.title,
            assignee=self.assignee,
            priority=self.priority,
            tags=self.tags,
            due_date=self.due_date,
            created_by=self.created_by,
        )
```

The handler becomes thin and fully typed:

```python
def cmd_task_create(args: argparse.Namespace, svc: KanbanService) -> None:
    typed = TaskCreateArgs.from_namespace(args)
    board, column, params = typed.to_service_params()
    task = svc.create_task(board, column, params)
    render_task(task, format=args.format)
```

**Strengths**: the `from_namespace` classmethod is the single place where stringly-typed namespace keys are referenced, making typos easy to catch and test. `to_service_params` is a pure function — trivially testable without argparse or the service. The TUI can construct `TaskCreateArgs` directly from its own form fields and call the same `to_service_params`, sharing the mapping logic without touching argparse.

**Weaknesses**: doubles the number of dataclasses — you now have `TaskCreateArgs` alongside `TaskCreateParams`. For commands with few arguments this feels like overhead.

---

## Recommendation

**Start with Option 1** (direct dispatch) and **extract Option 3's adapter pattern selectively** for commands that have enough arguments to make the namespace-to-params mapping worth naming.

The `set_defaults(func=...)` dispatch mechanism is the right foundation regardless — it's the standard argparse idiom, it's flat, and it adds zero indirection. The question is only how much structure you put inside each handler function.

The commands that most benefit from a typed adapter are the ones the TUI will also drive — `task create`, `task edit`, `task list` — because the adapter becomes the shared contract between the CLI arg parser and the TUI form. Commands like `board delete` or `kanban use --clear` are simple enough that a direct three-line handler is cleaner than a dedicated dataclass.

---

