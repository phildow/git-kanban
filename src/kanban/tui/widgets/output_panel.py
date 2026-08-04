"""The panel that shows what a command run from the command bar printed."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

# The width the output panel guarantees its contents, whatever the terminal is.
# Commands are rendered at a fixed width and their tables assume the room; a
# narrower terminal scrolls sideways rather than folding the columns together.
MIN_OUTPUT_WIDTH = 80


class OutputPanel(VerticalScroll):
    """
    Command output, docked directly above the command bar.

    Commands run from the bar are rendered into a buffer rather than to the
    terminal, so their output has to be shown somewhere; it is shown here, in
    place, so the bar stays open and focused underneath and the user can run
    another command against what they just read.  It is a scroll of its own in
    both directions: long output scrolls rather than pushing the board away, and
    output wider than the terminal scrolls sideways rather than wrapping.

    It is a focus target of its own, reached with shift+tab from the bar, so
    output too long to fit can be read with the arrow and paging keys the
    scroll binds.
    """

    can_focus = True

    def __init__(self, *, id: str | None = None) -> None:
        """Create an empty, hidden panel; the board screen reveals it on demand."""
        super().__init__(id=id)
        self._body = Static("", markup=False, id="output-panel-body")

    def compose(self) -> ComposeResult:
        """Lay out the single static the output is written into."""
        yield self._body

    @property
    def text(self) -> str:
        """Return the output currently shown, empty when the panel is down."""
        return str(self._body.content)

    def show(self, command: str, output: str) -> None:
        """
        Display `output` and reveal the panel, titled by the `command` that produced it.

        The bar clears itself when a command is submitted, so the title is the
        only record on screen of what was run.  Output is written as plain text:
        it is rendered without colour and may hold anything a task title does,
        including square brackets that would otherwise read as markup.
        """
        self.border_title = f"> {command}"
        self._body.update(output)
        self.add_class("-visible")
        self.scroll_home(animate=False)

    def hide(self) -> None:
        """Clear the output and hide the panel."""
        self.border_title = ""
        self._body.update("")
        self.remove_class("-visible")
