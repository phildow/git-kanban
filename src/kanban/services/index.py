"""Forwarding facade over an IndexBase implementation.

Other services depend on IndexService rather than importing an IndexBase
implementation directly. IndexService holds a concrete IndexBase and
forwards every call to it unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ..index.base import IndexBase
from ..index.query import SearchQuery, SearchResult
from ..models import Slug, Task
from ..storage.base import KanbanRepository


@dataclass(frozen=True)
class IndexDiff:
    """Diff between indexed paths and repository paths."""

    missing_from_repository: set[Path]
    """Paths known to the index but no longer present in the repository."""

    missing_from_index: set[Path]
    """Paths present in the repository but not yet known to the index."""


class IndexService:
    """Forwards index operations to an injected IndexBase implementation."""

    def __init__(self, index_base: IndexBase, repository: KanbanRepository) -> None:
        """Wrap index_base, the concrete implementation to forward calls to.

        repository is used for rebuild(), which scans the filesystem
        source of truth to repopulate index_base.
        """
        self.index_base = index_base
        self.repository = repository

    # Forwarding methods

    def upsert_task(self, task: Task) -> None:
        """Insert or update the indexed record for a task."""
        self.index_base.upsert_task(task)

    def remove_task(self, task: Task) -> None:
        """Remove the indexed record for task_id. No-op if absent."""
        self.index_base.remove_task(task)

    def clear(self, board: Slug | None = None) -> None:
        """Drop indexed records."""
        self.index_base.clear(board)

    def get_path(self, task_id: UUID) -> Path | None:
        """Return the current filesystem path for task_id, or None."""
        return self.index_base.get_path(task_id)

    def find_by_title(
        self,
        title_prefix: str,
        board: Slug | None = None,
        column: Slug | None = None,
    ) -> list[Task]:
        """Return tasks whose title starts with title_prefix."""
        return self.index_base.find_by_title(title_prefix, board, column)

    def list_tags(self, board: Slug | None = None) -> list[str]:
        """Return distinct tags seen across indexed tasks, sorted."""
        return self.index_base.list_tags(board)

    def list_assigned_to(self, board: Slug | None = None) -> list[str]:
        """Return distinct assigned_to values seen across indexed tasks, sorted."""
        return self.index_base.list_assigned_to(board)

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Return tasks matching all active filters in query."""
        return self.index_base.search(query)

    # Custom methods

    def rebuild(self, board: Slug | None = None) -> None:
        """Rebuild the index from scratch by scanning the repository."""
        self.index_base.clear(board)
        for task in self.repository.get_tasks(board=board):
            self.index_base.upsert_task(task)

    def diff(self, board: Slug | None = None) -> IndexDiff:
        """Diff indexed paths against the repository's paths.

        Compares index_base.known_paths() against the paths of tasks
        returned by repository.get_tasks() to detect out-of-band
        filesystem changes without mutating either side.
        """
        indexed_paths = self.index_base.known_paths(board)
        repository_paths = {task.path for task in self.repository.get_tasks(board=board)}
        return IndexDiff(
            missing_from_repository=indexed_paths - repository_paths,
            missing_from_index=repository_paths - indexed_paths,
        )

    # TODO: remove from service
    def known_paths(self, board: Slug | None = None) -> set[Path]:
        """Return the filesystem paths of all currently indexed tasks."""
        return self.index_base.known_paths(board)
