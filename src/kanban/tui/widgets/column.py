"""The column widget: a scrollable, focusable list of task cards."""

from __future__ import annotations

from typing import Any

from textual.reactive import reactive
from textual.widgets import ListItem, ListView

from ...models import Column, Slug, Task
from ..formatting import column_title
from .card import CardWidget

# ListView inherits horizontal scroll bindings from its container base class,
# and the board needs left/right for moving between columns.
_SCROLL_ACTIONS = {"scroll_left", "scroll_right"}

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

    locked: reactive[bool] = reactive(False)
    """Release cursor and select bindings to the board screen when True."""

    def __init__(self, column: Column, *, id: str | None = None) -> None:
        """Create an empty view for `column`; call `set_tasks` to populate it."""
        super().__init__(id=id)
        self.column = column
        self._tasks: list[Task] = []
        self.border_title = column_title(column, 0)

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

    async def set_tasks(self, tasks: list[Task], *, dense: bool = False) -> None:
        """Replace the column's contents with `tasks` and update the header count."""
        self._tasks = list(tasks)
        self.border_title = column_title(self.column, len(tasks))

        await self.clear()
        await self.extend(
            ListItem(CardWidget(task, dense=dense)) for task in self._tasks
        )
        self.index = 0 if self._tasks else None

    def set_dense(self, dense: bool) -> None:
        """Propagate a density change to every card in the column."""
        for card in self.cards:
            card.dense = dense

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

    def watch_locked(self, locked: bool) -> None:
        """Reflect the locked state in CSS so move mode is visible on the column."""
        self.set_class(locked, "-locked")


def item_task(item: ListItem | Any) -> Task | None:
    """Return the task rendered by a list item, or None when it holds no card."""
    if not isinstance(item, ListItem):
        return None
    cards = list(item.query(CardWidget))
    return cards[0].card_task if cards else None
