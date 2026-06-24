from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from models.column import Column

@dataclass
class Board:
    """A kanban board containing an ordered list of columns."""
    # TODO: add slug and path properties for easier referencing in the REPL and storage layers
    
    name: str
    slug: str = ""

    # TODO: remove this: a core principle is that we do not cache filesystem state in memory
    #       or it should be a list of strings, not Column objects
    columns: list[Column] = field(default_factory=list)
    
    column_count: int = 0
    task_count: int = 0

    # Do I want to include created_at and created_by here? 
    # Maybe not since boards are more about organization than workflow?

    @property
    def filename(self) -> str:
        return self.slug

    @property
    def path(self) -> Path:
        return self.slug
    