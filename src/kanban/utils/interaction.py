"""Questions put to a user sitting at the terminal."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile

from ..models import Task
from ..protocols.interaction import Interaction
from .shell import prompt_for_confirmation


class TerminalInteraction(Interaction):
    """
    The terminal's answer to a command that needs the user.

    What the CLI and the REPL use, and what the service falls back to when a
    consumer installs nothing of its own.  Both own the terminal for the length
    of a command, so both can prompt on it and wait for the answer.
    """

    def confirm(self, message: str, default: bool = False) -> bool:
        """Prompt for a yes or a no, and take the newline as `default`."""
        return prompt_for_confirmation(message, default)

    def edit(self, text: str, task: Task) -> str:
        """
        Open `text` in the user's editor and return what they saved.

        The text goes to a temporary file rather than to the task's own, so a
        failed edit leaves the store untouched; the caller writes the result
        back.  `$EDITOR` is preferred over `$VISUAL`, and `vi` stands in for
        both when neither is set.
        """
        _ = task

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                suffix=".md",
                prefix="kanban-task-",
                delete=False,
            ) as tmp:
                tmp.write(text)
                tmp.flush()
                tmp_path = tmp.name

            editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
            subprocess.run([*shlex.split(editor), tmp_path], check=True)

            with open(tmp_path, "r", encoding="utf-8") as f:
                return f.read()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass
