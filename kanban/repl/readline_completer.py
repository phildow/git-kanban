"""Adapts :class:`CompletionEngine` to readline's completer protocol.

This is the only module that touches ``readline``. It exists so the
engine itself stays unit-testable with plain strings, no terminal
required.
"""

from __future__ import annotations

import readline

from repl.completion_engine import CompletionEngine


class ReplCompleter:
    """Readline-compatible completer backed by a :class:`CompletionEngine`.

    Args:
        engine: The pure completion engine to delegate to.
    """

    def __init__(self, engine: CompletionEngine) -> None:
        self._engine = engine
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

        Tab is bound to ``menu-complete`` rather than plain ``complete``
        so that repeated presses cycle through each match one at a
        time (wrapping back to the original text at the end), and
        ``show-all-if-ambiguous`` makes the very first ambiguous press
        display the full candidate list rather than requiring a second
        press to see it. Shift-Tab is bound to
        ``menu-complete-backward`` to cycle in reverse. This is GNU
        readline behavior; it relies on the Python ``readline`` module
        being linked against GNU readline rather than libedit (libedit
        is the macOS system default and does not support
        ``menu-complete`` the same way -- the ``gnureadline`` PyPI
        package is a drop-in replacement if that turns out to matter
        for your users).
        """

        readline.set_completer_delims(" \t\n/")
        readline.set_completer(self)
        readline.parse_and_bind("set show-all-if-ambiguous on")
        readline.parse_and_bind("set menu-complete-display-prefix on")
        readline.parse_and_bind("tab: menu-complete")
        readline.parse_and_bind('"\\e[1;2Z": menu-complete-backward')

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
            self._matches = self._engine.complete(line, cursor)
        if state < len(self._matches):
            return self._matches[state]
        return None