# Repository ABC

Date: 20260614_074503

ID: a37f7be1-9bae-4ccc-956a-9771ed904d23


**User**: [2026-06-14 06:49:21]

Let's look at the repository abstract base class

---


**Claude**: [2026-06-14 06:51:13]

This is a well-thought-out architecture. Let me design the `Repository` ABC carefully — it needs to be the stable interface contract that both the filesystem implementation and the in-memory test implementation will satisfy, while being expressive enough to cover all the CLI operations you've described.

Here's the `Repository` ABC, designed as the stable contract for this system.

The key design decisions I'm making:

**Scope**: The ABC covers the four main entity operations (CRUD for boards, columns, tasks) plus path/lookup helpers. Git and indexing are handled in their own services/repositories rather than mixed in here — that keeps this interface focused.

**Column ordering**: Columns within a board have a defined order (stored in `.order`). The ABC treats columns as ordered lists, not sets.

**Resolution support**: The CLI's path-resolution rules (explicit → active context → index search) mean the ABC needs `find_task_by_title` and `list_tasks` with filter predicates, not just `get_by_id`.

**Separation**: `move_task` is a repository method (it's storage manipulation — rename file, change directory), not a domain operation, since the domain service just validates and delegates.

Now let me visualise the method surface grouped by responsibility so it's easy to reason about coverage:

Here are the decisions worth calling out explicitly.

**Everything lives in one file.** `Task`, `Board`, `Column`, `TaskFilter`, all the exceptions, and `KanbanRepository` itself are in `repository.py`. Every other layer imports from here — no circular dependencies, no split-domain model across files.

**`task.id` is caller-assigned, not repository-assigned.** The domain `TaskService` generates the UUID before calling `create_task`. This keeps the repository passive and makes the `InMemoryRepository` trivially simple — it just stores what it's given.

**`update_task` handles renames.** When `task.title` has changed, the repository renames the underlying file. This is intentional: the repository owns the mapping between a title and a filename, so it's the right layer to manage that side-effect. The domain service just validates the new title is acceptable.

**`move_task` takes `(task_id, dest_board, dest_column)` — not a full `Task`.** It locates the task by UUID, moves it, and refreshes `updated_at`. Callers don't need to pre-fetch the task to move it.

**`find_tasks_by_title` returns a list, not a single task.** The CLI's path-resolution step needs to detect ambiguity (same title in two boards) and surface that as an error. Returning a list puts that decision in the domain layer where it belongs.

**`reorder_column` returns the full updated column list.** The CLI needs to display the new order; returning it from the repository avoids a second `list_columns` round-trip.

**Index methods are on the ABC.** `IndexService` calls them, and `InMemoryRepository` implements them as no-ops. This keeps `IndexService` from needing to know which concrete repository it's talking to.

**`TaskFilter` is separate from method arguments.** `list_tasks(board, column, filter)` takes explicit `board` and `column` for scope because they affect *which files to scan*, not just *which results to keep*. The `filter` carries the secondary predicates (assignee, priority, tag, dates).

The next natural pieces are `FilesystemRepository` (the concrete implementation), `InMemoryRepository` (for tests), or the `KanbanService` facade — whichever you'd like to tackle next.

---


**User**: [2026-06-14 06:54:22]

what do you think about using the word storage instead of repository

---


**Claude**: [2026-06-14 06:54:31]

 Reasonable question, but I'd keep "repository" — here's why.

"Storage" implies the raw medium: a disk, a database, a bucket. When you read `FilesystemStorage` you think "this thing talks to files." When you read `FilesystemRepository`, you think "this thing gives me domain objects back, and it happens to use the filesystem to do it." That distinction matters because the whole point of the layer is the translation — turning markdown frontmatter into `Task` dataclasses and back. The name should reflect *what it does for callers*, not *how it does it internally*.

The naming also has precedent weight. Repository is the established term for this pattern (from Evans' DDD), and developers who've seen it before will immediately know what to expect: a collection-like interface that abstracts persistence. "Storage" doesn't carry that contract implicitly.

There's also a practical collision risk in your own architecture. You already use "Storage" in your layer diagram as a label for the bottom tier — the raw filesystem + SQLite tier that the repository sits *above*. If you name the ABC `KanbanStorage`, the distinction between the ABC and what it wraps becomes harder to communicate in conversation, in docs, and in code.

That said, if the team finds "repository" unfamiliar or ceremonious, `KanbanStore` / `FilesystemStore` is a reasonable middle ground — "store" carries some of the same collection semantics without the DDD baggage.

---


**User**: [2026-06-14 07:10:00]

Where do the dataclasses belong in the project?

---


**Claude**: [2026-06-14 07:10:10]

 They shouldn't live in `repository.py`. That made sense as a single-file sketch, but in a real project it creates an awkward dependency: every layer that wants to work with a `Task` has to import from the repository module, which implies a storage concern it has nothing to do with.

The dataclasses are your domain model — they belong in a dedicated `models.py` (or a `models/` package if it grows). That module has no dependencies of its own: no storage, no git, no CLI. Everything else imports from it.

```
kanban/
  models.py          # Task, Board, Column, TaskFilter — pure dataclasses
  repository.py      # KanbanRepository ABC + exceptions — imports from models
  services/
    task_service.py  # imports from models and repository
    board_service.py
    ...
  storage/
    filesystem.py    # FilesystemRepository — imports from models and repository
    memory.py        # InMemoryRepository
  cli.py             # imports from models and services
```

The exceptions are a closer call. `TaskNotFound` and friends are repository-layer exceptions right now — domain services catch them and re-raise as domain exceptions — so keeping them in `repository.py` is defensible. But if you find yourself wanting to raise `TaskNotFound` from a service directly (rather than wrapping it in a separate `DomainTaskNotFound`), they'd migrate to `models.py` too. Start with them in `repository.py` and move them when the pain is real.

---

