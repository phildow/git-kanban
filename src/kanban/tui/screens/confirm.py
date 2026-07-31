"""A generic yes/no confirmation modal."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ...models import Task
from ..formatting import metadata_text
from ..widgets import TaskHeading


class ConfirmScreen(ModalScreen[bool]):
    """Asks the user to confirm a destructive action.  Dismisses with True or False."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("y", "confirm", "Confirm", show=True),
        Binding("n", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self,
        prompt: str | Text,
        *,
        task: Task | None = None,
        confirm_label: str = "Delete",
    ) -> None:
        """
        Create a confirmation modal showing `prompt` above the buttons.

        `prompt` may be styled text.  Pass `task` when the question is about one
        task, and its title, path, and metadata are shown beneath the question
        so the user can see exactly what is about to go.
        """
        super().__init__()
        self.prompt = prompt
        self.confirm_task = task
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        """
        Lay out the prompt, the task it concerns, and the confirm/cancel buttons.

        The task is described the way the detail screen describes it, minus the
        body: a confirmation should show what is at stake at a glance, and the
        description and comments are too long for that.
        """
        with Vertical(id="dialog", classes="-narrow"):
            yield Static(self.prompt, id="confirm-prompt")
            if self.confirm_task is not None:
                yield TaskHeading(self.confirm_task)
                yield Static(metadata_text(self.confirm_task), classes="-task-meta")
            with Horizontal(id="dialog-buttons"):
                yield Button(self.confirm_label, variant="error", id="confirm")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss with the answer the pressed button represents."""
        self.dismiss(event.button.id == "confirm")

    def action_confirm(self) -> None:
        """Dismiss with True."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Dismiss with False."""
        self.dismiss(False)
