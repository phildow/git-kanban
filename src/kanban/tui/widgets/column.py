"""The column widget: a focusable header over a scrollable list of task cards."""

from __future__ import annotations

from typing import Any, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import ListItem, ListView

from ...models import Column, Slug, Task
from .card import CardWidget
from .column_header import ColumnHeader

# ListView inherits scrolling bindings from its container base class.  The board
# needs those keys for moving between columns and paging through cards, and a
# column that scrolls without moving the selection is not what they should do.
_SCROLL_ACTIONS = {
    "scroll_left",
    "scroll_right",
    "page_up",
    "page_down",
    "page_left",
    "page_right",
}

# Cursor actions the board takes over while a card is being staged in move mode.
_CURSOR_ACTIONS = {"cursor_up", "cursor_down", "select_cursor"}


class ColumnView(ListView):
    """
    A single board column.

    Holds a `Column` and the tasks currently displayed in it.  Like every other
    widget in the TUI, it renders what it is given and never queries the kanban
    service itself.  When `locked` is set the column releases its cursor keys so
    the board screen can drive them during move mode.
    """

    # ListView binds Enter without showing it.  The board's footer should name
    # the action, and the focused column is what the footer reads bindings from.
    BINDINGS = [
        Binding("enter", "select_cursor", "Open", show=True, key_display="↵"),
    ]

    locked: reactive[bool] = reactive(False)
    """
    Release cursor and select bindings to the board screen when True.

    Every column is locked during a move, so this says nothing about where the
    card would land — see `staging` for that.
    """

    staging: reactive[bool] = reactive(False)
    """True when this is the column the card being moved would land in."""

    def __init__(self, column: Column) -> None:
        """Create an empty view for `column`; call `set_tasks` to populate it."""
        super().__init__()
        self.column = column
        self._tasks: list[Task] = []

    @property
    def panel(self) -> ColumnPanel:
        """Return the column this list belongs to."""
        return cast("ColumnPanel", self.parent)

    @property
    def header(self) -> ColumnHeader:
        """Return the header above this list."""
        return self.panel.header

    @property
    def tasks(self) -> list[Task]:
        """Return the tasks currently displayed, in display order."""
        return list(self._tasks)

    @property
    def cards(self) -> list[CardWidget]:
        """Return the card widgets currently displayed, in display order."""
        return list(self.query(CardWidget))

    @property
    def selected_task(self) -> Task | None:
        """Return the highlighted task, or None when the column is empty."""
        index = self.index
        if index is None or not (0 <= index < len(self._tasks)):
            return None
        return self._tasks[index]

    async def set_tasks(
        self, tasks: list[Task], *, dense: bool = False, show_id: bool = False
    ) -> None:
        """Replace the column's contents with `tasks` and update the header count."""
        self._tasks = list(tasks)
        self.header.set_count(len(tasks))

        await self.clear()
        await self.extend(
            ListItem(CardWidget(task, dense=dense, show_id=show_id))
            for task in self._tasks
        )
        self.index = 0 if self._tasks else None

    def set_dense(self, dense: bool) -> None:
        """Propagate a density change to every card in the column."""
        for card in self.cards:
            card.dense = dense

    def set_show_id(self, show_id: bool) -> None:
        """Propagate a change of the `tui.task-id` setting to every card in the column."""
        for card in self.cards:
            card.show_id = show_id

    def card_for(self, slug: Slug) -> CardWidget | None:
        """Return the card displaying the task with `slug`, if it is in this column."""
        return next((card for card in self.cards if card.card_task.slug == slug), None)

    def select_task(self, slug: Slug) -> bool:
        """Highlight the task with `slug`.  Returns False when it is not in this column."""
        index = next(
            (i for i, task in enumerate(self._tasks) if task.slug == slug), None
        )
        if index is None:
            return False
        self.index = index
        return True

    # Walking up out of the cards and onto the header, disabled for now: the
    # board screen's `c` is what focuses the header, so ↑ stays inside the
    # column and stops at the top card, as it does in any other list.
    #
    # def action_cursor_up(self) -> None:
    #     """Move the cursor up, or onto the header once it is at the top card."""
    #     if self.index is None or self.index == 0:
    #         self.header.focus()
    #         return
    #     super().action_cursor_up()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """
        Disable the bindings the board screen needs to own.

        Horizontal scrolling is always released so left/right reach the board,
        and cursor movement is released while the column is locked for move
        mode.  A disabled binding is not matched, so the key bubbles up.
        """
        _ = parameters

        if action in _SCROLL_ACTIONS:
            return False
        if self.locked and action in _CURSOR_ACTIONS:
            return False
        return True

    def watch_staging(self, staging: bool) -> None:
        """
        Mark the column as the staged destination so it stands out during a move.

        The mark goes on the panel: the border and the header it colours belong
        to the column as a whole, not to the list of cards inside it.
        """
        if self.is_mounted:
            self.panel.set_class(staging, "-staging")

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        """
        Keep the scrollbar in step with the offset, even while it is hidden.

        The base watcher moves the scrollbar only when it is showing.  Emptying
        a column to repopulate it hides the scrollbar for a moment, and the
        offset is clamped to zero in that moment — so without this the thumb is
        left stranded wherever it was when the cards come back.
        """
        super().watch_scroll_y(old_value, new_value)
        self.vertical_scrollbar.position = new_value


class ColumnPanel(Vertical):
    """
    One board column: its header above the cards it holds.

    The panel carries the column's border and its focus colours, so the header
    and the cards read as one thing however focus moves between them.  It holds
    no state of its own — the header and the list each own theirs.
    """

    def __init__(
        self, column: Column, *, draft: bool = False, id: str | None = None
    ) -> None:
        """
        Create a panel for `column`.

        A `draft` panel stands in for a column that does not exist yet: its
        header opens a field to name it, and the board screen removes the panel
        again if no name arrives.
        """
        super().__init__(id=id)
        self.column = column
        self.draft = draft

    def compose(self) -> ComposeResult:
        """Lay out the header over the cards."""
        yield ColumnHeader(self.column, draft=self.draft)
        yield ColumnView(self.column)

    @property
    def header(self) -> ColumnHeader:
        """Return the column's header."""
        return self.query_one(ColumnHeader)

    @property
    def view(self) -> ColumnView:
        """Return the column's cards."""
        return self.query_one(ColumnView)

    def set_column(self, column: Column) -> None:
        """
        Hand the panel, and the two widgets in it, a new record of the column.

        Used when the column itself changed but its cards did not — a reorder,
        which moves the panel and renumbers it, and nothing else.
        """
        self.column = column
        self.header.set_column(column)
        self.view.column = column


def item_task(item: ListItem | Any) -> Task | None:
    """Return the task rendered by a list item, or None when it holds no card."""
    if not isinstance(item, ListItem):
        return None
    cards = list(item.query(CardWidget))
    return cards[0].card_task if cards else None
