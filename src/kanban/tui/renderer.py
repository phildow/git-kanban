"""A renderer that captures command output instead of printing it."""

from __future__ import annotations

import argparse
from io import StringIO
from typing import Any

from rich.console import Console

from ..repl.rich_renderer import RichRenderer
from ..services.render_service import RenderService

# Wide enough that tables do not wrap awkwardly in the output modal.
CAPTURE_WIDTH = 100


class TUIRenderer(RichRenderer):
    """
    The REPL's renderer, redirected into a buffer.

    The TUI owns the terminal, so commands run from the command bar cannot
    print.  This renderer reuses every REPL rendering rule and only changes
    where the output goes; the board screen drains the buffer and shows it in a
    modal.
    """

    def __init__(self, render_service: RenderService) -> None:
        """Create a renderer that writes into an internal buffer."""
        super().__init__(render_service=render_service)
        self._buffer = StringIO()
        self.console = Console(file=self._buffer, width=CAPTURE_WIDTH, color_system=None)

    def _emit(self, args: argparse.Namespace, value: Any) -> None:
        """Write a renderable into the buffer rather than to the terminal."""
        if value is None:
            return
        self.console.print(value)

    def take_output(self) -> str:
        """Return everything rendered since the last call and reset the buffer."""
        output = self._buffer.getvalue()
        self._buffer.seek(0)
        self._buffer.truncate(0)
        return output
