from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID


@dataclass
class Column:
    """
    A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.
    """

    name: str
    slug: str
    board: str
    position: int
    task_count: int = 0

    @property
    def filename(self) -> str:
        return self.slug

    @property
    def path(self) -> Path:
        return Path(self.slug)
    