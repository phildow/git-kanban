"""Text fields that move by word on option/alt + arrow."""

from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Input, TextArea

# Textual binds word motion to ctrl + arrows.  The habit on macOS is option +
# arrows, which terminals report as `alt`; `alt+b`/`alt+f` cover the ones
# configured to send Option as Meta, where they are the readline equivalents.
WORD_LEFT = "alt+left,alt+b"
WORD_RIGHT = "alt+right,alt+f"

# Command + arrows are not bound: macOS terminals keep Command for their own
# shortcuts and never forward it, so the key never reaches the app.  Textual's
# own `home,ctrl+a` and `end,ctrl+e` already reach the ends of a line.


class TextInput(Input):
    """A single-line field where option/alt + ← → move by word."""

    BINDINGS = [
        Binding(WORD_LEFT, "cursor_left_word", "Word left", show=False),
        Binding(WORD_RIGHT, "cursor_right_word", "Word right", show=False),
    ]


class MarkdownArea(TextArea):
    """
    A multi-line markdown field with the same word motion.

    `TextArea` names its word actions the other way round from `Input`, hence
    the different action names for the same keys.
    """

    BINDINGS = [
        Binding(WORD_LEFT, "cursor_word_left", "Word left", show=False),
        Binding(WORD_RIGHT, "cursor_word_right", "Word right", show=False),
    ]

    def __init__(self, text: str = "", *, id: str | None = None) -> None:
        """Create an editor over `text`, holding markdown source."""
        super().__init__(text, language="markdown", soft_wrap=True, id=id)
