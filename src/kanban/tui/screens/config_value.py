"""The value prompt, pushed from the configuration screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ..widgets import TextInput


class ConfigValueScreen(ModalScreen[str | None]):
    """
    Asks for the value of a single configuration key.

    Dismisses with the new value, or None when cancelled.  Writing it is left
    to the configuration screen, which is the one that talks to the kanban
    service; this one only collects the value.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
    ]

    def __init__(self, key: str, value: str | None = None) -> None:
        """Create a prompt for `key`, pre-filled with its current `value`."""
        super().__init__()
        self.key = key
        self.value = value

    def compose(self) -> ComposeResult:
        """Lay out the value field, headed by the key it belongs to."""
        with Vertical(id="dialog", classes="-narrow"):
            yield Static(f"Set {self.key}", id="form-heading")
            with VerticalScroll(id="form-fields"):
                yield Label("Value")
                yield TextInput(
                    value=self.value or "",
                    placeholder=self.key,
                    id="field-config-value",
                )
                yield Static("", id="form-error")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Put the cursor at the end of the value already held."""
        field = self.query_one("#field-config-value", Input)
        field.focus()
        field.action_end()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or cancel depending on which button was pressed."""
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter in the value field as a save."""
        _ = event
        self.action_save()

    def action_save(self) -> None:
        """Dismiss with the value, or show an error when it is empty."""
        value = self.query_one("#field-config-value", Input).value.strip()
        if not value:
            self.query_one("#form-error", Static).update("A value is required")
            return

        self.dismiss(value)

    def action_cancel(self) -> None:
        """Dismiss without changing anything."""
        self.dismiss(None)
