"""Abstract base class for the task index cache.

The index is a derived cache over the filesystem; the filesystem is
always the source of truth. IndexService is never queried as an
authority on what exists — only for search, filtering, path resolution,
and tab-completion support.

IndexService has no knowledge of user context (active board, active
column). Callers populate SearchQuery fields and method arguments for
any scoping they require.

Concrete implementations:

    InMemoryIndexService  — dict-backed, for unit tests
    SqliteIndexService    — SQLite + FTS5, for production use
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID

from ..models import Task
from ..index.query import SearchQuery, SearchResult
from ..storage.base import KanbanRepository

class IndexService(ABC):
    """Cache of task metadata for fast search, lookup, and completion."""

    # ------------------------------------------------------------------
    # Write-through
    #
    # KanbanService calls these after every Repository read or write so
    # the cache stays current. The reconciliation service calls clear()
    # and re-upserts when it detects out-of-band filesystem changes.
    # ------------------------------------------------------------------

    @abstractmethod
    def __init__(self, repository: KanbanRepository) -> None:
        super().__init__()
        self.repository = repository

    @abstractmethod
    def upsert_task(self, task: Task) -> None:
        """Insert or update the indexed record for a task.

        Board and column are derived from task.path. Replaces any
        existing record keyed on task.id.
        """

    @abstractmethod
    def remove_task(self, task: Task) -> None:
        """Remove the indexed record for task_id. No-op if absent."""

    @abstractmethod
    def clear(self, board: str | None = None) -> None:
        """
        Drop indexed records.

        Args:
            board: Remove only records for this board. None removes all.
        """

    @abstractmethod
    def rebuild(self, board: str | None = None) -> None:
        """
        Rebuild the index from scratch by scanning the repository.

        Args:
            board: Restrict to this board, or None for all boards.
        """

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    @abstractmethod
    def get_path(self, task_id: UUID) -> Path | None:
        """
        Return the current filesystem path for task_id, or None.

        The primary use case is resolving a UUID (stable across renames)
        to a path for commands like ``kanban log`` and ``kanban show``.
        """

    @abstractmethod
    def find_by_title(
        self,
        title_prefix: str,
        board: str | None = None,
        column: str | None = None,
    ) -> list[Task]:
        """
        Return tasks whose title starts with title_prefix.

        Matching is exact prefix, case-sensitive — not fuzzy or
        substring. Used for CLI/REPL path resolution (step 3) and for
        path segment tab-completion. Callers decide how to handle zero
        or multiple results.

        Args:
            title_prefix: Left-anchored prefix to match against titles.
            board: Restrict to this board, or None for all boards.
            column: Restrict to this column. Only meaningful with board.
        """

    @abstractmethod
    def known_paths(self, board: str | None = None) -> set[Path]:
        """
        Return the filesystem paths of all currently indexed tasks.

        Used by the reconciliation service to diff the index against
        what is actually on disk and detect out-of-band changes.

        Args:
            board: Restrict to this board, or None for all boards.
        """

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    @abstractmethod
    def list_tags(self, board: str | None = None) -> list[str]:
        """
        Return distinct tags seen across indexed tasks, sorted.

        Used to populate --tag completions in the CLI and REPL.

        Args:
            board: Restrict to tags used in this board, or None for all.
        """

    @abstractmethod
    def list_assigned_to(self, board: str | None = None) -> list[str]:
        """
        Return distinct assigned_to values seen across indexed tasks, sorted.

        Used to populate --assigned_to completions in the CLI and REPL.

        Args:
            board: Restrict to assigned_to values in this board, or None for all.
        """

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """
        Return tasks matching all active filters in query.

        Results are ordered by query.sort, reversed when query.reverse
        is True. Tasks with a None value for the sort field always appear
        last, regardless of direction.

        Args:
            query: Filter, scope, free-text, and sort parameters.
        """