"""Adapts :class:`CompletionEngine` to readline's completer protocol.

This is the only module that touches ``readline``. It exists so the
engine itself stays unit-testable with plain strings, no terminal
required.
"""

from __future__ import annotations

import readline
from typing import Callable

from repl.completion_engine import CompletionEngine, UserContextLike


class ReplCompleter:
    """Readline-compatible completer backed by a :class:`CompletionEngine`.

    Args:
        engine: The pure completion engine to delegate to.
        get_context: Called on each completion attempt to fetch the
            REPL's *current* active board/column, since context can
            change between commands (e.g. after ``cd``).
    """

    def __init__(
        self,
        engine: CompletionEngine,
        get_context: Callable[[], UserContextLike],
    ) -> None:
        self._engine = engine
        self._get_context = get_context
        self._matches: list[str] = []

    def install(self) -> None:
        """Register this completer with readline for the REPL session.

        ``/`` is included as a word-break character alongside
        whitespace, matching standard shell path-completion behavior:
        readline computes the replaceable span as everything since the
        last ``/`` (or whitespace), so it only ever touches the final
        path segment. Combined with CompletionEngine returning bare
        segment names, this is what makes completion show plain names
        like "in-progress" while the resulting line still reads as the
        full path the person already typed plus that name.
        """

        readline.set_completer_delims(" \t\n/")
        readline.set_completer(self)
        readline.parse_and_bind("tab: complete")

    def __call__(self, text: str, state: int) -> str | None:
        """Readline's completer protocol: called repeatedly with state=0,1,2,...

        Args:
            text: The current token per readline's word-break rules
                (unused directly; we re-derive it from the line buffer
                so segmentation logic lives in one place).
            state: Which match to return, starting at 0.

        Returns:
            The match at ``state``, or ``None`` once exhausted.
        """

        if state == 0:
            line = readline.get_line_buffer()
            cursor = readline.get_endidx()
            self._matches = self._engine.complete(line, cursor, self._get_context())
        if state < len(self._matches):
            return self._matches[state]
        return None
