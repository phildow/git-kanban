"""The task detail modal, pushed on Enter."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static

from ...models import Task
from ..formatting import detail_text


class TaskDetailScreen(ModalScreen[None]):
    """
    Renders a single task: metadata block followed by the markdown body.

    The body is the task's file content below the frontmatter, so the
    Description and Comments sections render as written on disk.
    """

    BINDINGS = [
        Binding("escape,q,enter", "dismiss_screen", "Close", show=True),
    ]

    def __init__(self, task: Task) -> None:
        """Create a detail screen for `task`."""
        super().__init__()
        # Named `detail_task` because Textual's MessagePump owns `task`.
        self.detail_task = task

    def compose(self) -> ComposeResult:
        """Lay out the metadata block above a scrollable rendering of the body."""
        with Vertical(id="dialog"):
            yield Static(detail_text(self.detail_task), id="task-detail-meta")
            with VerticalScroll(id="task-detail-body"):
                yield Markdown(self.detail_task.body or "*(no description)*")

    def action_dismiss_screen(self) -> None:
        """Close the modal."""
        self.dismiss(None)
