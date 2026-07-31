"""The board switcher modal, pushed on `b`."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from ...models import Board, Slug
from ..formatting import board_label
from ..widgets import PrefixList
from .board_form import BoardFormScreen

NEW_BOARD_LABEL = "+ New board…"

# What typing jumps to the new-board row.  No board slug starts with it, so it
# never competes with a board for a typed prefix.
NEW_BOARD_KEY = "+"


@dataclass(frozen=True)
class SwitchToBoard:
    """The user picked an existing board."""

    slug: Slug


@dataclass(frozen=True)
class CreateBoard:
    """The user asked for a new board with this title."""

    name: str


BoardChoice = SwitchToBoard | CreateBoard
"""What the switcher came back with."""


class BoardSwitcherScreen(ModalScreen[BoardChoice | None]):
    """
    Lists the available boards, plus an option to create one.

    Arrow keys move through the boards and typing jumps to the one whose slug
    starts with what was typed, as the column prompt does.  Dismisses with the
    chosen board, a board to create, or None when cancelled.  Neither outcome
    touches the kanban service — the board screen acts on the choice.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, boards: list[Board], *, active: Slug | None = None) -> None:
        """Create a switcher over `boards`, highlighting `active` if it is present."""
        super().__init__()
        self.boards = boards
        self.active = active

    def compose(self) -> ComposeResult:
        """Lay out the board list, followed by the new-board option, under a heading."""
        # Widths come from the widest entry, so the rows line up as columns.
        name_width = max((len(board.name) for board in self.boards), default=0)
        path_width = max((len(board.slug) + 1 for board in self.boards), default=0)
        count_width = max(
            (len(str(board.task_count)) for board in self.boards), default=0
        )

        entries = [
            (str(board.slug), board_label(board, name_width, path_width, count_width))
            for board in self.boards
        ]
        entries.append((NEW_BOARD_KEY, Text(NEW_BOARD_LABEL)))

        # Full width rather than `-narrow`: rows carry a name, a path, and counts.
        with Vertical(id="dialog"):
            yield Static("Switch board", id="form-heading")
            yield PrefixList(entries, show_search=False, id="board-list")

    def on_mount(self) -> None:
        """Start on the active board, and take focus so the arrow keys work."""
        boards = self.query_one("#board-list", PrefixList)

        if self.active is not None and self.active in boards.keys:
            boards.highlighted = boards.keys.index(self.active)

        boards.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Switch to the selected board, or start creating a new one."""
        index = event.option_index

        if not (0 <= index <= len(self.boards)):
            self.dismiss(None)
            return

        if index == len(self.boards):
            self._prompt_for_new_board()
            return

        self.dismiss(SwitchToBoard(self.boards[index].slug))

    def action_cancel(self) -> None:
        """Dismiss without switching."""
        self.dismiss(None)

    def _prompt_for_new_board(self) -> None:
        """Ask for the new board's title, staying open if the prompt is cancelled."""
        self.app.push_screen(BoardFormScreen(), self._new_board_named)

    def _new_board_named(self, name: str | None) -> None:
        """Report the title back to the board screen, or stay put when cancelled."""
        if name is None:
            return
        self.dismiss(CreateBoard(name))
