"""The board switcher modal, pushed on `b`."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static

from ...models import Board, Slug


class BoardSwitcherScreen(ModalScreen[Slug | None]):
    """Lists the available boards.  Dismisses with the chosen board's slug, or None."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, boards: list[Board], *, active: Slug | None = None) -> None:
        """Create a switcher over `boards`, highlighting `active` if it is present."""
        super().__init__()
        self.boards = boards
        self.active = active

    def compose(self) -> ComposeResult:
        """Lay out the board list under a heading."""
        initial = next(
            (i for i, board in enumerate(self.boards) if board.slug == self.active), 0
        )

        with Vertical(id="dialog", classes="-narrow"):
            yield Static("Switch board", id="form-heading")
            if not self.boards:
                yield Static("No boards yet", classes="-empty")
            else:
                yield ListView(
                    *[
                        ListItem(Label(_board_label(board)), id=f"board-{board.slug}")
                        for board in self.boards
                    ],
                    initial_index=initial,
                    id="board-list",
                )

    def on_mount(self) -> None:
        """Focus the list so the arrow keys work immediately."""
        for view in self.query(ListView):
            view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Dismiss with the slug of the selected board."""
        index = event.list_view.index
        if index is None or not (0 <= index < len(self.boards)):
            self.dismiss(None)
            return
        self.dismiss(self.boards[index].slug)

    def action_cancel(self) -> None:
        """Dismiss without switching."""
        self.dismiss(None)


def _board_label(board: Board) -> str:
    """Return the switcher row for a board: its path and its counts."""
    return f"/{board.slug}  ({board.column_count} columns, {board.task_count} tasks)"
