"""The column header: a focusable strip that names a column and manages it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, Static

from ...models import Column
from ..formatting import column_title
from .text import TextInput

if TYPE_CHECKING:
    from .column import ColumnPanel


class HeaderRequest(Message):
    """
    Something a column header was asked to do, for the board screen to carry out.

    Headers render what they are handed and never call the kanban service, so
    every column-level action leaves the widget as one of these.
    """

    def __init__(self, header: ColumnHeader) -> None:
        """Record the header the request came from, and the column it names."""
        super().__init__()
        self.header = header
        self.column = header.column

    @property
    def control(self) -> ColumnHeader:
        """Return the header the request came from."""
        return self.header


class ColumnHeader(Vertical, can_focus=True):
    """
    The strip above a column's cards, naming it and counting what it holds.

    It is a focus target of its own, and the column-level actions hang off it:
    `r` renames the column, `d` deletes it, `n` starts a new one to its right,
    and alt + ←/→ move it through the board.  `c` and `esc` hand focus back
    to the cards below.

    A name is typed into a one-line field that replaces the label, so a column
    is renamed where its name is read.  A draft header — one standing in for a
    column that does not exist yet — opens the same field to name it, and is
    discarded if the name is cancelled.
    """

    BINDINGS = [
        Binding("r", "rename", "Rename", show=True),
        Binding("n", "new_column", "New", show=True),
        Binding("d", "delete", "Delete", show=True),
        # The header owns these rather than leaving them to the board's
        # jump-to-the-end bindings: a focused header is what alt + ←/→ moves.
        Binding("alt+left,alt+h", "reorder(-1)", "Reorder", show=True, key_display="⌥←/→"),
        Binding("alt+right,alt+l", "reorder(1)", "Reorder", show=False),
        # `c` is what reached the header from the cards, and it is what leaves
        # it again — the same key both ways, so it is the one hinted.
        Binding("c", "leave", "Cards", show=True),
        Binding("escape", "leave", "Cards", show=False),
    ]

    class NewRequested(HeaderRequest):
        """`n`: a column should be created to the right of this one."""

    class DeleteRequested(HeaderRequest):
        """`d`: this column should be deleted."""

    class ReorderRequested(HeaderRequest):
        """Alt + ←/→: this column should move `delta` places along the board."""

        def __init__(self, header: ColumnHeader, delta: int) -> None:
            """Record which way the column should move."""
            super().__init__(header)
            self.delta = delta

    class Named(HeaderRequest):
        """A name was submitted: a rename, or the name of a draft column."""

        def __init__(self, header: ColumnHeader, name: str) -> None:
            """Record the name that was typed."""
            super().__init__(header)
            self.name = name

    class NamingCancelled(HeaderRequest):
        """The field was closed without a name, so a draft header is spent."""

    class NamingChanged(HeaderRequest):
        """
        The field was opened or closed.

        The field claims every printable key while it is open, so the header's
        own keys are unreachable and the footer has nothing to say: this is what
        lets the board swap it for the field's hints and back.
        """

        def __init__(self, header: ColumnHeader, naming: bool) -> None:
            """Record whether the field is now open."""
            super().__init__(header)
            self.naming = naming

    def __init__(self, column: Column, *, draft: bool = False) -> None:
        """
        Create a header for `column`.

        A `draft` header stands in for a column that has not been created yet:
        it exists only to be named, and the board screen removes it if it is
        not.
        """
        super().__init__()
        self.column = column
        self.draft = draft
        self._count = 0

    def compose(self) -> ComposeResult:
        """Lay out the label and the field that replaces it while naming."""
        yield Static(column_title(self.column, self._count), classes="-title")
        yield TextInput(compact=True, classes="-name")

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def panel(self) -> ColumnPanel:
        """Return the column this header belongs to."""
        return cast("ColumnPanel", self.parent)

    @property
    def field(self) -> Input:
        """Return the field a name is typed into."""
        return self.query_one(".-name", Input)

    @property
    def naming(self) -> bool:
        """Return True while the field is open."""
        return self.has_class("-naming")

    def set_count(self, count: int) -> None:
        """Show `count` tasks in the label."""
        self._count = count
        self._draw_label()

    def set_column(self, column: Column) -> None:
        """Hand the header a new record of the column it names."""
        self.column = column
        self._draw_label()

    def _draw_label(self) -> None:
        """Redraw the label from the column and count currently held."""
        if self.is_mounted:
            self.query_one(".-title", Static).update(
                column_title(self.column, self._count)
            )

    # ── Naming ────────────────────────────────────────────────────────────────

    def begin_naming(self, value: str = "") -> None:
        """Open the field over the label, holding `value`."""
        field = self.field
        field.value = value
        self.add_class("-naming")
        field.focus()
        self.post_message(self.NamingChanged(self, True))

    def end_naming(self, *, focus: bool = True) -> None:
        """
        Close the field and take focus back from it.

        `focus` is False when the header must not be focused: because focus has
        already gone somewhere else, which must not be taken off the user, or
        because this header is about to be replaced or discarded.  Focusing is
        deferred by Textual, so a header that is gone by the time the deferred
        call runs would be left holding a focus nothing can take back — see
        `BoardScreen.focused_column`.
        """
        self.remove_class("-naming")
        if focus:
            self.focus()
        self.post_message(self.NamingChanged(self, False))

    def _cancel_naming(self, *, focus: bool) -> None:
        """Close the field with nothing submitted."""
        self.end_naming(focus=focus)
        self.post_message(self.NamingCancelled(self))

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        """
        Close the field when it loses focus with no name submitted.

        Clicking away is a way out of naming a column, the same as escape: a
        field left open would go on covering a header the user has walked away
        from, and a draft would stand there unnamed for good.
        """
        if self.is_mounted and self.naming and event.widget is self.field:
            self._cancel_naming(focus=False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """
        Report the name that was typed, or the cancellation of an empty one.

        Stopped here: the board screen reads `Input.Submitted` off its filter
        and command bars, and a name typed on a column is neither.
        """
        event.stop()

        name = event.value.strip()
        if name:
            self.post_message(self.Named(self, name))
        else:
            self.action_leave()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_rename(self) -> None:
        """Rename the column, in the field that replaces its label."""
        self.begin_naming(self.column.name)

    def action_new_column(self) -> None:
        """Ask for a column to the right of this one."""
        self.post_message(self.NewRequested(self))

    def action_delete(self) -> None:
        """Ask for this column to be deleted."""
        self.post_message(self.DeleteRequested(self))

    def action_reorder(self, delta: int) -> None:
        """Ask for this column to move `delta` places along the board."""
        self.post_message(self.ReorderRequested(self, delta))

    def action_focus_cards(self) -> None:
        """Hand focus to the cards below."""
        self.panel.view.focus()

    def action_leave(self) -> None:
        """Close the field if one is open, otherwise return focus to the cards."""
        if self.naming:
            # A draft header goes with the column it stands for, so it is not
            # given focus back; the board hands focus to a header that stays.
            self._cancel_naming(focus=not self.draft)
            return

        self.action_focus_cards()
