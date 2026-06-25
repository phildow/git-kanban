from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from models.column import Column
from models.slug import Slug

@dataclass
class Board:
    """A kanban board containing an ordered list of columns."""
    
    id:   UUID
    name: str
    slug: Slug

    column_count: int = 0
    task_count: int = 0

    # created_at: datetime | None = None
    # created_by: str | None = None

    # TODO: remove this: a core principle is that we do not cache filesystem state in memory
    #       or it should be a list of strings, not Column objects
    columns: list[Column] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.slug

    @property
    def path(self) -> Path:
        return Path(self.slug)
    