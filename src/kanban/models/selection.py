from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..models.slug import Slug


@dataclass
class Selection:
    """
    What a visual consumer has selected, for commands that can act on it.

    The TUI is the only consumer with a selection — the CLI runs once and the
    REPL has a prompt, not a cursor — so it is the only one that sets this, and
    everywhere else it stands empty.  It is a live pointer at the screen, not a
    setting: it is held for the session only and never written to userdata,
    unlike the active board of the [UserContext].

    A selection is what was on screen when it was last set, so it can name a
    task that has since been renamed, moved, or deleted.  Whoever acts on one
    resolves it against the store and carries on without it when it no longer
    names anything — a selection is a convenience, never a requirement.
    """

    board:  Slug | None = None
    column: Slug | None = None
    task:   Slug | None = None

    @property
    def is_empty(self) -> bool:
        """Return `True` when nothing is selected."""
        return self.board is None and self.column is None and self.task is None

    @property
    def path(self) -> Path | None:
        """
        Return the path of the selection, as far as it goes: a task, the column
        holding it, or the board.  None when nothing is selected.
        """
        if self.board is None:
            return None

        path = Path("/") / self.board
        if self.column is None:
            return path

        path = path / self.column
        return path / self.task if self.task is not None else path
