"""
The two bottom-docked input overlays.

`FilterBar` live-filters the visible cards as the user types (`/`).  `CommandBar`
accepts a full REPL command line (`:`).  Both complete on Tab, both cycle a
history of their own on ↑/↓, and both are `Input` subclasses so the board screen
can tell their messages apart by widget type.
"""

from __future__ import annotations

from os.path import commonprefix
from typing import Iterable

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input, Static

from ...protocols.completer import Completer
from ..history import CommandHistory
from .text import TextInput


class CompletingInput(TextInput):
    """
    An input that completes what has been typed when Tab is pressed, and
    cycles what has been typed before it with ↑/↓.

    A single candidate is filled in; several are narrowed to their common
    prefix and reported with `Ambiguous` so the screen can show them.  The
    candidates come from a `Completer`, and the past lines from a
    `CommandHistory`, both supplied by the screen — the widget never asks the
    kanban service anything itself.
    """

    # Tab is bound on the screen for focus movement, and ctrl+c on the app for
    # quitting and on `Input` for copying — none of them with priority, so a
    # binding here takes the key while one of these bars has focus.
    #
    # ↑/↓ are the board's card navigation, which a bar with the focus must not
    # leave running: the cards would move under a user who is typing, and the
    # selection a command is meant for is the card they started typing on.  The
    # bar claims them for its history, as the REPL's readline does.
    BINDINGS = [
        Binding("tab", "complete", "Complete", show=False),
        Binding("ctrl+c", "clear", "Clear", show=False),
        Binding("up", "previous", "Previous", show=False),
        Binding("down", "next", "Next", show=False),
    ]

    class Ambiguous(Message):
        """Posted when Tab found more than one candidate."""

        def __init__(self, input: CompletingInput, candidates: list[str]) -> None:
            """Report the `candidates` Tab could not choose between."""
            super().__init__()
            self.input = input
            self.candidates = candidates

    def __init__(self, *, placeholder: str = "", id: str | None = None) -> None:
        """Create a bar with no completer or history; the screen attaches them on mount."""
        super().__init__(placeholder=placeholder, id=id)
        self.completer: Completer | None = None
        self.history: CommandHistory | None = None

    def action_clear(self) -> None:
        """
        Empty the bar, leaving it open and focused to type into again.

        Starting over means starting over in the history too: ↑ goes back to the
        newest entry rather than carrying on from wherever it had reached, and
        there is no longer a draft worth returning to.
        """
        self.value = ""
        if self.history is not None:
            self.history.reset()

    def action_previous(self) -> None:
        """Show the line typed before the one showing, if there is one."""
        if self.history is not None:
            self._show(self.history.previous(self.value))

    def action_next(self) -> None:
        """Show the line typed after the one showing, or the draft at the end of them."""
        if self.history is not None:
            self._show(self.history.next())

    def _show(self, line: str | None) -> None:
        """
        Put `line` in the bar, cursor at its end, leaving the bar alone for None.

        None is the history saying there was nowhere to move — at the oldest
        entry, or already on the draft — where the line the user is looking at
        should stay as it is.
        """
        if line is None:
            return

        self.value = line
        self.cursor_position = len(self.value)

    def action_complete(self) -> None:
        """Complete the token at the cursor, as far as the candidates agree."""
        completer = self.completer
        if completer is None:
            return

        line, cursor = self.value, self.cursor_position
        candidates = completer.complete(line, cursor)
        if not candidates:
            return

        partial = completer.partial_at(line, cursor)

        if len(candidates) == 1:
            # A settled token: leave a space ready for the next one.
            self._replace(partial, f"{candidates[0]} ")
            return

        shared = commonprefix(candidates)
        if len(shared) > len(partial):
            self._replace(partial, shared)

        self.post_message(self.Ambiguous(self, candidates))

    def _replace(self, partial: str, replacement: str) -> None:
        """Swap the `partial` token before the cursor for `replacement`."""
        cursor = self.cursor_position
        start = cursor - len(partial)

        self.value = f"{self.value[:start]}{replacement}{self.value[cursor:]}"
        self.cursor_position = start + len(replacement)


class FilterBar(CompletingInput):
    """Inline search bar that live-filters visible cards as the user types."""

    def __init__(self, *, id: str | None = None) -> None:
        """Create a hidden filter bar; the board screen reveals it on demand."""
        super().__init__(placeholder="filter cards…", id=id)


class CommandBar(CompletingInput):
    """Command line accepting REPL syntax, parsed with the REPL's own parser."""

    def __init__(self, *, id: str | None = None) -> None:
        """Create a hidden command bar; the board screen reveals it on demand."""
        super().__init__(placeholder="command (REPL syntax)", id=id)


def format_hints(hints: Iterable[tuple[str, str]]) -> str:
    """
    Return key/description pairs marked up the way the footer renders them.

    The hint bar stands in for the footer while a mode is active, so it should
    not look like something else: same key colour, same weight, same spacing.
    """
    return " ".join(
        f"[$footer-key-foreground bold]{key}[/]"
        f" [$footer-description-foreground]{description}[/]"
        for key, description in hints
    )


class ModeBar(Static):
    """
    Contextual key hints that replace the footer while a mode is active.

    The footer covers normal mode; this bar covers move mode and the input
    overlays, so the user is never guessing what is available.
    """

    def __init__(self, *, id: str | None = None) -> None:
        """Create an empty, hidden mode bar."""
        super().__init__("", id=id)

    def show(self, hints: str, *, muted: bool = False) -> None:
        """
        Display `hints` and reveal the bar.

        `muted` dims text the bar is not styling itself.  It is a CSS class
        rather than markup because the muted colour carries an alpha, and only
        the stylesheet applies that.
        """
        self.set_class(muted, "-muted")
        self.update(hints)
        self.add_class("-visible")

    def hide(self) -> None:
        """Clear the hints and hide the bar."""
        self.update("")
        self.remove_class("-visible")
