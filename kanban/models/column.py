from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class Column:
    """A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.
    """

    name: str
    board: str
    position: int
