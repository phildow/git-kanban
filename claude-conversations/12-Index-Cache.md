# Index Cache

Date: 20260710_005840

ID: 77f2222a-9894-4e6a-847e-d3309facdd39


**User**: [2026-06-25 20:19:03]

Let’s take a closer look at the index / cache and search service, operating under the constraint that the filesystem remains the source of truth. What are some of the behaviors it can provide?

---


**Claude**: [2026-06-25 20:19:52]

Behaviors the index/cache and SearchService could provide, while staying a derived cache rather than a second source of truth:

**Staleness detection & reconciliation**
- Per-file freshness check (mtime+size, or content hash) so a query can decide "trust the cache" vs "reparse this file" without rescanning the whole store
- Full-tree reconciliation pass (for `kanban status`, or on `repl` startup) that diffs the index's file list against what's actually on disk — catches files added/deleted/moved outside the app (manual edits, `git pull`, branch switches)
- Lazy reconciliation: only re-stat/reparse files relevant to the current query's scope (board, or board/column) rather than the whole store

**Write-through updates**
- On every KanbanService write (create/update/move/delete/rename), update just the affected row(s) instead of a rescan — this is the "index updated after every interaction" behavior in the spec
- On reads, a cheap freshness check before serving cached rows (or just serve cache and let the next reconciliation catch drift — a policy choice)

**Query execution (SearchService's main job)**
- Structured filtering on indexed frontmatter fields: assignee, priority, tag, due-date range, created-by — without parsing every markdown file
- Sorting on those same fields
- Scoping by board/column
- Full-text search over title/body via SQLite FTS5, with relevance ranking (bm25) as an alternative sort to the explicit `--sort` flags
- Combining FTS + structured filters in one query

**Supporting the CLI's path resolution**
- Step 3 of path resolution ("index search scoped to active board") needs partial/fuzzy title matching — the index is what makes that fast, and it must report ambiguous matches (multiple hits) rather than silently picking one, so the facade can raise the "error on ambiguity" case
- UUID → current path lookup: since filenames change but UUIDs don't, the index is the lookup table other commands (`log`, `show`, internal references) use to find a task's current location

**Integrity / health reporting**
- Surfacing problems found during reconciliation: duplicate UUIDs, files with missing/malformed frontmatter, orphaned index rows (path no longer exists) — useful for `kanban status`
- Explicit `kanban index rebuild` (or similar) for a forced full rescan after something like a rebase or manual restructuring

**Graceful degradation**
- If `index.db` is missing, empty, or a board isn't indexed yet, queries fall back to the scan-on-demand path through the repository directly — matches the roadmap of starting with scan-on-demand and adding SQLite later
- Index results should be treated as hints, not authority, for any mutating operation — the repository re-verifies against the filesystem before acting, and corrects the index if it finds a mismatch (no TOCTOU trust)

Open decisions worth deciding before scaffolding `IndexService`:
1. Freshness check: mtime+size only, or content hash (more robust, costs more I/O)?
2. Reconciliation trigger: eager (every CLI invocation does a quick diff) vs lazy (only on `status`/explicit rebuild)?
3. Does `kanban status` report index/filesystem drift, or just git status — or both?

---


**User**: [2026-06-25 20:28:08]

I’d also like the index to provide a list of tags and users that have so far been set in the tags and assigned-to fields of a task, for tab and autocompletion in addition to fast search

---


**Claude**: [2026-06-25 20:28:22]

That's a distinct-value enumeration behavior — separate from search, but same underlying cache. A few design points to settle:

**Where it lives**
- Could be a derived query (`SELECT DISTINCT assignee FROM tasks`, and a join/unnest for tags if they're a separate table) rather than a maintained list — keeps it consistent with "index is always a cache," no separate write path to keep in sync
- If tags are stored as a JSON array column, `DISTINCT` won't help directly — likely want a normalized `tags` table (`task_id`, `tag`) so both FTS-style filtering and `DISTINCT tag` are simple queries

**Update timing**
- Falls under the existing "index updated after every interaction" rule — no new write-through logic needed, just additional columns/tables populated on the same create/update events

**Scope**
- Global across all boards, or scoped to active board (consistent with how index search scopes to active board when set)? Affects whether the completer needs a `--board` style filter or always offers everything

**Staleness on removal**
- If the last task using a tag is deleted or retagged, does the tag disappear from suggestions immediately, or persist until reconciliation/rebuild? A live `DISTINCT` query handles this for free; a maintained/cached value-list table would need explicit pruning logic
- Same question for assignees — if alice leaves and her last task is reassigned, does `alice` vanish from completion?

**Surface to completer**
- Used for completing `--assignee <TAB>` and `--tag <TAB>` values in both CLI flags and REPL — distinct from the path completion described earlier (boards/columns/tasks), so the REPL completer needs to know "this argument position wants tag/assignee values" vs "this position wants a path"

**New tags/assignees not yet in the index**
- A brand-new tag or assignee name typed by the user is valid (free text, not an enum) — completion offers known values but doesn't reject novel ones

Questions before this gets scaffolded:
1. Normalized `tags` table, or is there already a planned schema for tags I should align with?
2. Global suggestions or board-scoped?
3. Live `DISTINCT` query each time, or maintain a cached value list updated on writes (more state, but possibly cheaper if called very frequently during typing)?

---


**User**: [2026-06-25 20:35:12]

1) tags are comma delimited in the front matter so what is the best option for storage in the index? 2) search is scoped to the active board by default but with the option to search across all boards. 3) assuming 10,000 task how long will a distinct query take to execute?

