"""The seam between a command that needs the user and the consumer running it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Task


class InteractionRequired(Exception):
    """
    Raised when a command needs the user and the consumer cannot ask them here.

    A consumer that owns the terminal — the CLI and the REPL — puts every
    question where it stands and never raises this.  One drawing a screen of
    its own cannot: its answer arrives from a modal, which needs the event loop
    the command is running on.  It raises instead, and the consumer asks in its
    own way and runs the command again.

    A command therefore abandons whatever it was doing at the point it asked,
    so everything before a question must be safe to abandon.  Confirmations
    already are: a read and a question, before anything has been written.
    """


class ConfirmationRequired(InteractionRequired):
    """A yes or no the consumer must put to the user itself."""

    def __init__(self, message: str) -> None:
        """Carry the question that was asked, for the consumer to ask again."""
        super().__init__(message)
        self.message = message


class EditRequired(InteractionRequired):
    """A task the consumer must open in an editor of its own."""

    def __init__(self, task: Task) -> None:
        """Carry the task that was to be edited, for the consumer to open."""
        super().__init__(f"{task.title} must be edited in the application")
        self.task = task


class Interaction(ABC):
    """
    How a command asks the user something.

    Injected into the `KanbanService` at startup, as every other service is, so
    that the consumer running a command decides how its questions are put: a
    prompt on the terminal, a modal over a board, or a refusal.  This is the
    only route to the user below the consumer layer — nothing under it reads
    from stdin or launches a program of its own.
    """

    @abstractmethod
    def confirm(self, message: str, default: bool = False) -> bool:
        """Put `message` as a yes/no question and return the answer."""

    @abstractmethod
    def edit(self, text: str, task: Task) -> str:
        """Return `text` as the user left it after editing `task`."""
