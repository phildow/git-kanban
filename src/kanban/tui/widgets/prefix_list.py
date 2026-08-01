"""A list whose entries can be reached by typing the start of their name."""

from __future__ import annotations

import time
from typing import Sequence

from rich.text import Text
from textual import events
from textual.widgets import OptionList
from textual.widgets.option_list import Option

# How long a typed prefix stays live.  Type again within this and the letters
# accumulate; pause longer and the next key starts a new search.
SEARCH_TIMEOUT = 1.0


def _options(entries: Sequence[tuple[str | None, Text]]) -> list[Option]:
    """Turn entries into options, the keyless ones disabled so they read as headings."""
    return [Option(label, disabled=key is None) for key, label in entries]


class PrefixList(OptionList):
    """
    An option list that jumps to the entry a typed prefix matches.

    Each entry pairs a key — what typing is matched against — with what the row
    shows.  Arrow keys move as usual; typing jumps.

    An entry whose key is None is a heading: it is drawn like any other row but
    cannot be selected, is stepped over by the arrow keys, and is never what
    typing lands on.  That is how a list groups what it holds.
    """

    def __init__(
        self,
        entries: Sequence[tuple[str | None, Text]],
        *,
        show_search: bool = True,
        reserved: Sequence[str] = (),
        id: str | None = None,
    ) -> None:
        """
        Create a list over `entries`, each a key and the row to show for it.

        `show_search` puts the prefix being typed in the border subtitle; lists
        without a border to carry it pass False and jump silently.

        `reserved` names characters the list will not take for its own search,
        letting them through to whatever binds them instead.  A screen that
        wants a letter of its own — `e` to edit, say — names it here, at the
        cost of that letter no longer starting a jump.
        """
        super().__init__(*_options(entries), id=id)

        self.keys = [key for key, _ in entries]
        self.show_search = show_search
        self.reserved = frozenset(reserved)
        self._search = ""
        self._searched_at = 0.0

    def set_entries(self, entries: Sequence[tuple[str | None, Text]]) -> None:
        """
        Replace the list's contents with `entries`, keys and rows together.

        Used when the data behind a list changes while it is on screen — a
        configuration value edited in place, say.  Any prefix being typed is
        dropped, since it was matched against the keys that have just gone.
        """
        self.keys = [key for key, _ in entries]
        self._search = ""
        self._show_search()

        self.clear_options()
        self.add_options(_options(entries))

    @property
    def first_key_index(self) -> int | None:
        """Return the row of the first selectable entry, or None when there is none."""
        return next((i for i, key in enumerate(self.keys) if key is not None), None)

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
        not quit the app.  The exceptions are the characters named `reserved`,
        which are left to bubble to whatever binds them.
        """
        if event.key == "backspace" and self._search:
            event.stop()
            self._set_search(self._search[:-1])
            return

        character = event.character
        if character is None or not character.isprintable() or character == " ":
            return
        if character in self.reserved:
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
            (
                i
                for i, key in enumerate(self.keys)
                if key is not None and key.startswith(search)
            ),
            None,
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
        if not self.show_search:
            return
        self.border_subtitle = f" {self._search} " if self._search else ""
