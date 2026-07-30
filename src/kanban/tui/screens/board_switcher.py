"""The board switcher modal, pushed on `b`."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ...models import Board, Slug
from ..formatting import board_label
from .board_form import BoardFormScreen

NEW_BOARD_LABEL = "+ New board…"


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

    Dismisses with the chosen board, a board to create, or None when cancelled.
    Neither outcome touches the kanban service — the board screen acts on the
    choice.
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
        initial = next(
            (i for i, board in enumerate(self.boards) if board.slug == self.active), 0
        )

        # Widths come from the widest entry, so the rows line up as columns.
        name_width = max((len(board.name) for board in self.boards), default=0)
        path_width = max((len(board.slug) + 1 for board in self.boards), default=0)
        count_width = max(
            (len(str(board.task_count)) for board in self.boards), default=0
        )

        rows = [
            ListItem(
                Label(board_label(board, name_width, path_width, count_width)),
                id=f"board-{board.slug}",
            )
            for board in self.boards
        ]
        rows.append(ListItem(Label(NEW_BOARD_LABEL), id="new-board-option"))

        # Full width rather than `-narrow`: rows carry a name, a path, and counts.
        with Vertical(id="dialog"):
            yield Static("Switch board", id="form-heading")
            yield ListView(*rows, initial_index=initial, id="board-list")

    def on_mount(self) -> None:
        """Focus the list so the arrow keys work immediately."""
        for view in self.query(ListView):
            view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Switch to the selected board, or start creating a new one."""
        index = event.list_view.index

        if index is None or not (0 <= index <= len(self.boards)):
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
