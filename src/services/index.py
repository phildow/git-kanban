"""Index/cache orchestration service.

This service wraps repository index operations so the facade can depend on a
single, testable abstraction for index lifecycle decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from models import TaskFilter
from models import Task
from storage.kanban import KanbanRepository


@dataclass(frozen=True)
class IndexState:
    """Represents the current state of the search index cache."""

    built_at: datetime | None

    @property
    def exists(self) -> bool:
        """Return ``True`` when an index has been built at least once."""
        return self.built_at is not None


class IndexService:
    """Coordinates index cache rebuild and freshness checks."""

    def __init__(self, repository: KanbanRepository) -> None:
        """Create the service with an optional repository for future index backends."""
        self.repository = repository
        self._built_at: datetime | None = None

    def rebuild(self) -> None:
        """Mark the in-memory index state as rebuilt at the current UTC time."""
        self._built_at = datetime.now(timezone.utc)

    def update_task(self, task: Task) -> None:
        """Scaffold for upserting a single task into the index cache."""
        _ = task

    def delete_task(self, task: Task) -> None:
        """Scaffold for removing a single task from the index cache."""
        _ = task

    def search_tasks(self, query: str, filter: TaskFilter | None = None) -> list[Task]:
        raise NotImplementedError()

    def get_state(self) -> IndexState:
        """Return index build metadata as an ``IndexState`` value object."""
        return IndexState(built_at=self._built_at)

    def is_fresh(self, *, max_age_seconds: int) -> bool:
        """Return ``True`` when the index exists and is newer than ``max_age_seconds``."""
        built_at = self._built_at
        if built_at is None:
            return False

        now = datetime.now(timezone.utc)
        if built_at.tzinfo is None:
            built_at = built_at.replace(tzinfo=timezone.utc)

        age = (now - built_at).total_seconds()
        return age <= max_age_seconds
