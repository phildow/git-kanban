"""The configuration modal, opened from the command palette."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static

from ...models.config import CONFIG_VALUES
from ...services.kanban import KanbanService
from ..formatting import (
    FREE_TEXT_VALUES,
    config_group_label,
    config_label,
    config_value_column,
    config_values_hint,
)
from ..widgets import PrefixList, RowField


def _section_of(keypath: str) -> str:
    """Return the group a keypath belongs to: everything before its first dot."""
    section, _, _ = keypath.partition(".")
    return section


def _name_of(keypath: str) -> str:
    """Return a keypath's name within its section: everything after the first dot."""
    _, _, name = keypath.partition(".")
    return name or keypath

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

    Editing happens on the row, never in a dialog of its own.  A key drawn from
    a fixed set has nothing to type, so Enter steps it to the next value it
    permits; anything else is typed into a `RowField` laid over the row's value,
    leaving its name legible beside what is being typed.

    An edited value is staged rather than written: the list shows it, marked as
    pending, and nothing reaches the service until the screen is saved.  Cancel
    discards the lot, so a user who opens a setting to see what it says can back
    out of every field they touched on the way.

    The line under the list says what the setting in focus will take, following
    the highlight down the list.  The keys the screen answers to are not spelt
    out there: Save and Cancel are on the buttons, and what a setting accepts is
    the thing the user cannot work out by looking — and, for a key that cycles,
    what the next Enter will land on.
    """

    BINDINGS = [
        Binding(EDIT_KEY, "edit", "Edit", show=True),
        # Save from the list as well as from the buttons.  Plain Enter cannot:
        # on the list it opens the highlighted setting, which is what it should
        # do there.
        Binding("shift+enter", "save", "Save", show=True),
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, svc: KanbanService) -> None:
        """Create a configuration screen backed by `svc`."""
        super().__init__()
        self.svc = svc
        self._values: dict[str, str | None] = {}
        # Values edited but not yet written.  They take the place of the stored
        # value everywhere the screen shows or offers one, and are handed to the
        # service only on save.
        self._staged: dict[str, str] = {}
        # The keypath each row stands for, headings included as None, so a
        # chosen row names the setting it belongs to.  The rows themselves show
        # only the name within the section, which is all the list needs to say
        # once the section heading is above it.
        self._keypaths: list[str | None] = []
        # What the rows reserve for their names, which is where the value the
        # field edits begins.
        self._name_width = 0
        # The keypath the open field is editing, and None when it is closed.
        self._editing: str | None = None

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Lay out the key list under a heading, with the values line and buttons below."""
        self._load()

        with Vertical(id="dialog", classes="-narrow"):
            yield Static("Configuration", id="form-heading")
            rows = PrefixList(self._entries(), reserved=[EDIT_KEY], id="config-list")
            yield rows
            yield Static("", id="config-hint")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")
            yield RowField(rows, id="config-value")

    def on_mount(self) -> None:
        """Start on the first setting, below its heading, and take focus."""
        keys = self.rows

        first = keys.first_key_index
        if first is not None:
            keys.highlighted = first

        keys.focus()
        self._show_values(keys.highlighted)

    @property
    def rows(self) -> PrefixList:
        """Return the list of settings."""
        return self.query_one("#config-list", PrefixList)

    @property
    def field(self) -> RowField:
        """Return the field a value is typed into."""
        return self.query_one("#config-value", RowField)

    # ── The values line ───────────────────────────────────────────────────────

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        """Follow the highlight with what the setting it landed on will take."""
        self._show_values(event.option_index)

    def _show_values(self, index: int | None) -> None:
        """Say what the setting at `index` accepts, or nothing for a heading."""
        self.query_one("#config-hint", Static).update(
            self._values_line(self._keypath_at(index))
        )

    def _values_line(self, keypath: str | None) -> str:
        """
        Return the values `keypath` will take, for the line under the list.

        A key drawn from a fixed set lists that set, in the order the prompt and
        the service's refusal both give it, so the three agree.  Anything else
        takes free text, which is worth saying rather than leaving blank: a line
        with nothing on it reads as a value the screen failed to find.

        The values stand on their own, unlabelled and quiet, directly under the
        list — as they do under the field in the value prompt.  What they are is
        clear from where they sit.
        """
        if keypath is None:
            return ""

        permitted = CONFIG_VALUES.get(keypath)
        return config_values_hint(permitted) if permitted else FREE_TEXT_VALUES

    def _load(self) -> None:
        """Re-read every configuration value from the service."""
        with self._service_errors("config"):
            self._values = self.svc.list_config()

    def value_of(self, keypath: str) -> str | None:
        """Return what the screen holds for `keypath`: its staged value, or the stored one."""
        if keypath in self._staged:
            return self._staged[keypath]
        return self._values.get(keypath)

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

        self._name_width = max((len(_name_of(key)) for key in self._values), default=0)

        rows: list[tuple[str | None, Text]] = []
        self._keypaths = []

        for section in sorted(groups):
            rows.append((None, config_group_label(section)))
            self._keypaths.append(None)

            for keypath in sorted(groups[section]):
                name = _name_of(keypath)
                label = config_label(
                    name,
                    self.value_of(keypath),
                    self._name_width,
                    staged=keypath in self._staged,
                )
                rows.append((name, label))
                self._keypaths.append(keypath)

        return rows

    # ── Editing ───────────────────────────────────────────────────────────────

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Take on the key that was chosen, cycling or opening the field for it."""
        self._edit(self._keypath_at(event.option_index))

    def action_edit(self) -> None:
        """Edit the highlighted setting, as Enter does."""
        self._edit(self._keypath_at(self.rows.highlighted))

    def _edit(self, key: str | None) -> None:
        """
        Step `key` to its next value, or open a field to type one.

        A key drawn from a fixed set has nothing to type — the values line under
        the list is the whole of what it will take — so it cycles instead, which
        makes a setting one keypress to change rather than a dialog.  A heading
        is not a setting, and edits to nothing.
        """
        if key is None:
            return

        permitted = CONFIG_VALUES.get(key)
        if permitted:
            self._cycle(key, permitted)
        else:
            self._open_field(key)

    def _cycle(self, key: str, permitted: frozenset[str]) -> None:
        """Stage the value after the one `key` holds, wrapping round to the first."""
        # The same order the values line gives them in, so what the next Enter
        # lands on is the value after the one shown.
        values = sorted(permitted)

        # A key that is unset, or holding a value no longer permitted, starts at
        # the beginning rather than nowhere.
        current = self.value_of(key)
        index = values.index(current) + 1 if current in values else 0

        self._set_value(key, values[index % len(values)])

    # ── Typing a value on its row ─────────────────────────────────────────────

    def _open_field(self, key: str) -> None:
        """Open the field over the value of `key`, holding what it has now."""
        self._editing = key
        self.field.open(
            self.value_of(key) or "", column=config_value_column(self._name_width)
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Stage what was typed on the row."""
        event.stop()
        self._commit_field(event.value)

    def _commit_field(self, value: str) -> None:
        """
        Close the field, staging `value` for the key it was editing.

        An empty field stages nothing: there is no unset to write, so a value
        cleared away leaves the setting as it was, which is what closing the
        field with nothing in it should do.
        """
        key = self._editing
        self._close_field()

        text = value.strip()
        if key is not None and text:
            self._set_value(key, text)

    def _close_field(self) -> None:
        """Hide the field, whatever it held, and hand the focus back to the list."""
        self.field.close()
        self._editing = None

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

    def _set_value(self, key: str, value: str) -> None:
        """Stage `value` for `key`, then redraw the list."""
        # A value typed back to what is already stored is not a change, so it
        # stops being staged rather than being written again on save.
        if value == self._values.get(key):
            self._staged.pop(key, None)
        else:
            self._staged[key] = value

        self._refresh_list(key)

    def _refresh_list(self, key: str) -> None:
        """Rebuild the rows, staying on the key that was just edited."""
        keys = self.rows
        keys.set_entries(self._entries())

        row = self.row_for(key)
        if row is not None:
            keys.highlighted = row

        self._show_values(keys.highlighted)

    # ── Saving ────────────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or cancel depending on which button was pressed."""
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def action_save(self) -> None:
        """
        Write every staged value, then close.

        A field still open is taken as typed, the same as Enter would take it:
        saving with the cursor in a field means saving what is in it.

        A write that fails leaves the modal up with the rest of the changes
        still staged, so the user can correct the one that was refused rather
        than losing the others to it.
        """
        if self.field.is_open:
            self._commit_field(self.field.value)

        for key, value in list(self._staged.items()):
            try:
                self.svc.set_config(key, value)
            except Exception as exc:
                self._report(exc, "config")
                return
            del self._staged[key]

        self.dismiss(None)

    def action_cancel(self) -> None:
        """Close the field if one is open, otherwise the modal, staging nothing."""
        if self.field.is_open:
            self._close_field()
            return

        self.dismiss(None)

    # ── Errors ────────────────────────────────────────────────────────────────

    @contextmanager
    def _service_errors(self, action: str) -> Iterator[None]:
        """Report a failed service call as a toast instead of tearing down the app."""
        try:
            yield
        except Exception as exc:
            self._report(exc, action)

    def _report(self, exc: Exception, action: str) -> None:
        """Log a failed service call and show it as a toast."""
        description = str(exc) or exc.__class__.__name__
        logging.error("TUI %s failed: %s", action, description)
        self.notify(description, title=action, severity="error")
