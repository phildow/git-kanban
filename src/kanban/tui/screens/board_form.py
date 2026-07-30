"""The new-board prompt, pushed from the board switcher."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class BoardFormScreen(ModalScreen[str | None]):
    """
    Asks for a new board's title.

    Dismisses with the title, or None when cancelled.  Creating the board is
    left to the board screen, which is the only screen that talks to the kanban
    service; this one only collects the name.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
    ]

    def compose(self) -> ComposeResult:
        """Lay out the title field above the button row."""
        with Vertical(id="dialog", classes="-narrow"):
            yield Static("New board", id="form-heading")
            with VerticalScroll(id="form-fields"):
                yield Label("Title")
                yield Input(placeholder="board title", id="field-board-title")
                yield Static("", id="form-error")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Put the cursor in the title field."""
        self.query_one("#field-board-title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or cancel depending on which button was pressed."""
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter in the title field as a save."""
        _ = event
        self.action_save()

    def action_save(self) -> None:
        """Dismiss with the title, or show an error when it is empty."""
        title = self.query_one("#field-board-title", Input).value.strip()
        if not title:
            self.query_one("#form-error", Static).update("A title is required")
            return

        self.dismiss(title)

    def action_cancel(self) -> None:
        """Dismiss without creating anything."""
        self.dismiss(None)
