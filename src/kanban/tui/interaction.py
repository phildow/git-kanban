"""The TUI's answer to a command that needs the user: ask again, on screen."""

from __future__ import annotations

from ..models import Task
from ..protocols.interaction import (
    ConfirmationRequired,
    EditRequired,
    Interaction,
)


class DeferredInteraction(Interaction):
    """
    Questions the TUI cannot answer where they are asked, and defers.

    A command run from the command bar runs on the event loop, so a modal put
    up in the middle of one could never be answered: the loop that would draw
    it and take the keypress is the loop the command is holding.  Every
    question is therefore refused by raising, leaving the board to put it up
    when the command has finished unwinding.

    A confirmation the board has already had answered is granted before the
    command is run again, and answered where it is asked the second time.  The
    grant names the question it answers, so a command that goes on to ask
    something else asks it rather than having it answered on the user's behalf.
    """

    def __init__(self) -> None:
        """Create an interaction with nothing granted."""
        self.granted: str | None = None

    def confirm(self, message: str, default: bool = False) -> bool:
        """Answer `message` when it is the question the board granted, or raise."""
        _ = default

        if self.granted is not None and self.granted == message:
            return True
        raise ConfirmationRequired(message)

    def edit(self, text: str, task: Task) -> str:
        """Refuse to edit `task` here, naming it for the board to open."""
        _ = text
        raise EditRequired(task)
