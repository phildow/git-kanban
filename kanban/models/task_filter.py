from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskFilter:
    """Optional criteria for narrowing task lists and search results.

    All fields are optional; `None` means "do not filter by this field".
    """
    
    assigned_to: str | None = None
    priority:    str | None = None          # "low" | "medium" | "high"
    tags:        list[str] = field(default_factory=list)
    due_before:  datetime | None = None
    due_after:   datetime | None = None
    created_by:  str | None = None
