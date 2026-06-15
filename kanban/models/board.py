from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Board:
    """A kanban board containing an ordered list of columns."""

    name: str
    columns: list[Column] = field(default_factory=list)

    # Do I want to include created_at and created_by here? 
    # Maybe not since boards are more about organization than workflow?
