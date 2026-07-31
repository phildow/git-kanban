"""The column prompt, pushed from move mode to pick a destination."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from ...models import Column, Slug
from ..formatting import column_label
from ..widgets import PrefixList


class ColumnPromptScreen(ModalScreen[Slug | None]):
    """
    Asks which column to move a card to.

    The board's columns are listed: arrow keys move through them and typing
    jumps to the one whose slug starts with what was typed.  Dismisses with the
    chosen slug, or None when cancelled — the board screen performs the move,
    as it does for every other way of choosing a destination.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, columns: list[Column], *, current: Slug | None = None) -> None:
        """Create a prompt over `columns`, starting on the `current` one."""
        super().__init__()
        self.columns = columns
        self.current = current

    def compose(self) -> ComposeResult:
        """Lay out the column list under a heading."""
        slug_width = max((len(column.slug) for column in self.columns), default=0)
        entries = [
            (column.slug, column_label(column, slug_width)) for column in self.columns
        ]

        with Vertical(id="dialog", classes="-narrow"):
            yield Static("Move to column", id="form-heading")
            yield PrefixList(entries, id="column-list")

    def on_mount(self) -> None:
        """Start on the column the card is already staged in, and take focus."""
        columns = self.query_one("#column-list", PrefixList)

        if self.current is not None and self.current in columns.keys:
            columns.highlighted = columns.keys.index(self.current)

        columns.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Dismiss with the column that was chosen."""
        columns = self.query_one("#column-list", PrefixList)
        slug = columns.key_at(event.option_index)

        self.dismiss(Slug(slug) if slug is not None else None)

    def action_cancel(self) -> None:
        """Dismiss without choosing."""
        self.dismiss(None)