---


**Claude**: [2026-06-25 20:35:30]

**1) Tag storage**

Store as a normalized child table, not a delimited string column:

```sql
CREATE TABLE task_tags (
    task_id TEXT NOT NULL REFERENCES tasks(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (task_id, tag)
);
CREATE INDEX idx_task_tags_tag ON task_tags(tag);
```

Reasoning: the frontmatter parses to a list (`tags: [bug, auth]` via `python-frontmatter`/YAML), so on write you already have discrete values — no need to serialize back into a delimited string just to split it again on every read. A delimited column (`tags TEXT` = `"bug,auth"`) would force `LIKE '%bug%'` matching for filters (slow, no index use, false positives on substrings) and manual split-in-Python for `DISTINCT`. The child table gives you:
- `WHERE tag = ?` filtering with an index
- `SELECT DISTINCT tag FROM task_tags` for completion, cheap and indexed
- Natural join back to `tasks` for combined filters (assignee + tag + due-date)

This is internal index schema only — the markdown frontmatter keeps whatever format you settle on for the file format (list or comma string); the index's job is to normalize whatever it parses on write-through.

**2) Scoping** — noted. Queries default to `WHERE board = :active_board`, with an explicit flag (`--all-boards` or similar) dropping that predicate. Same pattern presumably applies to tag/assignee completion lists, unless you want those always-global regardless of active board — worth deciding now since it affects the completer's query.

**3) DISTINCT query timing at 10k tasks**

With the indexed `task_tags(tag)` schema above: a `SELECT DISTINCT tag FROM task_tags` (or `assignee` similarly indexed on `tasks`) is effectively an index scan over however many tag-rows exist — call it 20k–40k rows at ~2–4 tags/task. SQLite with a covering index on that column does this in low single-digit milliseconds on any modern machine; it's not a query that will be perceptible to a user typing in the REPL.

Without an index (table scan + dedup in memory) it's still sub-10ms at this row count — SQLite is fast enough that 10k–40k rows of short text is trivial either way. The index matters more for write-heavy churn and for combined filter queries than for this specific lookup.

If you want it even cheaper for autocomplete-while-typing (called on every keystroke), the option from earlier — a maintained, in-memory cached value-list refreshed on write-through rather than queried fresh each keystroke — would turn it into a Python set lookup instead of a SQL roundtrip. At 10k tasks I wouldn't bother; worth revisiting only if profiling says otherwise.

---


**User**: [2026-06-25 20:37:07]

Describe FTS5 in more detail

---


**Claude**: [2026-06-25 20:37:26]

**What FTS5 is**

FTS5 is a SQLite virtual table module purpose-built for full-text search. Instead of storing rows in a B-tree like a normal table, it builds an inverted index — for each token (word), a list of which rows contain it — so a search for a word is a fast index lookup rather than scanning every row's text.

**Schema shape**

```sql
CREATE VIRTUAL TABLE tasks_fts USING fts5(
    title,
    body,
    content='tasks',      -- external content table
    content_rowid='rowid'
);
```

