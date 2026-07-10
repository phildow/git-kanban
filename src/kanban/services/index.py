"""Forwarding facade over an IndexBase implementation.

Other services depend on IndexService rather than importing an IndexBase
implementation directly. IndexService holds a concrete IndexBase and
forwards every call to it unchanged.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from ..index.base import IndexBase
from ..index.query import SearchQuery, SearchResult
from ..models import Task


class IndexService:
    """Forwards index operations to an injected IndexBase implementation."""

    def __init__(self, index_base: IndexBase) -> None:
        """Wrap index_base, the concrete implementation to forward calls to."""
        self.index_base = index_base

    def upsert_task(self, task: Task) -> None:
        """Insert or update the indexed record for a task."""
        self.index_base.upsert_task(task)

    def remove_task(self, task: Task) -> None:
        """Remove the indexed record for task_id. No-op if absent."""
        self.index_base.remove_task(task)

    def clear(self, board: str | None = None) -> None:
        """Drop indexed records."""
        self.index_base.clear(board)

    def rebuild(self, board: str | None = None) -> None:
        """Rebuild the index from scratch by scanning the repository."""
        self.index_base.rebuild(board)

    def get_path(self, task_id: UUID) -> Path | None:
        """Return the current filesystem path for task_id, or None."""
        return self.index_base.get_path(task_id)

    def find_by_title(
        self,
        title_prefix: str,
        board: str | None = None,
        column: str | None = None,
    ) -> list[Task]:
        """Return tasks whose title starts with title_prefix."""
        return self.index_base.find_by_title(title_prefix, board, column)

    def known_paths(self, board: str | None = None) -> set[Path]:
        """Return the filesystem paths of all currently indexed tasks."""
        return self.index_base.known_paths(board)

    def list_tags(self, board: str | None = None) -> list[str]:
        """Return distinct tags seen across indexed tasks, sorted."""
        return self.index_base.list_tags(board)

    def list_assigned_to(self, board: str | None = None) -> list[str]:
        """Return distinct assigned_to values seen across indexed tasks, sorted."""
        return self.index_base.list_assigned_to(board)

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Return tasks matching all active filters in query."""
        return self.index_base.search(query)
