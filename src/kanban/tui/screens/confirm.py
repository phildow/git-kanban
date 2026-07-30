"""A generic yes/no confirmation modal."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """Asks the user to confirm a destructive action.  Dismisses with True or False."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("y", "confirm", "Confirm", show=True),
        Binding("n", "cancel", "Cancel", show=False),
    ]

    def __init__(self, prompt: str, *, confirm_label: str = "Delete") -> None:
        """Create a confirmation modal showing `prompt` above the buttons."""
        super().__init__()
        self.prompt = prompt
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        """Lay out the prompt and the confirm/cancel buttons."""
        with Vertical(id="dialog", classes="-narrow"):
            yield Static(self.prompt, id="confirm-prompt")
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
