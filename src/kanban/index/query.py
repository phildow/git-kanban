"""Query and result types for the index layer.

These are shared between IndexBase and SearchService. SearchQuery is
the single parameter object for all filtering, scoping, and sorting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from ..models import Priority, Task


class SortField(str, Enum):
    """Fields that search and list results can be ordered by.

    Values match the --sort flag strings accepted by the CLI so they can
    be passed through directly without translation.
    """

    TITLE = "title"
    PRIORITY = "priority"
    DUE_DATE = "due-date"
    CREATED_AT = "created-at"
    UPDATED_AT = "updated-at"
    CREATED_BY = "created-by"


@dataclass(frozen=True)
class SearchQuery:
    """Filters, scope, free-text, and sort parameters for a search.

    Every field defaults to an inactive state (None or empty) so callers
    only set what they need. All active fields are combined with AND.

    board=None means all boards. Callers that want active-board scoping
    (e.g. SearchService applying user context) are responsible for
    populating board before passing the query to IndexBase.
    """

    text: str | None = None          # case-insensitive substring of title or body
    board: str | None = None         # None = all boards
    column: str | None = None        # None = all columns; only used with board
    # Columns to leave out, by slug.  Search reaches everywhere by default, the
    # archive included, so this is how a caller narrows it — `--exclude archive`.
    exclude_columns: tuple[str, ...] = field(default_factory=tuple)
    assigned_to: str | None = None
    priority: Priority | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)  # all must match
    created_by: str | None = None
    due_before: date | None = None   # exclusive: due_date < due_before
    due_after: date | None = None    # exclusive: due_date > due_after
    sort: SortField = SortField.TITLE
    reverse: bool = False


@dataclass(frozen=True)
class SearchResult:
    """A matched task with an optional relevance score.

    score is populated by FTS-backed implementations via bm25 and is
    None for InMemoryIndex, which has no ranking concept. Tests
    that assert on relevance ordering should target the SQLite
    implementation.
    """

    task: Task
    score: float | None = None