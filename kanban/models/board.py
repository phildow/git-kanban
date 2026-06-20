from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Board:
    """A kanban board containing an ordered list of columns."""
    # TODO: add slug and path properties for easier referencing in the REPL and storage layers
    
    name: str
    # slug: str

    # TODO: is this even used - a core principle is that we do not cache filesystem state in memory
    columns: list[Column] = field(default_factory=list)
    
    column_count: int = 0
    task_count: int = 0

    # Do I want to include created_at and created_by here? 
    # Maybe not since boards are more about organization than workflow?

    @property
    def path(self) -> Path:
        return Path(f"/{self.name}")

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "-")