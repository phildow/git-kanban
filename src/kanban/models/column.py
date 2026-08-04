from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from ..models.slug import Slug
from ..protocols.sluggable import Sluggable

ROLE_ARCHIVE = "archive"
"""The role of the column archived tasks are held in."""

ARCHIVE_COLUMN_NAME = "Archive"
ARCHIVE_COLUMN_SLUG = Slug("archive")

@dataclass
class Column(Sluggable):
    """
    A single workflow column within a board.

    `position` is the zero-based display order inside the owning board.

    `role` marks a column the application treats specially rather than as one
    more step in the workflow.  Only `archive` is defined; a column with no role
    is an ordinary one.  The role is assigned when the column is created and
    survives a rename, so the archive is found by role and never by its slug.
    """

    id:         UUID
    name:       str
    slug:       Slug
    board:      Slug
    position:   int

    task_count: int = 0
    role:       str | None = None

    deleted:    bool = False
    """Set on the record returned by a delete; never read from storage."""

    @property
    def path(self) -> Path:
        return Path(f"/{self.board}/{self.slug}")

    @property
    def is_archive(self) -> bool:
        """Return True when this is the board's archive column."""
        return self.role == ROLE_ARCHIVE
