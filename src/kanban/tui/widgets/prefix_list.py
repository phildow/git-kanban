"""A list whose entries can be reached by typing the start of their name."""

from __future__ import annotations

import time
from typing import Sequence

from rich.text import Text
from textual import events
from textual.widgets import OptionList

# How long a typed prefix stays live.  Type again within this and the letters
# accumulate; pause longer and the next key starts a new search.
SEARCH_TIMEOUT = 1.0


class PrefixList(OptionList):
    """
    An option list that jumps to the entry a typed prefix matches.

    Each entry pairs a key — what typing is matched against — with what the row
    shows.  Arrow keys move as usual; typing jumps.
    """

    def __init__(
        self, entries: Sequence[tuple[str, Text]], *, id: str | None = None
    ) -> None:
        """Create a list over `entries`, each a key and the row to show for it."""
        super().__init__(*[label for _, label in entries], id=id)

        self.keys = [key for key, _ in entries]
        self._search = ""
        self._searched_at = 0.0

    @property
    def selected_key(self) -> str | None:
        """Return the key of the highlighted entry, or None when there is none."""
        index = self.highlighted
        if index is None or not (0 <= index < len(self.keys)):
            return None
        return self.keys[index]

    def key_at(self, index: int | None) -> str | None:
        """Return the key of the entry at `index`, or None when out of range."""
        if index is None or not (0 <= index < len(self.keys)):
            return None
        return self.keys[index]

    @property
    def search(self) -> str:
        """Return the prefix currently being typed."""
        return self._search

    def on_key(self, event: events.Key) -> None:
        """
        Extend the typed prefix and jump to what it matches.

        Printable keys are consumed here rather than left to bubble: the board
        beneath binds plenty of single letters, and typing `q` in a list should
        not quit the app.
        """
        if event.key == "backspace" and self._search:
            event.stop()
            self._set_search(self._search[:-1])
            return

        character = event.character
        if character is None or not character.isprintable() or character == " ":
            return

        event.stop()
        self._set_search(self._expired_search() + character)

    def _expired_search(self) -> str:
        """Return the prefix so far, or nothing if the user has paused."""
        if time.monotonic() - self._searched_at > SEARCH_TIMEOUT:
            return ""
        return self._search

    def _set_search(self, search: str) -> None:
        """Adopt `search` and highlight what it matches, if anything does."""
        self._searched_at = time.monotonic()

        if not search:
            self._search = ""
            self._show_search()
            return

        index = next(
            (i for i, key in enumerate(self.keys) if key.startswith(search)), None
        )
        # A key that matches nothing is dropped rather than stranding the search
        # on a prefix that can never match again.
        if index is None:
            return

        self._search = search
        self.highlighted = index
        self._show_search()

    def _show_search(self) -> None:
        """Show what is being typed, so the jump does not look like magic."""
        self.border_subtitle = f" {self._search} " if self._search else ""
