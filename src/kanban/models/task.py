from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from uuid import UUID

from ..models.priority import Priority
from ..models.slug import Slug
from ..protocols.sluggable import Sluggable

@dataclass
class Task(Sluggable):
    """
    Canonical task entity used by repository and service layers.

    `board` and `column` describe the task's current location and are not saved 
    or restored from the repository.  They are only used for rendering and filtering 
    in the CLI. Other fields capture metadata rendered in the CLI and used for filtering/sorting.
    """

    id:             UUID
    title:          str
    slug:           Slug
    board:          Slug
    column:         Slug
    
    created_by:     str | None = None
    assigned_to:    str | None = None
    priority:       Priority | None = None
    due_date:       datetime | None = None
    tags:           list[str] = field(default_factory=list)
    created_at:     datetime | None = None
    updated_at:     datetime | None = None
    body:           str = ""
    
    @property
    def path(self) -> Path:
        return Path(f"/{self.board}/{self.column}/{self.slug}")
    