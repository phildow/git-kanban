from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.slug import Slug

@dataclass
class UserContext:
    """Persisted current board scope used by CLI commands."""

    board:  Slug | None = None

    @property
    def is_empty(self) -> bool:
        """Return `True` when no board is set."""
        return self.board is None

    @property
    def path(self) -> Path:
        """Return the current context as a path string (e.g. "/board")."""
        root = Path("/")
        if self.board:
            return root / self.board
        return root