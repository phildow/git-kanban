from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Column:
    """
    A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.
    """
    # TODO: add slug and path properties for easier referencing in the REPL and storage layers

    name: str
    # slug: str
    board: str
    position: int
    task_count: int = 0

    @property
    def path(self) -> Path:
        return Path(f"/{self.board}/{self.name}")

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "-")
    
    @property
    def filename(self) -> str:
        return self.slug