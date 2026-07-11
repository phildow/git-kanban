"""Test helpers for the index test suite."""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from kanban.models import Task  # Priority


def make_task(
    title: str = "Fix login bug",
    board: str = "my-project",
    column: str = "todo",
    id: UUID | None = None,
    slug: str | None = None,
    created_by: str = "alice",
    assigned_to: str | None = None,
    # priority: Priority | None = None,
    priority: str | None = None,
    due_date: date | None = None,
    tags: tuple[str, ...] = (),
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    body: str = "",
) -> Task:
    """Build a Task with derived path and sensible defaults."""
    derived_slug = slug or title.lower().replace(" ", "-")
    return Task(
        id=id or uuid4(),
        title=title,
        slug=derived_slug,
        board=board,
        column=column,
        created_by=created_by,
        assigned_to=assigned_to,
        priority=priority,
        due_date=due_date,
        tags=tags,
        created_at=created_at,
        updated_at=updated_at,
        body=body,
    )


def utc(year: int, month: int, day: int) -> datetime:
    """Convenience constructor for UTC datetimes in tests."""
    return datetime(year, month, day, tzinfo=timezone.utc)