Two storage modes matter here:
- **External content table** (`content='tasks'`): FTS5 stores only the index, not the text — the actual title/body live in your normal `tasks` table, and FTS5 just points back via rowid. Saves space, avoids duplicating data you already have. Requires triggers (or manual write-through) to keep the FTS index in sync on insert/update/delete.
- **Standalone/contentless**: FTS5 owns and stores the text itself. Simpler to write to but duplicates content and you can't easily get non-indexed columns back from a join.

Given your "index updated after every interaction" rule, external content fits naturally — you're already write-through updating `tasks` on every create/update/delete; either add `INSERT/UPDATE/DELETE` triggers on `tasks` to mirror into `tasks_fts`, or do it explicitly from `IndexService` alongside the other write-through calls (more aligned with "index updated by the service," but triggers are less error-prone).

**Tokenization**

Default tokenizer is `unicode61` (splits on whitespace/punctuation, case-insensitive, basic unicode-aware). Options relevant to task titles/bodies:
- `porter` stemmer wrapper (`tokenize = 'porter unicode61'`) — matches "logging" when searching "log," generally desirable for prose search
- Can add `prefix='2 3'` to support prefix matching efficiently (useful if you want incremental search-as-you-type, separate from the tag/assignee completion discussed earlier)

**Querying**

```sql
SELECT tasks.* FROM tasks_fts
JOIN tasks ON tasks.rowid = tasks_fts.rowid
WHERE tasks_fts MATCH 'login bug'
ORDER BY bm25(tasks_fts);
```

- `MATCH` supports boolean operators (`AND`, `OR`, `NOT`), phrase queries (`"fix login"`), prefix queries (`log*`), column filters (`title: login`)
- `bm25(tasks_fts)` gives a relevance score (lower = more relevant by default sign convention) — this is your natural default sort for free-text `search`, as an alternative to the explicit `--sort` flags which apply to structured fields

**Combining with structured filters**

This is the case that matters for your `search` command — FTS for the query text, joined with the normal filters (assignee, tag, priority, board scope):

```sql
SELECT tasks.* FROM tasks_fts
JOIN tasks ON tasks.rowid = tasks_fts.rowid
LEFT JOIN task_tags ON task_tags.task_id = tasks.id
WHERE tasks_fts MATCH ?
  AND tasks.board = ?
  AND tasks.assignee = ?
ORDER BY bm25(tasks_fts);
```

FTS5 handles the `MATCH` efficiently; the joined `WHERE` clauses on indexed columns (board, assignee) narrow it further. SQLite's query planner generally handles this combination well at the row counts you're talking about (10k tasks).

**Practical implications for your design**

- Write-through cost: every task create/update needs the FTS mirror updated too — one more statement in the same transaction as the `tasks` table write, not a separate pass
- Body content: if markdown bodies are large, FTS5 indexes can grow accordingly, but at 10k tasks of typical task-description length this is a non-issue for size or speed
- This only covers free-text `search` — the tag/assignee `DISTINCT` completion lookups discussed earlier are unrelated to FTS5 and stay on the plain indexed columns/tables

---


**User**: [2026-06-26 00:58:52]

Before moving onto the sql specification I’d like to develop the api to the index service, and I’d like to test it with an in memory index. As we’ve done for the repository layer the index service will be an abstract base class with concrete SQLite and in memory implementations. What might the api to the service and the memory index look like?

---


**Claude**: [2026-06-26 00:59:32]

A few design choices to settle, then a sketch.

**Choices**

- The index works on domain `Task` objects, not raw frontmatter — `IndexService` never parses markdown itself. `KanbanService` calls it with the `Task` the repository already returned.
- Tag/assignee scoping defaults to active board per your last answer, with an "all boards" override — same as search.
- Distinct from `Repository`: there's no `read` path that "creates" data here — the index is purely a derived cache, so its write methods are `upsert`/`remove`, and its read methods are query-shaped, not CRUD-shaped.
- Reconciliation needs a way to ask "what does the index currently think exists" so the facade (or a dedicated reconciliation routine) can diff that against the filesystem.

**Query/filter shape**

