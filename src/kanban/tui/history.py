"""
The lines typed into an input bar, cycled with ↑/↓ and kept between sessions.

The REPL gets this from readline, which the TUI has no access to — Textual owns
the terminal — so the bars keep their own.  A history is a plain text file of
one entry per line, oldest first, held under `.kanban/` with the rest of the
local machine state.  It is written by the TUI alone, so the file is never
shared with a readline session that would overwrite it wholesale on exit.
"""

from __future__ import annotations

import logging
from pathlib import Path

# How many entries a history file keeps.  Old enough entries are of no use to
# anyone, and the file is read in full every time the TUI starts.
HISTORY_LIMIT = 500


class CommandHistory:
    """
    What has been typed into one bar, and where ↑/↓ have moved through it.

    The cursor sits on the entry being shown, or on the draft — the line the
    user had typed before they started moving — which is restored on the way
    back down.  A history with no file behind it works the same for as long as
    the session lasts; nothing is persisted.
    """

    def __init__(self, path: Path | None, *, limit: int = HISTORY_LIMIT) -> None:
        """Create a history backed by `path`, keeping at most `limit` entries."""
        self.path = path
        self.limit = limit

        self._entries: list[str] = []
        # The entry ↑/↓ have reached, or None while the bar is on the draft.
        self._cursor: int | None = None
        self._draft = ""

    @property
    def entries(self) -> list[str]:
        """Return the entries held, oldest first."""
        return list(self._entries)

    # ── Cycling ───────────────────────────────────────────────────────────────

    def previous(self, draft: str) -> str | None:
        """
        Return the entry before the one showing, or None when there is none.

        `draft` is what the bar holds now; it is remembered on the first step
        back so that stepping forward again returns to it.
        """
        if not self._entries:
            return None

        if self._cursor is None:
            self._draft = draft
            self._cursor = len(self._entries) - 1
        elif self._cursor > 0:
            self._cursor -= 1
        else:
            return None

        return self._entries[self._cursor]

    def next(self) -> str | None:
        """
        Return the entry after the one showing, or the draft at the newest end.

        None means the bar was already on the draft and has nothing to move to.
        The draft itself may be empty, which is a value the bar does display —
        hence the distinction.
        """
        if self._cursor is None:
            return None

        if self._cursor < len(self._entries) - 1:
            self._cursor += 1
            return self._entries[self._cursor]

        self._cursor = None
        return self._draft

    def reset(self) -> None:
        """Return to the draft end, which is where a newly opened bar starts."""
        self._cursor = None
        self._draft = ""

    # ── Recording ─────────────────────────────────────────────────────────────

    def append(self, line: str) -> None:
        """
        Record a submitted `line`, and return the cursor to the draft end.

        A blank line is not an entry, and a line repeated straight after itself
        is not worth a second one — cycling past the same command twice tells
        the user nothing.
        """
        entry = line.strip()
        self.reset()

        if not entry:
            return
        if self._entries and self._entries[-1] == entry:
            return

        self._entries.append(entry)
        del self._entries[: -self.limit]

    # ── Storage ───────────────────────────────────────────────────────────────

    def load(self) -> None:
        """
        Read the history file, replacing whatever is held.

        A history is a convenience: a missing or unreadable file leaves the bar
        with an empty one rather than stopping the TUI from opening.
        """
        path = self.path
        if path is None or not path.exists():
            return

        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            logging.warning("Could not read TUI history %s: %s", path, exc)
            return

        self._entries = [line for line in (raw.strip() for raw in lines) if line][
            -self.limit :
        ]
        self.reset()

    def save(self) -> None:
        """Write the history file, or log why it could not be written."""
        path = self.path
        if path is None:
            return

        try:
            path.write_text(
                "".join(f"{entry}\n" for entry in self._entries), encoding="utf-8"
            )
        except OSError as exc:
            logging.warning("Could not save TUI history %s: %s", path, exc)
