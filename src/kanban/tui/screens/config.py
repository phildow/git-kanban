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
from ..formatting import config_group_label, config_label
from ..widgets import PrefixList, format_hints
from .config_value import ConfigValueScreen


def _section_of(keypath: str) -> str:
    """Return the group a keypath belongs to: everything before its first dot."""
    section, _, _ = keypath.partition(".")
    return section


def _name_of(keypath: str) -> str:
    """Return a keypath's name within its section: everything after the first dot."""
    _, _, name = keypath.partition(".")
    return name or keypath

# What the modal answers to, in the footer's own key/description form.
CONFIG_KEYS_HINTS: list[tuple[str, str]] = [
    ("↵ e", "Edit"),
    ("esc", "Close"),
]

# `e` edits, as it does on the board.  The list is told not to take it for its
# own type-ahead, which is what leaves it free to reach this screen.
EDIT_KEY = "e"


class ConfigScreen(ModalScreen[None]):
    """
    Lists every supported configuration key with its value, and edits one on Enter.

    Reads and writes through the kanban service, as the sidebar does: settings
    are the app's own state rather than a board's, so there is no board screen
    to route them through.  The service is the authority on which keys exist —
    the list is whatever `list_config` reports, unset keys included.
    """

    BINDINGS = [
        Binding(EDIT_KEY, "edit", "Edit", show=True),
        Binding("escape", "cancel", "Close", show=True),
    ]

    def __init__(self, svc: KanbanService) -> None:
        """Create a configuration screen backed by `svc`."""
        super().__init__()
        self.svc = svc
        self._values: dict[str, str | None] = {}
        # The keypath each row stands for, headings included as None, so a
        # chosen row names the setting it belongs to.  The rows themselves show
        # only the name within the section, which is all the list needs to say
        # once the section heading is above it.
        self._keypaths: list[str | None] = []

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Lay out the key list under a heading, with the modal's hints beneath it."""
        self._load()

        with Vertical(id="dialog", classes="-narrow"):
            yield Static("Configuration", id="form-heading")
            yield PrefixList(self._entries(), reserved=[EDIT_KEY], id="config-list")
            yield Static(format_hints(CONFIG_KEYS_HINTS), id="config-hint")

    def on_mount(self) -> None:
        """Start on the first setting, below its heading, and take focus."""
        keys = self.query_one("#config-list", PrefixList)

        first = keys.first_key_index
        if first is not None:
            keys.highlighted = first

        keys.focus()

    def _load(self) -> None:
        """Re-read every configuration value from the service."""
        with self._service_errors("config"):
            self._values = self.svc.list_config()

    def _entries(self) -> list[tuple[str | None, Text]]:
        """
        Return the list's rows, grouped by section.

        A keypath is `section.name`, so the sections are the groups — the same
        ones the config file has as its `[section]` headings.  Each group is
        headed by its section and followed by that section's settings, both in
        name order.
        """
        groups: dict[str, list[str]] = {}
        for keypath in self._values:
            groups.setdefault(_section_of(keypath), []).append(keypath)

        name_width = max((len(_name_of(key)) for key in self._values), default=0)

        rows: list[tuple[str | None, Text]] = []
        self._keypaths = []

        for section in sorted(groups):
            rows.append((None, config_group_label(section)))
            self._keypaths.append(None)

            for keypath in sorted(groups[section]):
                name = _name_of(keypath)
                rows.append((name, config_label(name, self._values[keypath], name_width)))
                self._keypaths.append(keypath)

        return rows

    # ── Editing ───────────────────────────────────────────────────────────────

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Ask for a new value for the key that was chosen."""
        self._edit(self._keypath_at(event.option_index))

    def action_edit(self) -> None:
        """Edit the highlighted setting, as Enter does."""
        self._edit(self._keypath_at(self.query_one("#config-list", PrefixList).highlighted))

    def _edit(self, key: str | None) -> None:
        """Open the value prompt for `key`, or do nothing when there is no setting."""
        if key is None:
            return

        self.app.push_screen(
            ConfigValueScreen(key, self._values.get(key)),
            lambda value: self._set_value(key, value),
        )

    def _keypath_at(self, index: int | None) -> str | None:
        """Return the keypath the row at `index` stands for, or None for a heading."""
        if index is None or not (0 <= index < len(self._keypaths)):
            return None
        return self._keypaths[index]

    def row_for(self, keypath: str) -> int | None:
        """Return the row `keypath` is listed at, or None when it is not listed."""
        if keypath not in self._keypaths:
            return None
        return self._keypaths.index(keypath)

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

        row = self.row_for(key)
        if row is not None:
            keys.highlighted = row

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
