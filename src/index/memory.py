"""In-memory IndexService implementation, for use in tests.

Provides the same filter and scope semantics as the SQLite implementation
using plain Python. SearchResult.score is always None — there is no bm25
ranking equivalent. Tests that assert on relevance ordering should target
the SQLite implementation instead.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from models import Task # Priority
from index.base import IndexService
from index.query import SearchQuery, SearchResult, SortField
from storage.kanban import KanbanRepository

# _PRIORITY_ORDER: dict[Priority, int] = {
#     Priority.LOW: 0,
#     Priority.MEDIUM: 1,
#     Priority.HIGH: 2,
# }

_PRIORITY_ORDER: dict[str, int] = {
    "low": 0,
    "medium": 1,
    "high": 2,
}

# Sentinels for nullable sort fields; must match the timezone-awareness
# of domain datetimes (always UTC per the frontmatter spec).
_DATETIME_MIN = datetime.min.replace(tzinfo=timezone.utc)


class InMemoryIndexService(IndexService):
    """IndexService backed by a dict[UUID, Task]."""

    def __init__(self, repository: KanbanRepository) -> None:
        super().__init__(repository)
        self._tasks: dict[UUID, Task] = {}

    # ------------------------------------------------------------------
    # Write-through
    # ------------------------------------------------------------------

    def upsert_task(self, task: Task) -> None:
        self._tasks[task.id] = task

    def remove_task(self, task_id: UUID) -> None:
        self._tasks.pop(task_id, None)

    def clear(self, board: str | None = None) -> None:
        if board is None:
            self._tasks.clear()
            return
        stale = [tid for tid, t in self._tasks.items() if t.board == board]
        for tid in stale:
            del self._tasks[tid]

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    def get_path(self, task_id: UUID) -> Path | None:
        task = self._tasks.get(task_id)
        return task.path if task is not None else None

    def find_by_title(
        self,
        title_prefix: str,
        board: str | None = None,
        column: str | None = None,
    ) -> list[Task]:
        return [
            t for t in self._tasks.values()
            if t.title.startswith(title_prefix) and _in_scope(t, board, column)
        ]

    def known_paths(self, board: str | None = None) -> set[Path]:
        return {
            t.path for t in self._tasks.values()
            if board is None or t.board == board
        }

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def list_tags(self, board: str | None = None) -> list[str]:
        tags: set[str] = set()
        for t in self._tasks.values():
            if board is None or t.board == board:
                tags.update(t.tags)
        return sorted(tags)

    def list_assignees(self, board: str | None = None) -> list[str]:
        return sorted({
            t.assignee for t in self._tasks.values()
            if t.assignee is not None and (board is None or t.board == board)
        })

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: SearchQuery) -> list[SearchResult]:
        matches = [t for t in self._tasks.values() if _matches(t, query)]
        # Two stable passes keep None-valued tasks at the end regardless
        # of the reverse flag: first sort by value (respects reverse),
        # then sort by is_none ascending (stable, so within-group order
        # from the first pass is preserved).
        matches.sort(key=_value_key(query.sort), reverse=query.reverse)
        matches.sort(key=_none_key(query.sort))
        return [SearchResult(task=t) for t in matches]


# ------------------------------------------------------------------
# Module-level helpers (not part of the public interface)
# ------------------------------------------------------------------

def _in_scope(task: Task, board: str | None, column: str | None) -> bool:
    """Return True if task falls within the given board/column scope."""
    if board is not None and task.board != board:
        return False
    if column is not None and task.column != column:
        return False
    return True


def _matches(task: Task, query: SearchQuery) -> bool:
    """Return True if task satisfies every non-None filter on query."""
    if not _in_scope(task, query.board, query.column):
        return False
    if query.assignee is not None and task.assignee != query.assignee:
        return False
    if query.priority is not None and task.priority != query.priority:
        return False
    if query.created_by is not None and task.created_by != query.created_by:
        return False
    if query.tags and not set(query.tags).issubset(task.tags):
        return False
    if query.due_before is not None:
        if task.due_date is None or task.due_date >= query.due_before:
            return False
    if query.due_after is not None:
        if task.due_date is None or task.due_date <= query.due_after:
            return False
    if query.text is not None and query.text.lower() not in task.title.lower():
        return False
    return True


def _value_key(sort: SortField) -> Callable[[Task], Any]:
    """Return a key function that extracts the comparable sort value.

    For nullable fields, returns a fallback sentinel when the value is
    None so the first sort pass does not raise TypeError on comparison.
    The second pass (_none_key) then moves those tasks to the end.
    """
    match sort:
        case SortField.TITLE:
            return lambda t: t.title.lower()
        case SortField.PRIORITY:
            return lambda t: _PRIORITY_ORDER.get(t.priority, 0)
        case SortField.DUE_DATE:
            return lambda t: t.due_date or date.min
        case SortField.CREATED_AT:
            return lambda t: t.created_at or _DATETIME_MIN
        case SortField.UPDATED_AT:
            return lambda t: t.updated_at or _DATETIME_MIN
        case SortField.CREATED_BY:
            return lambda t: t.created_by.lower()


def _none_key(sort: SortField) -> Callable[[Task], bool]:
    """Return a key that is True when the task's sort field is None.

    Used as the second stable sort pass so that None-valued tasks always
    appear last, regardless of the reverse flag on the first pass.
    """
    match sort:
        case SortField.PRIORITY:
            return lambda t: t.priority is None
        case SortField.DUE_DATE:
            return lambda t: t.due_date is None
        case SortField.CREATED_AT:
            return lambda t: t.created_at is None
        case SortField.UPDATED_AT:
            return lambda t: t.updated_at is None
        case _:  # TITLE, CREATED_BY — never None
            return lambda t: False