```python
@dataclass(frozen=True)
class SearchQuery:
    """Parameters for a search or filter operation against the index."""
    text: str | None = None              # free-text term; None = no FTS/text filter
    board: str | None = None             # None = all boards (explicit opt-in)
    column: str | None = None
    assignee: str | None = None
    priority: Priority | None = None
    tags: tuple[str, ...] = ()           # AND semantics across tags
    created_by: str | None = None
    due_before: date | None = None
    due_after: date | None = None
    sort: SortField = SortField.TITLE
    reverse: bool = False


@dataclass(frozen=True)
class SearchResult:
    """A single matched task plus optional relevance ranking."""
    task: Task
    score: float | None = None  # bm25 rank in SQLite impl; None in in-memory impl
```

**The ABC**

```python
class IndexService(ABC):
    """Cache of task metadata for fast search and completion.

    The index is always derived from the filesystem via Task objects
    supplied by the caller (typically KanbanService, after a Repository
    read or write). It is never queried by KanbanService for anything
    KanbanService treats as authoritative state -- only for search,
    filtering, and completion convenience.
    """

    @abstractmethod
    def upsert_task(self, task: Task) -> None:
        """Insert or update the indexed record for a task."""

    @abstractmethod
    def remove_task(self, task_id: UUID) -> None:
        """Remove a task's indexed record. No-op if not present."""

    @abstractmethod
    def get_path(self, task_id: UUID) -> TaskPath | None:
        """Look up a task's current board/column/title by UUID."""

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Return tasks matching the given filters, sorted accordingly."""

    @abstractmethod
    def find_by_title(
        self, partial_title: str, board: str | None = None, column: str | None = None
    ) -> list[Task]:
        """Find tasks whose title matches partial_title, scoped as given.

        Used for CLI/REPL path resolution step 3 (index search). Returns
        all matches; the caller decides whether multiple results is an
        ambiguity error.
        """

    @abstractmethod
    def list_tags(self, board: str | None = None) -> list[str]:
        """Return distinct tag values seen so far, scoped to board if given."""

    @abstractmethod
    def list_assignees(self, board: str | None = None) -> list[str]:
        """Return distinct assignee values seen so far, scoped to board if given."""

    @abstractmethod
    def known_paths(self, board: str | None = None) -> set[TaskPath]:
        """Return every task path currently recorded in the index.

        Used by reconciliation to diff against what's actually on disk.
        """

    @abstractmethod
    def clear(self, board: str | None = None) -> None:
        """Drop all indexed records, or all records for one board."""
```

`TaskPath` would be a small frozen dataclass (`board`, `column`, `title`) — board/column/title only, no object references, consistent with the "no cached relationships" rule.

**InMemoryIndexService**

```python
class InMemoryIndexService(IndexService):
    """Index backed by a plain dict, for unit tests.

    Trades real FTS5 ranking and SQL filtering for direct Python
    filtering. Functionally equivalent for filter/scope correctness;
    SearchResult.score is always None since there is no bm25 equivalent
    here. Tests asserting on ranking order should target the SQLite
    implementation instead.
    """

    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    def upsert_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    def remove_task(self, task_id: UUID) -> None:
        self._tasks.pop(task_id, None)

    def search(self, query: SearchQuery) -> list[SearchResult]:
        results = [t for t in self._tasks.values() if self._matches(t, query)]
        results.sort(key=self._sort_key(query.sort), reverse=query.reverse)
        return [SearchResult(task=t) for t in results]

    def _matches(self, task: Task, query: SearchQuery) -> bool:
        """Apply each non-None filter in query as an AND condition."""
        ...

    # list_tags / list_assignees: set comprehension over self._tasks,
    # optionally filtered by board first.
```

This gives the same shape your repository ABC has: `IndexService` defined against domain types, `InMemoryIndexService` for tests, `SqliteIndexService` (next) for the real FTS5/SQL backing — and `KanbanService`/`SearchService` code against the ABC without knowing which is active.

Things I'd want confirmed before writing real files:
1. Should `find_by_title` do substring/fuzzy matching in-memory, or exact-prefix only — does it need to mirror SQLite `LIKE`/FTS prefix behavior closely enough for tests to be meaningful across both implementations?
2. Is `TaskPath` the right granularity for `known_paths`/reconciliation, or do you want full `Task` snapshots returned so reconciliation can also detect *changed* (not just added/removed) files by comparing `updated_at`?
3. Where does `SearchService` sit relative to this — does it call `IndexService` directly, or does `IndexService` stay this low-level and `SearchService` adds query-building/validation on top?

