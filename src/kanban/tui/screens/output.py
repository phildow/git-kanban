"""A modal for showing the captured output of a command bar invocation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class OutputScreen(ModalScreen[None]):
    """
    Displays text produced by a command run from the command bar.

    Commands are rendered by a `CommandRenderer` that writes to a buffer rather
    than to the terminal, so their output has to be shown somewhere; this is it.
    """

    BINDINGS = [
        Binding("escape,q,enter", "dismiss_screen", "Close", show=True),
    ]

    def __init__(self, command: str, output: str) -> None:
        """Create a modal showing `output`, headed by the `command` that produced it."""
        super().__init__()
        self.command = command
        self.output = output

    def compose(self) -> ComposeResult:
        """Lay out the command line above its scrollable output."""
        with Vertical(id="dialog"):
            yield Static(f"> {self.command}", id="form-heading")
            with VerticalScroll(id="output-body"):
                yield Static(self.output or "(no output)")

    def action_dismiss_screen(self) -> None:
        """Close the modal."""
        self.dismiss(None)
