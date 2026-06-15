from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Task:
    """Canonical task entity used by repository and service layers.

    `board` and `column` describe the task's current location. Other fields
    capture metadata rendered in the CLI and used for filtering/sorting.
    """

    id: UUID
    title: str
    slug: str = ""
    board: Optional[str] = None
    column: Optional[str] = None
    created_by: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    body: str = ""


@dataclass
class Column:
    """A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.
    """

    name: str
    board: str
    position: int


@dataclass
class Board:
    """A kanban board containing an ordered list of columns."""

    name: str
    columns: list[Column] = field(default_factory=list)

    # Do I want to include created_at and created_by here? 
    # Maybe not since boards are more about organization than workflow?


@dataclass
class TaskFilter:
    """Optional criteria for narrowing task lists and search results.

    All fields are optional; `None` means "do not filter by this field".
    """

    board: Optional[str] = None
    column: Optional[str] = None
    assignee: Optional[str] = None
    priority: Optional[str] = None
    tag: Optional[str] = None
    created_by: Optional[str] = None
    due_before: Optional[datetime] = None
    due_after: Optional[datetime] = None


@dataclass
class UserContext:
    """Persisted current board/column scope used by CLI commands."""

    board: Optional[str] = None
    column: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Return `True` when neither board nor column is set."""
        return self.board is None and self.column is None