---


**User**: [2026-06-26 01:08:58]

1) Find by tittle is exact prefix matching 2) just the path, type it as an absolute Path not a custom type yet 3), search service sits between the kanban service and the index service

---


**Claude**: [2026-06-26 01:09:16]

Updating the three points:

**1) `find_by_title` → exact prefix matching**

```python
@abstractmethod
def find_by_title(
    self, title_prefix: str, board: str | None = None, column: str | None = None
) -> list[Task]:
    """Find tasks whose title starts with title_prefix (case-sensitive,
    exact prefix — not fuzzy/substring), scoped as given.

    Used for CLI/REPL path resolution step 3 and for path-segment tab
    completion. Returns all matches; caller decides if multiple results
    is an ambiguity error.
    """
```

In-memory: `[t for t in self._tasks.values() if t.title.startswith(title_prefix) and self._in_scope(t, board, column)]`. This makes the in-memory and SQLite (`LIKE 'prefix%'`, which can use an index since it's left-anchored) implementations behave identically — good, since this is the method most directly exercised by path-resolution tests.

**2) `Path` instead of `TaskPath`**

```python
@abstractmethod
def get_path(self, task_id: UUID) -> Path | None:
    """Return the absolute filesystem path of the task's markdown file,
    or None if not indexed.
    """

@abstractmethod
def known_paths(self, board: str | None = None) -> set[Path]:
    """Return the absolute paths of every task currently recorded in
    the index, for reconciliation against the filesystem.
    """
```

Drops `TaskPath` entirely for now — `Task` itself presumably carries enough (board/column/title or a `path` field) to derive scope from a `Path`, so no need for a parallel dataclass yet. In-memory storage would then need to key/store by id and derive path from the task's own fields, or store `(Task, Path)` pairs if `Task` doesn't carry its path — depends on whether the `Task` dataclass already has a `path: Path` field.

Worth confirming: does `Task` already include its filesystem path as a field, or does the index need to be told the path separately on `upsert_task`? If `Task` doesn't carry it, `upsert_task` needs a second parameter:

```python
@abstractmethod
def upsert_task(self, task: Task, path: Path) -> None:
    ...
```

**3) `SearchService` layering**

So the call chain is `KanbanService → SearchService → IndexService`, and `KanbanService` never touches `IndexService` directly — for reads *and* writes? That's the open question: the spec says "index is updated by the KanbanService after every interaction with the repository, read or write." If `SearchService` is now strictly in between, does that mean:

- (a) `KanbanService` still calls `IndexService.upsert_task`/`remove_task` directly for write-through, and `SearchService` only wraps the *read* side (`search`, `find_by_title`, `list_tags`, `list_assignees`), or
- (b) `KanbanService` routes everything through `SearchService`, including write-through, and `SearchService` exposes its own `index_task`/`remove_task` methods that just delegate to `IndexService`?

(b) keeps the "each layer interacts only with the layer below it" rule cleaner — `KanbanService` would otherwise have two siblings (`SearchService` and `IndexService`) it both touch, which breaks the strict layering. (a) keeps `SearchService` purely about querying/filtering, which matches its name better.

Which did you mean?

---


**User**: [2026-06-26 01:14:50]

2) the task knows its path, I need to update the specification. 3) it’s ok for a layer to have two siblings and for one of those siblings to sit below the other (the other also falls into it eg the search service also calls into the index service)

---


**Claude**: [2026-06-26 01:15:07]

Noted on both.

**Revised `upsert_task`** (since `Task` carries its own path now):

```python
@abstractmethod
def upsert_task(self, task: Task) -> None:
    """Insert or update the indexed record for a task, keyed by task.id.
    Path is read from task.path.
    """
```

**Layering, confirmed**

So the call graph is:

```
KanbanService ──→ SearchService ──→ IndexService
       └──────────────────────────────↗
```

`KanbanService` calls `IndexService` directly for write-through (`upsert_task`/`remove_task`/`clear`) after every repository read or write, and calls `SearchService` for anything search/filter/completion-shaped. `SearchService` sits below `KanbanService` and itself calls `IndexService` for the actual querying — it doesn't talk to the repository or storage at all. This matches "domain services return rich dataclasses, never touch storage directly" — `SearchService` is a domain service whose "repository" is `IndexService` rather than `Repository`.

