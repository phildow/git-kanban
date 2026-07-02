from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ..models.slug import Slug

@dataclass
class Column:
    """
    A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.
    """

    id:         UUID
    name:       str
    slug:       Slug
    board:      Slug
    # TODO: why does the col have a position but the task doesn't?  
    # Shouldn't the task have a position too? Or remove this
    position:   int
    
    task_count: int = 0

    @property
    def filename(self) -> str:
        return self.slug

    @property
    def path(self) -> Path:
        return Path(f"/{self.board}/{self.slug}")
    