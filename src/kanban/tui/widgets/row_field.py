"""A field laid over a row of an option list, so a row can be edited in place."""

from __future__ import annotations

from textual.widget import Widget
from textual.widgets import OptionList

from .text import TextInput

# What marks the field as open.  It is hidden otherwise, so the row beneath
# shows through and the field takes no room on the layer it sits on.
VISIBLE_CLASS = "-visible"


class RowField(TextInput):
    """
    A one-line field laid over the highlighted row of an option list.

    An `OptionList` draws its rows rather than mounting them, so a row cannot
    hold a field of its own.  This one lives on a layer above the list and is
    placed against the row it is editing, which reads as the row itself having
    become editable.

    It is placed rather than laid out, so it has to be a child of the container
    the offset is measured from — the dialog, in practice — and that container
    needs an `editor` layer for it to sit on.  Opening it takes the focus and
    closing it hands the focus back to the list.

    The field only collects what is typed: the screen that opened it decides
    what to do with `Input.Submitted`, and what an empty value means.
    """

    def __init__(self, rows: OptionList, *, id: str | None = None) -> None:
        """Create a field over the rows of `rows`, hidden until it is opened."""
        super().__init__(compact=True, id=id)
        self.rows = rows
        # How far into the row the field starts.  Held between opening and
        # placing, the two being a refresh apart.
        self._column = 0

    @property
    def is_open(self) -> bool:
        """Report whether the field is showing."""
        return self.has_class(VISIBLE_CLASS)

    def open(self, value: str = "", *, column: int = 0) -> None:
        """
        Show the field over the highlighted row, holding `value`.

        `column` is how far into the row the field starts, in cells: a row that
        shows a name and then a value passes the width of the name, which leaves
        the name legible while its value is edited.
        """
        self._column = column
        self.value = value
        self.add_class(VISIBLE_CLASS)

        # The list may still have to scroll the row into view, and the field is
        # placed against where the row ends up rather than where it is now.
        self.call_after_refresh(self.place)
        self.focus()

    def place(self) -> None:
        """Lay the field over the highlighted row, matching its position and width."""
        row = self.rows.highlighted
        parent = self.parent
        if row is None or not isinstance(parent, Widget):
            return

        # Both regions are in screen coordinates, and the offset is measured
        # from the container the field sits in — hence the difference.  Every
        # row is one line tall, so the row index is the line it is drawn on.
        region = self.rows.scrollable_content_region
        origin = parent.content_region

        self.styles.offset = (
            region.x - origin.x + self._column,
            region.y - origin.y + row - self.rows.scroll_offset.y,
        )
        self.styles.width = max(region.width - self._column, 1)

    def close(self) -> None:
        """Hide the field and hand the focus back to the list."""
        self.remove_class(VISIBLE_CLASS)
        self.rows.focus()