That reshapes the split between `IndexService` and `SearchService`:

- **`IndexService`**: low-level cache operations — write-through (`upsert_task`, `remove_task`, `clear`), raw lookups (`get_path`, `find_by_title`), raw distinct-value queries (`list_tags`, `list_assignees`), and reconciliation support (`known_paths`). No knowledge of CLI concerns like ambiguity errors or default sort fields.
- **`SearchService`**: builds on `IndexService` to do the things the CLI/REPL actually ask for — applying `SearchQuery` defaults (e.g. defaulting `board` to active board, raising `TaskAmbiguous` when `find_by_title` returns >1 result for path resolution), and any cross-cutting query logic that doesn't belong in the raw cache.

```python
class SearchService:
    """Domain service for search, filtering, and path-resolution lookups.
    Delegates all actual querying to an injected IndexService; never
    touches Repository or storage directly.
    """

    def __init__(self, index: IndexService) -> None:
        self._index = index

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Run a search/filter query, returning ranked/sorted results."""
        return self._index.search(query)

    def resolve_title(
        self, title_prefix: str, board: str | None, column: str | None
    ) -> Task:
        """Resolve a partial title to exactly one task within scope.

        Raises TaskNotFound if no match, TaskAmbiguous if multiple.
        """
        matches = self._index.find_by_title(title_prefix, board, column)
        if not matches:
            raise TaskNotFound(title_prefix)
        if len(matches) > 1:
            raise TaskAmbiguous(title_prefix, matches)
        return matches[0]

    def list_tags(self, board: str | None = None) -> list[str]:
        return self._index.list_tags(board)

    def list_assignees(self, board: str | None = None) -> list[str]:
        return self._index.list_assignees(board)
```

`TaskAmbiguous` is a new domain exception worth adding alongside `TaskNotFound`/`BoardAlreadyExists` — it's exactly the "error on ambiguity" case from CLI path resolution step 4, and `resolve_title` is presumably what the CLI/REPL path resolver calls for step 3.

One thing to confirm: should `IndexService.search` itself apply the active-board default, or does `SearchService` need to inject `board=active_board` into the `SearchQuery` before calling down (i.e., does `IndexService` stay scope-agnostic and just honor whatever `SearchQuery.board` says, with `SearchService` or `KanbanService` owning "what is the active board")? I'd lean toward the latter — `IndexService` shouldn't know about user context at all — but want your call before finalizing `resolve_title`'s signature (whether it takes `board`/`column` explicitly as above, or reads them itself somehow).

---


**User**: [2026-06-26 01:18:27]

If resolve title discovers more than one task with the title prefix return all of them instead of raising and ambiguous error

---


**Claude**: [2026-06-26 01:18:33]

Updated:

```python
def resolve_title(
    self, title_prefix: str, board: str | None, column: str | None
) -> list[Task]:
    """Resolve a partial title to matching tasks within scope.

    Returns all tasks whose title starts with title_prefix. Empty list
    if no match. Caller decides how to handle zero or multiple results
    (e.g. KanbanService raises TaskNotFound or TaskAmbiguous as part of
    CLI path-resolution step 4).
    """
    return self._index.find_by_title(title_prefix, board, column)
```

This pushes the "error on ambiguity" decision (and `TaskNotFound`/`TaskAmbiguous` exceptions) up to `KanbanService`, which is where path resolution's step 4 lives per the CLI spec anyway — `SearchService` stays a pure query layer with no opinion on what counts as an error.

That removes the need for `TaskAmbiguous`/`TaskNotFound` to be raised from `SearchService` at all — they'd be raised by `KanbanService` after inspecting the list length. Worth confirming: do you still want those two exceptions defined as domain exceptions (just relocating who throws them), or does `KanbanService`, being a facade/orchestrator rather than a domain service, throw a different exception type at that layer?

---


**User**: [2026-06-26 01:21:59]

Great we’re also planning to add a reconciliation service that also sits between the kanban service and the index search to handle changes made directly to the filesystem outside of the kanban app.

But for now scaffold the index service abc, the in memory concrete implementation, and the search service that sits between the kanban service and the index service

---


**Claude**: [2026-06-26 01:22:58]

