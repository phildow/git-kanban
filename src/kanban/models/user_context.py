from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.slug import Slug

@dataclass
class UserContext:
    """Persisted current board/column scope used by CLI commands."""

    board:  Slug | None = None
    column: Slug | None = None

    @property
    def is_empty(self) -> bool:
        """Return `True` when neither board nor column is set."""
        return self.board is None and self.column is None

    @property
    def path(self) -> Path:
        """Return the current context as a path string (e.g. "/board/column")."""
        root = Path("/")
        if self.board and self.column:
            return root / self.board / self.column
        if self.board:
            return root / self.board
        return root