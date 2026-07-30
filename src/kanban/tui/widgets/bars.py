"""
The two bottom-docked input overlays.

`FilterBar` live-filters the visible cards as the user types (`/`).  `CommandBar`
accepts a full REPL command line (`:`).  Both are plain `Input` subclasses so
the board screen can tell their messages apart by widget type.
"""

from __future__ import annotations

from textual.widgets import Input, Static


class FilterBar(Input):
    """Inline search bar that live-filters visible cards as the user types."""

    def __init__(self, *, id: str | None = None) -> None:
        """Create a hidden filter bar; the board screen reveals it on demand."""
        super().__init__(placeholder="filter cards…", id=id)


class CommandBar(Input):
    """Command line accepting REPL syntax, parsed with the REPL's own parser."""

    def __init__(self, *, id: str | None = None) -> None:
        """Create a hidden command bar; the board screen reveals it on demand."""
        super().__init__(placeholder="command (REPL syntax)", id=id)


class ModeBar(Static):
    """
    Contextual key hints that replace the footer while a mode is active.

    The footer covers normal mode; this bar covers move mode and the input
    overlays, so the user is never guessing what is available.
    """

    def __init__(self, *, id: str | None = None) -> None:
        """Create an empty, hidden mode bar."""
        super().__init__("", id=id)

    def show(self, hints: str) -> None:
        """Display `hints` and reveal the bar."""
        self.update(hints)
        self.add_class("-visible")

    def hide(self) -> None:
        """Clear the hints and hide the bar."""
        self.update("")
        self.remove_class("-visible")
