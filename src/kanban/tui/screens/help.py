"""The help modal: a reference for the board screen's key bindings."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

NORMAL_BINDINGS: list[tuple[str, str]] = [
    ("←/→ or h/l", "move focus between columns"),
    ("↑/↓ or j/k", "move focus between cards"),
    ("tab", "cycle between columns"),
    ("enter", "open the focused card"),
    ("n", "new task in the focused column"),
    ("e", "edit the focused card"),
    ("d", "delete the focused card"),
    ("m", "enter move mode"),
    ("b", "switch board"),
    ("/", "filter cards as you type"),
    (":", "command bar (REPL syntax)"),
    ("s", "collapse or expand the sidebar"),
    ("c", "collapse or expand the cards"),
    ("r", "refresh from the filesystem"),
    ("?", "this help"),
    ("q / ctrl+q", "quit"),
]

MOVE_BINDINGS: list[tuple[str, str]] = [
    ("←/→ or h/l", "stage the card in the adjacent column"),
    ("↑/↓ or j/k", "stage the card higher or lower"),
    ("shift + any of those", "stage it as far as it will go that way"),
    ("shift + H/L/J/K", "the same, without reaching for the arrows"),
    ("enter", "commit the staged position"),
    ("esc", "cancel — nothing is written"),
]


class HelpScreen(ModalScreen[None]):
    """A bindings reference, pushed on `?`."""

    BINDINGS = [
        Binding("escape,q,question_mark", "dismiss_screen", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Lay out the normal-mode and move-mode binding tables."""
        with Vertical(id="dialog"):
            yield Static("Key bindings", id="form-heading")
            with VerticalScroll(id="help-body"):
                yield Static(_section("Board", NORMAL_BINDINGS))
                yield Static(_section("Move mode", MOVE_BINDINGS))

    def action_dismiss_screen(self) -> None:
        """Close the modal."""
        self.dismiss(None)


def _section(heading: str, bindings: list[tuple[str, str]]) -> Text:
    """Return a titled, aligned table of key/description pairs."""
    text = Text()
    text.append(f"{heading}\n", style="bold")

    width = max(len(key) for key, _ in bindings)
    for key, description in bindings:
        text.append(f"  {key.rjust(width)}  ", style="cyan")
        text.append(f"{description}\n")
    text.append("\n")
    return text
