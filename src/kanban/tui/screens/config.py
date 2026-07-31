"""The configuration modal, opened from the command palette."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static

from ...services.kanban import KanbanService
from ..formatting import config_label
from ..widgets import PrefixList, format_hints
from .config_value import ConfigValueScreen

# What the modal answers to, in the footer's own key/description form.
CONFIG_KEYS_HINTS: list[tuple[str, str]] = [
    ("↵", "Edit"),
    ("esc", "Close"),
]


class ConfigScreen(ModalScreen[None]):
    """
    Lists every supported configuration key with its value, and edits one on Enter.

    Reads and writes through the kanban service, as the sidebar does: settings
    are the app's own state rather than a board's, so there is no board screen
    to route them through.  The service is the authority on which keys exist —
    the list is whatever `list_config` reports, unset keys included.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=True),
    ]

    def __init__(self, svc: KanbanService) -> None:
        """Create a configuration screen backed by `svc`."""
        super().__init__()
        self.svc = svc
        self._values: dict[str, str | None] = {}

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Lay out the key list under a heading, with the modal's hints beneath it."""
        self._load()

        with Vertical(id="dialog", classes="-narrow"):
            yield Static("Configuration", id="form-heading")
            yield PrefixList(self._entries(), id="config-list")
            yield Static(format_hints(CONFIG_KEYS_HINTS), id="config-hint")

    def on_mount(self) -> None:
        """Take focus so the arrow keys and Enter reach the list."""
        self.query_one("#config-list", PrefixList).focus()

    def _load(self) -> None:
        """Re-read every configuration value from the service."""
        with self._service_errors("config"):
            self._values = self.svc.list_config()

    def _entries(self) -> list[tuple[str, Text]]:
        """Return the list's rows: each key paired with what it shows."""
        key_width = max((len(key) for key in self._values), default=0)
        return [
            (key, config_label(key, value, key_width))
            for key, value in self._values.items()
        ]

    # ── Editing ───────────────────────────────────────────────────────────────

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Ask for a new value for the key that was chosen."""
        keys = self.query_one("#config-list", PrefixList)
        key = keys.key_at(event.option_index)
        if key is None:
            return

        self.app.push_screen(
            ConfigValueScreen(key, self._values.get(key)),
            lambda value: self._set_value(key, value),
        )

    def _set_value(self, key: str, value: str | None) -> None:
        """Write the value the prompt came back with, then redraw the list."""
        if value is None:
            return

        with self._service_errors("config"):
            self.svc.set_config(key, value)

        self._load()
        self._refresh_list(key)

    def _refresh_list(self, key: str) -> None:
        """Rebuild the rows, staying on the key that was just edited."""
        keys = self.query_one("#config-list", PrefixList)
        keys.set_entries(self._entries())

        if key in keys.keys:
            keys.highlighted = keys.keys.index(key)

    def action_cancel(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    # ── Errors ────────────────────────────────────────────────────────────────

    @contextmanager
    def _service_errors(self, action: str) -> Iterator[None]:
        """Report a failed service call as a toast instead of tearing down the app."""
        try:
            yield
        except Exception as exc:
            description = str(exc) or exc.__class__.__name__
            logging.error("TUI %s failed: %s", action, description)
            self.notify(description, title=action, severity="error")
