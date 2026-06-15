from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class UserContext:
    """Persisted current board/column scope used by CLI commands."""

    board: Optional[str] = None
    column: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Return `True` when neither board nor column is set."""
        return self.board is None and self.column is None
