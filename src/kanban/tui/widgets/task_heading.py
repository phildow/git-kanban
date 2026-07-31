"""The heading that names a task on the screens that act on one."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ...models import Task


class TaskHeading(Vertical):
    """
    A task's title above its path.

    Viewing, editing, and deleting a task all lead with this, so a screen
    always says both which task the user means and which file it is.  Colour
    carries the distinction: the title takes the primary text colour and the
    path the secondary one.
    """

    def __init__(self, task: Task, *, id: str | None = None) -> None:
        """Create a heading for `task`."""
        super().__init__(id=id)
        # Named `heading_task` because Textual's MessagePump owns `task`.
        self.heading_task = task

    def compose(self) -> ComposeResult:
        """Lay out the title above the path, each on its own line."""
        yield Static(self.heading_task.title, classes="-task-title")
        yield Static(str(self.heading_task.path), classes="-task-path")
