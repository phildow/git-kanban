"""Shared fixtures for TUI tests."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from kanban.models import Board, Column, Priority, Slug, Task

TASK_ID = UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")


def make_task(**overrides: object) -> Task:
    """Return a task with predictable defaults, overridable field by field."""
    fields: dict[str, object] = {
        "id": TASK_ID,
        "title": "Fix login bug",
        "slug": Slug("fix-login-bug"),
        "board": Slug("main"),
        "column": Slug("todo"),
        "priority": Priority.HIGH,
        "assigned_to": "alice",
        "due_date": datetime(2026, 6, 15),
        "tags": ["bug", "auth"],
    }
    fields.update(overrides)
    return Task(**fields)  # type: ignore[arg-type]


def make_column(**overrides: object) -> Column:
    """Return a column with predictable defaults, overridable field by field."""
    fields: dict[str, object] = {
        "id": UUID("11111111-1111-1111-1111-111111111111"),
        "name": "To Do",
        "slug": Slug("todo"),
        "board": Slug("main"),
        "position": 0,
    }
    fields.update(overrides)
    return Column(**fields)  # type: ignore[arg-type]


def make_board(**overrides: object) -> Board:
    """Return a board with predictable defaults, overridable field by field."""
    fields: dict[str, object] = {
        "id": UUID("22222222-2222-2222-2222-222222222222"),
        "name": "Main",
        "slug": Slug("main"),
    }
    fields.update(overrides)
    return Board(**fields)  # type: ignore[arg-type]
