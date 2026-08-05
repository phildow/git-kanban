"""Interface for anything that can complete a partly typed input line."""

from __future__ import annotations

from typing import Protocol


class Completer(Protocol):
    """
    Supplies tab-completion candidates for an input line.

    The REPL's `CompletionEngine` satisfies this, which is how the TUI's input
    bars complete the same commands, flags, and names the REPL does.
    """

    def complete(self, line: str, cursor: int) -> list[str]:
        """Return candidates for the token at `cursor`, each a full replacement."""
        ...

    def partial_at(self, line: str, cursor: int) -> str:
        """Return the fragment at `cursor` that a candidate replaces.

        Not always the whole token: a candidate for a path completes one
        segment of it, so the fragment stops at the last `/`.
        """
        ...