No existing project files — this is a fresh scaffold under `/home/claude/kanban`. I'll create minimal supporting pieces (`Task`/`Priority` dataclasses, domain exceptions) only as needed to make the index/search code coherent — I'm not building out `Repository`, `KanbanService`, or the other domain services since those haven't been scaffolded with you yet.

Now the `IndexService` ABC:

---


**User**: [2026-06-26 01:23:00]

Assume the rest of the project already exists I just want these services

---


**Claude**: [2026-07-01 00:37:32]

Good — the three core files were already started. Let me check query.py and models.py for issues, then write the tests and pyproject.

Good — the three core files are already there and look solid. Two things to fix in `memory.py` before tests: the `getattr` call (violates the project's dot-notation rule) and the priority sort order (string comparison on "high"/"low"/"medium" gives wrong order). Then I'll write tests and pyproject.

Two failures — both from the "None sorts last regardless of reverse" invariant. The `(is_none, value)` tuple flips when `reverse=True`. Fix: two stable passes.

---


**User**: [2026-07-01 00:38:53]

Assume the project files already exist along with KanbanService, datamodel types including Task, Board, and Column, and the Repository types. Scaffold the IndexService ABC and MemoryIndexService that implements it

---


**Claude**: [2026-07-01 00:42:31]

Now overwrite the tests cleanly:

The sentinel `datetime.min` is naive; the test creates UTC-aware datetimes. Fix the sentinel:

61 tests, all passing. Here's a summary of what was scaffolded:

**`src/kanban/index/query.py`** — `SortField`, `SearchQuery`, `SearchResult`. `SearchQuery` is a frozen dataclass; all fields default to None/empty so callers only populate what they need. `SearchResult.score` is None in the memory impl, populated by bm25 in the future SQLite impl.

**`src/kanban/index/base.py`** — `IndexService` ABC. Methods grouped into three sections: write-through (`upsert_task`, `remove_task`, `clear`), lookups (`get_path`, `find_by_title`, `known_paths`), completion (`list_tags`, `list_assignees`), and search (`search`). No knowledge of user context — scoping is the caller's job.

**`src/kanban/index/memory.py`** — `InMemoryIndexService`. The main implementation detail worth noting is the two-pass stable sort in `search()`: first sort by value with the `reverse` flag, then sort by `is_none` ascending (stable, so within-group order from the first pass is preserved). This is what gives None-valued fields their "always last" behaviour regardless of direction. `_value_key` and `_none_key` are module-level functions rather than static methods to keep `search()` readable.

**Tests** — split across four files by concern: write operations, lookups, completion values, search filters, and search sort. 61 tests total.

---


**User**: [2026-07-01 00:49:03]

regenerate the base.py and query.py files pleas

---


**Claude**: [2026-07-01 00:49:52]

61 tests still green. The main additions over the previous versions:

**`query.py`** — inline comments on `SearchQuery` fields clarify semantics that aren't obvious from types alone (`due_before`/`due_after` are exclusive, `tags` requires all to match, `column` is only meaningful with `board`). `SortField` docstring notes that its values match the CLI `--sort` flag strings directly.

**`base.py`** — module docstring names the two concrete implementations and their roles. Section comments explain *who* calls each group of methods and *why* (`KanbanService` drives write-through; the reconciliation service drives `clear`/`known_paths`). `get_path` and `search` docstrings capture the "None sorts last regardless of direction" contract that the memory and SQLite implementations both need to honour.

---


**User**: [2026-07-01 00:50:12]

save them as files so i can add them to my project

---


**Claude**: [2026-07-01 00:50:22]

Both files ready to download. They go in `src/kanban/index/`.

---


**User**: [2026-07-01 00:50:49]

save the memory implementation as a file as well

---


**Claude**: [2026-07-01 00:50:54]

Also goes in `src/kanban/index/`.

---


**User**: [2026-07-01 01:10:03]

generate the tests file for the in memory index service

---


**Claude**: [2026-07-01 01:10:27]

The tests are already split across four files by concern, plus a helpers module. I'll save them all.

Six files — suggested layout in your project:

```
tests/
  index/
    __init__.py
    helpers.py
    test_memory_write.py
    test_memory_lookup.py
    test_memory_completion.py
    test_memory_search_filters.py
    test_memory_search_sort.py
```

`helpers.py` contains `make_task` and `utc` — note the import path in the test files is `from tests.index.helpers import ...`, so adjust that if your test package is named differently.

---


**User**: [2026-07-01 01:27:36]

show me the Priority model used in these types

---


**Claude**: [2026-07-01 01:27:59]

```python
class Priority(str, Enum):
    """Task priority levels, matching the CLI's --priority values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

`str, Enum` means the values are strings, so `Priority.HIGH == "high"` is true and they serialise cleanly to/from frontmatter without a translation step. The sort order in the index (`LOW=0, MEDIUM=1, HIGH=2`) is defined explicitly in `memory.py` rather than relying on the string values, since alphabetical order ("high" < "low" < "medium") gives the wrong result.

---


**User**: [2026-07-10 00:49:32]

Let's refactor this a bit. Instead of having an index service that is the abstract base class and a query service, let's combine the index service and query service into a single index service, and let's have a separate base class the index base , that the index service interacts with. The base class continues to be responsible for the fundamental index operations, and we continue to have a memory index and a sqlite index that conform to the base class,  the stores, no change there. The service will pass most of its method calls onto the base, eg upsert_task and remove_task, but it will also be responsible for behavior that works across entries in the index, such as rebuilding it, syncing it against the filesystem, and other more complex behavior. In this design the index service requires access to the repository, but the index base and its concrete implementations do not.

---


**Claude**: [2026-07-10 00:50:40]

Let me make sure I understand the new structure before writing any files.

**Before:**
```
KanbanService ──→ SearchService ──→ IndexService (ABC)
      └──────────────────────────────────↗              
                                     InMemoryIndexService
                                     SqliteIndexService
```

**After:**
```
KanbanService ──→ IndexService (service)
                     ↓         ↓
                 IndexBase   Repository
                 (ABC)
                     ↓
                 InMemoryIndex
                 SqliteIndex
```

So:
- `IndexBase` is the renamed ABC — low-level cache operations only, no repository access
- `InMemoryIndex` and `SqliteIndex` are the concrete stores implementing `IndexBase`
- `IndexService` is the new service layer — wraps `IndexBase`, has `Repository`, absorbs `SearchService`, and adds cross-entry behaviour like `rebuild` and `sync`

A few things to confirm before writing:

1. `sync` needs to find a task's UUID given a path (to call `remove_task`) — the current `known_paths()` only returns `set[Path]`. Should `IndexBase` gain a `get_task_by_path(path: Path) -> Task | None` method to support this, or would you rather `known_paths` return a `dict[Path, UUID]`?

2. For `rebuild` and `sync`, what repository methods should `IndexService` assume exist? I'd expect something like `all_tasks(board=None)` and `all_task_paths(board=None)` — do those match what the Repository ABC looks like in your project?

3. Does `IndexService` keep `resolve_title` from the old `SearchService`, or does that stay in `KanbanService` now?

---


**User**: [2026-07-10 00:55:31]

Yes you have the design correct. 1) Let's postpone a decision. Do not change known_paths. 2) The repository implements `get_tasks` that returns all tasks optionally scoped to a board and column. 3) Ignore resolve_title

---


**Claude**: [2026-07-10 00:58:40]

Got it. Four files to produce — `base.py`, `memory.py`, `service.py`, and tests for the service. The existing memory tests just need their import updated from `InMemoryIndexService` to `InMemoryIndex`.

Now update the existing memory tests to use `InMemoryIndex`, and add service tests:

Two issues: `kanban.repository` doesn't exist in this sandbox, and `test_search_service.py` is stale from before the refactor. Fix both:

70 tests, all passing. Now save the files:

Suggested layout in your project:

```
src/kanban/index/
    base.py          ← IndexBase ABC
    memory.py        ← InMemoryIndex
    service.py       ← IndexService

tests/index/
    helpers.py       ← unchanged
    test_memory_write.py
    test_memory_lookup.py
    test_memory_completion.py
    test_memory_search_filters.py
    test_memory_search_sort.py
    test_index_service.py
```

Two things to note when integrating: `service.py` imports `Repository` under `TYPE_CHECKING` only, so it won't fail at runtime without the module — but once your `kanban.repository.base` exists you can remove the guard. And `SearchService` and its tests have been deleted, absorbed into `IndexService`.

---

