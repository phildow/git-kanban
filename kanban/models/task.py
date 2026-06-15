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
