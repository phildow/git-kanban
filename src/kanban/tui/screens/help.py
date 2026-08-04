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
    ("c", "focus this column's header"),
    ("shift + any of those", "jump to the end of the column or board"),
    ("page up/down", "page through the cards in a column"),
    ("ctrl + page up/down", "page across the columns"),
    ("tab", "step through the columns"),
    ("enter or v", "view the focused card"),
    ("n", "new task in the focused column"),
    ("e", "edit the focused card"),
    ("d", "delete the focused card"),
    ("m", "enter move mode"),
    ("a", "archive the focused card, or bring it back"),
    ("A", "show or hide the archive column"),
    ("b", "switch or manage boards"),
    ("/", "command bar (REPL syntax)"),
    (":", "filter cards as you type — text or flags"),
    ("tab", "tab complete in filter and command bar"),
    ("↑/↓ in a bar", "cycle what has been typed there before"),
    ("s", "collapse or expand the sidebar"),
    ("x", "collapse or expand the cards"),
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

HEADER_BINDINGS: list[tuple[str, str]] = [
    ("r", "rename this column, on its header"),
    ("n", "new column, named to the right of this one"),
    ("d", "delete this column (confirm first)"),
    ("shift + ←/→", "move this column along the board"),
    ("←/→ or h/l", "move along the header strip"),
    ("↓ or j, esc", "return to the cards below"),
    ("tab", "on to the next column's header"),
    ("the board's keys", "inactive — a header answers to columns only"),
]

DETAIL_BINDINGS: list[tuple[str, str]] = [
    ("←/→ or h/l", "show the card selected in the adjacent column"),
    ("↑/↓ or j/k", "show the next or previous card in this column"),
    ("shift + any of those", "scroll the description and comments"),
    ("page up/down", "scroll the description and comments"),
    ("e", "edit the task shown"),
    ("q, esc, enter", "close"),
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


SECTIONS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Board", NORMAL_BINDINGS),
    ("Column header (c)", HEADER_BINDINGS),
    ("Task detail (enter)", DETAIL_BINDINGS),
    ("Move mode", MOVE_BINDINGS),
    ("Boards (b)", BOARD_BINDINGS),
]


class HelpScreen(ModalScreen[None]):
    """A bindings reference, pushed on `?`."""

    BINDINGS = [
        Binding("escape,q,question_mark", "dismiss_screen", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Lay out the board, column header, task detail, move-mode, and board-switcher tables."""
        width = _key_width(SECTIONS)
        with Vertical(id="dialog"):
            yield Static("Key bindings", id="form-heading")
            with VerticalScroll(id="help-body"):
                for heading, bindings in SECTIONS:
                    yield Static(_section(heading, bindings, width))

    def action_dismiss_screen(self) -> None:
        """Close the modal."""
        self.dismiss(None)


def _key_width(sections: list[tuple[str, list[tuple[str, str]]]]) -> int:
    """Return the width the longest key needs, so every section aligns to the same column."""
    return max(len(key) for _, bindings in sections for key, _ in bindings)


def _section(heading: str, bindings: list[tuple[str, str]], width: int) -> Text:
    """Return a titled table of key/description pairs, keys right justified to `width`."""
    text = Text()
    text.append(f"{heading}\n", style="bold")

    for key, description in bindings:
        text.append(f"  {key.rjust(width)}  ", style="cyan")
        text.append(f"{description}\n")
    text.append("\n")
    return text
