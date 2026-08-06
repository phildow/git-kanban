"""The card widget: a single task rendered as a bordered box inside a column."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ...models import Task
from ..formatting import card_text


class CardWidget(Static):
    """
    One task, drawn as a bordered card.

    The widget owns a `Task` for display only; it never calls the kanban
    service.  Visual state is expressed with CSS classes rather than by
    redrawing: `-moving` marks the card staged in move mode, and `-dense`
    collapses it to a single summary line.
    """

    dense: reactive[bool] = reactive(False)
    """Collapse the card to a single line when True."""

    show_id: reactive[bool] = reactive(False)
    """Lead the card with the task's `#id` sigil when True, and it is not dense."""

    def __init__(
        self,
        task: Task,
        *,
        dense: bool = False,
        show_id: bool = False,
        id: str | None = None,
    ) -> None:
        """Create a card for `task`, optionally collapsed to dense mode."""
        super().__init__(id=id)
        self._card_task = task
        self.set_reactive(CardWidget.dense, dense)
        self.set_reactive(CardWidget.show_id, show_id)

    @property
    def card_task(self) -> Task:
        """
        Return the task this card displays.

        Named `card_task` rather than `task` because Textual's `MessagePump`
        already owns both `task` and `_task` for the widget's asyncio task.
        """
        return self._card_task

    def render(self) -> Text:
        """Return the card's body text for the current density."""
        return card_text(self.card_task, dense=self.dense, show_id=self.show_id)

    def set_task(self, task: Task) -> None:
        """
        Show `task` on this card, redrawing only when the record differs.

        A card outlives the refreshes that pass over its column, so this is how
        an edit reaches it.  The redraw asks for layout because the card is
        `height: auto` and the lines it draws vary with what the task carries.
        """
        if task == self._card_task:
            return
        self._card_task = task
        self.refresh(layout=True)

    def watch_dense(self, dense: bool) -> None:
        """Toggle the dense CSS class and redraw when the density changes."""
        self.set_class(dense, "-dense")
        self.refresh(layout=True)

    def watch_show_id(self, show_id: bool) -> None:
        """Redraw when the id is turned on or off, which can wrap the title onto a second line."""
        _ = show_id
        self.refresh(layout=True)

    def set_moving(self, moving: bool) -> None:
        """Mark or unmark this card as the one being staged in move mode."""
        self.set_class(moving, "-moving")
