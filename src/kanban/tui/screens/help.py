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
    ("shift + any of those", "jump to the end of the column or board"),
    ("page up/down", "page through the cards in a column"),
    ("ctrl + page up/down", "page across the columns"),
    ("tab", "cycle between columns"),
    ("enter or v", "view the focused card"),
    ("n", "new task in the focused column"),
    ("e", "edit the focused card"),
    ("d", "delete the focused card"),
    ("m", "enter move mode"),
    ("b", "switch or manage boards"),
    ("/", "command bar (REPL syntax)"),
    (":", "filter cards as you type — text or flags"),
    ("tab", "tab complete in filter and command bar"),
    ("s", "collapse or expand the sidebar"),
    ("c", "collapse or expand the cards"),
    ("r", "refresh from the filesystem"),
    ("ctrl+p", "command palette — app actions and config"),
    ("?", "this help"),
    ("q / ctrl+q", "quit"),
]

BOARD_BINDINGS: list[tuple[str, str]] = [
    ("↑/↓", "move through the boards"),
    ("any letter", "jump to the board whose slug starts with it"),
    ("enter", "switch to the highlighted board"),
    ("N", "new board — named on a row of its own"),
    ("R", "rename the highlighted board, on its row"),
    ("D", "delete the highlighted board (confirm first)"),
    ("esc", "close, or cancel the name being typed"),
]

MOVE_BINDINGS: list[tuple[str, str]] = [
    ("←/→ or h/l", "stage the card in the adjacent column"),
    ("↑/↓ or j/k", "stage the card higher or lower"),
    ("shift + any of those", "stage it as far as it will go that way"),
    ("shift + H/L/J/K", "the same, without reaching for the arrows"),
    ("page up/down", "stage it a screenful at a time"),
    ("tab", "choose the column by name"),
    ("enter", "commit the staged position"),
    ("esc", "cancel — nothing is written"),
]


class HelpScreen(ModalScreen[None]):
    """A bindings reference, pushed on `?`."""

    BINDINGS = [
        Binding("escape,q,question_mark", "dismiss_screen", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Lay out the normal-mode, move-mode, and board-switcher binding tables."""
        with Vertical(id="dialog"):
            yield Static("Key bindings", id="form-heading")
            with VerticalScroll(id="help-body"):
                yield Static(_section("Board", NORMAL_BINDINGS))
                yield Static(_section("Move mode", MOVE_BINDINGS))
                yield Static(_section("Boards (b)", BOARD_BINDINGS))

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
