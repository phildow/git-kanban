"""The column widget: a focusable header over a scrollable list of task cards."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

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
        """
        Bring the column's cards into line with `tasks`, touching only what changed.

        The cards are reconciled against what is already mounted rather than
        rebuilt: a card whose task is unchanged is left alone, one whose task
        changed is handed the new record, one that changed places is moved, and
        only a task with no card of its own has one built for it.  A card that
        survives keeps its scroll position, its highlight, and its focus.

        Matched on `id` rather than slug, since a rename changes the slug and a
        renamed task is still the same card.
        """
        # Read off what is on screen before anything is handed the new list:
        # the highlight belongs to the task the column is showing at the index,
        # not to whichever task the new list happens to put there.
        held = self.selected_task
        held_id = held.id if held is not None else None

        desired = list(tasks)
        self._tasks = desired
        self.header.set_count(len(desired))

        drawn = self.cards
        items = {card.card_task.id: cast(ListItem, card.parent) for card in drawn}
        wanted = {task.id for task in desired}

        gone = [
            index
            for index, card in enumerate(drawn)
            if card.card_task.id not in wanted
        ]
        if gone:
            await self.remove_items(gone)

        for task in desired:
            item = items.get(task.id)
            if item is None:
                continue
            card = item.query_one(CardWidget)
            card.set_task(task)
            card.dense = dense
            card.show_id = show_id

        placed = await self._place_cards(desired, items, dense=dense, show_id=show_id)
        self._restore_highlight(desired, held_id)

        # Cards that changed places carry the region they had before the move
        # until the next layout, and `ListView.watch_index` scrolls to whatever
        # region it is shown — so a scroll it did here would land on where the
        # card was.  The one that counts is taken once the layout has caught up.
        if placed or gone:
            self.call_after_refresh(self._scroll_highlight_into_view)

    async def _place_cards(
        self,
        desired: list[Task],
        items: dict[UUID, ListItem],
        *,
        dense: bool,
        show_id: bool,
    ) -> bool:
        """
        Put every card at its place in `desired`, building the ones that are new.

        Walked front to back holding the invariant that the children up to the
        index reached are already the ones `desired` asks for, so a card that is
        out of place is always further back and can be moved before whichever
        card stands at the index now.  Cards that have to be built accumulate
        into a run and are mounted together, which is one mount for a column
        being filled from empty and one for the single card a create adds.

        Returns whether any card was built or moved, which is what says the
        column's layout — and so where a card is on screen — has changed.
        """
        pending: list[ListItem] = []
        start = 0
        placed = False

        for index, task in enumerate(desired):
            item = items.get(task.id)

            if item is None:
                if not pending:
                    start = index
                pending.append(
                    ListItem(CardWidget(task, dense=dense, show_id=show_id))
                )
                continue

            if pending:
                await self.mount(*pending, before=start)
                pending = []
                placed = True

            if self.children[index] is not item:
                self.move_child(item, before=index)
                placed = True

        if pending:
            await self.mount(*pending, before=start)
            placed = True

        return placed

    def _scroll_highlight_into_view(self) -> None:
        """
        Bring the highlighted card into view, against the layout as it now stands.

        Run after a refresh rather than during the reconcile, so the regions it
        reads are the ones the cards ended up with.
        """
        index = self.index
        if index is None or not (0 <= index < len(self.children)):
            return
        self.scroll_to_widget(self.children[index], animate=False)

    def _restore_highlight(self, desired: list[Task], held_id: UUID | None) -> None:
        """
        Leave the highlight on the task that held it, or on the card that took its place.

        A task still on the column keeps the highlight wherever it has ended up.
        One that left the column leaves it where `remove_items` put it, which is
        the card that closed the gap — the neighbour the board expects.

        The flags are squared up whether or not the index moved: a card can
        change places under an index that does not change, and then the flag is
        on the wrong card.
        """
        if not desired:
            self.index = None
            return

        position = next(
            (index for index, task in enumerate(desired) if task.id == held_id), None
        )
        if position is None:
            position = self.index if self.index is not None else 0

        if self.index != position:
            self.index = position

        for index, item in enumerate(self.children):
            cast(ListItem, item).highlighted = index == position

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

        The base watcher moves the scrollbar only when it is showing.  A column
        that loses enough cards to stop scrolling hides the scrollbar, and the
        offset is clamped to zero in that moment — so without this the thumb is
        left stranded wherever it was should the cards come back.
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
