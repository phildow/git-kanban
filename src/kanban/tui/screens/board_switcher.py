"""The board switcher modal, pushed on `b`: switch between boards and manage them."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static

from ...models import Board, Slug
from ...services.kanban import KanbanService
from ..formatting import board_label
from ..widgets import PrefixList, RowField, format_hints
from .confirm import ConfirmScreen

T = TypeVar("T")

NEW_BOARD_LABEL = "+ New board…"

# What typing jumps to the new-board row.  No board slug starts with it, so it
# never competes with a board for a typed prefix.
NEW_BOARD_KEY = "+"

# The key of the row a new board is being named in.  It is empty because a
# prefix search is only ever run against something the user typed, and no
# non-empty prefix starts an empty string — so the draft row is never jumped to.
DRAFT_KEY = ""

# The management keys, shifted so that every lowercase letter is left to the
# list for type-ahead: a board called `roadmap` is still reachable by typing
# `r`.  The list is told not to take the shifted forms for its own search,
# which is what leaves them free to reach this screen.
NEW_KEY = "N"
RENAME_KEY = "R"
DELETE_KEY = "D"

MANAGE_KEYS = [NEW_KEY, RENAME_KEY, DELETE_KEY]

# What the modal answers to, in the footer's own key/description form.
MANAGE_HINTS: list[tuple[str, str]] = [
    ("↵", "Switch"),
    (NEW_KEY, "New"),
    (RENAME_KEY, "Rename"),
    (DELETE_KEY, "Delete"),
    ("esc", "Close"),
]

# What it answers to while a board is being named on its row.
EDIT_HINTS: list[tuple[str, str]] = [
    ("↵", "Save"),
    ("esc", "Cancel"),
]


@dataclass(frozen=True)
class SwitchToBoard:
    """The user picked an existing board."""

    slug: Slug


@dataclass(frozen=True)
class BoardsChanged:
    """Boards were created, renamed, or deleted, and none was switched to."""


BoardChoice = SwitchToBoard | BoardsChanged
"""What the switcher came back with."""


class BoardSwitcherScreen(ModalScreen[BoardChoice | None]):
    """
    Lists the available boards, switches between them, and manages them.

    Arrow keys move through the boards and typing jumps to the one whose slug
    starts with what was typed, as the column prompt does.  Enter switches to
    the highlighted board; `N`, `R`, and `D` create, rename, and delete one
    without leaving the list.

    Creating and renaming happen on the row itself, in a `RowField` laid over
    it, prefilled with the name being changed or empty for a new board.

    Boards are read and written through the kanban service, as the
    configuration screen does with settings: the modal stays open across a
    change, so it needs the boards it is showing to be its own.  Switching is
    still left to the board screen — it dismisses with the chosen board, with
    `BoardsChanged` when boards were altered but none chosen, or None when
    nothing happened at all.
    """

    BINDINGS = [
        Binding(NEW_KEY, "new_board", "New", show=True),
        Binding(RENAME_KEY, "rename_board", "Rename", show=True),
        Binding(DELETE_KEY, "delete_board", "Delete", show=True),
        Binding("escape", "cancel", "Close", show=True),
    ]

    def __init__(self, svc: KanbanService, *, active: Slug | None = None) -> None:
        """Create a switcher backed by `svc`, highlighting `active` if it is present."""
        super().__init__()
        self.svc = svc
        self.active = active

        self._boards: list[Board] = []
        # The board the open field is renaming.  None while the field is naming
        # a board that does not exist yet, and meaningless when it is closed.
        self._renaming: Slug | None = None
        self._editing = False
        # Whether anything was created, renamed, or deleted, which is what the
        # board screen has to reload for even when no board was switched to.
        self._changed = False

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Lay out the board list, the modal's hints, and the naming field."""
        self._load()

        # Full width rather than `-narrow`: rows carry a name, a path, and counts.
        with Vertical(id="dialog"):
            yield Static("Boards", id="form-heading")
            rows = PrefixList(
                self._entries(), show_search=False, reserved=MANAGE_KEYS, id="board-list"
            )
            yield rows
            yield Static(format_hints(MANAGE_HINTS), id="board-hint")
            yield RowField(rows, id="board-name")

    def on_mount(self) -> None:
        """Start on the active board, and take focus so the arrow keys work."""
        boards = self.rows

        if self.active is not None and self.active in boards.keys:
            boards.highlighted = boards.keys.index(self.active)

        boards.focus()

    @property
    def rows(self) -> PrefixList:
        """Return the list of boards."""
        return self.query_one("#board-list", PrefixList)

    @property
    def field(self) -> RowField:
        """Return the field a board is named in."""
        return self.query_one("#board-name", RowField)

    def _entries(self, *, draft: bool = False) -> list[tuple[str | None, Text]]:
        """
        Return the rows: every board, the new-board option, then any draft row.

        The draft row is the blank one a new board is being named in.  It is
        drawn empty because the field covers it for as long as it exists.
        """
        # Widths come from the widest entry, so the rows line up as columns.
        name_width = max((len(board.name) for board in self._boards), default=0)
        path_width = max((len(board.slug) + 1 for board in self._boards), default=0)
        count_width = max(
            (len(str(board.task_count)) for board in self._boards), default=0
        )

        entries: list[tuple[str | None, Text]] = [
            (str(board.slug), board_label(board, name_width, path_width, count_width))
            for board in self._boards
        ]
        entries.append((NEW_BOARD_KEY, Text(NEW_BOARD_LABEL)))

        if draft:
            entries.append((DRAFT_KEY, Text("")))

        return entries

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Re-read the boards from the service."""
        self._boards = self._attempt("load boards", self.svc.get_boards) or []

    def _reload(self, select: Slug | None = None) -> None:
        """
        Re-read the boards and redraw the rows, landing on `select`.

        Without a board to land on the highlight stays where it was, clamped to
        what is left — which after a delete is the row the next board has moved
        up into, or the new-board row when the last board has gone.
        """
        row = self.rows.highlighted
        self._load()

        rows = self.rows
        rows.set_entries(self._entries())

        slugs = [board.slug for board in self._boards]
        if select is not None and select in slugs:
            rows.highlighted = slugs.index(select)
        elif row is not None:
            rows.highlighted = min(row, len(rows.keys) - 1)
        else:
            rows.highlighted = rows.first_key_index

        rows.focus()

    def _highlighted_board(self) -> Board | None:
        """Return the board on the highlighted row, or None when it holds no board."""
        row = self.rows.highlighted
        if row is None or not (0 <= row < len(self._boards)):
            return None
        return self._boards[row]

    # ── Switching ─────────────────────────────────────────────────────────────

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Switch to the selected board, or start naming a new one."""
        index = event.option_index

        if index == len(self._boards):
            self.action_new_board()
            return

        if not (0 <= index < len(self._boards)):
            return

        self.dismiss(SwitchToBoard(self._boards[index].slug))

    def action_cancel(self) -> None:
        """Close the field if one is open, otherwise close the modal."""
        if self._editing:
            self._close_field()
            self._reload()
            return

        self.dismiss(BoardsChanged() if self._changed else None)

    # ── Naming a board in place ───────────────────────────────────────────────

    def action_new_board(self) -> None:
        """Append a row to the list and name a new board in it."""
        rows = self.rows
        rows.set_entries(self._entries(draft=True))
        rows.highlighted = len(rows.keys) - 1

        self._renaming = None
        self._open_field("")

    def action_rename_board(self) -> None:
        """Rename the highlighted board, on its own row."""
        board = self._highlighted_board()
        if board is None:
            return

        self._renaming = board.slug
        self._open_field(board.name)

    def _open_field(self, value: str) -> None:
        """Open the naming field over the highlighted row, holding `value`."""
        self._editing = True
        self._show_hints()
        self.field.open(value)

    def _close_field(self) -> None:
        """Hide the naming field and hand focus back to the list."""
        self.field.close()
        self._editing = False
        self._show_hints()

    def _show_hints(self) -> None:
        """Show the hints belonging to whichever mode the modal is in."""
        hints = EDIT_HINTS if self._editing else MANAGE_HINTS
        self.query_one("#board-hint", Static).update(format_hints(hints))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Create or rename the board with the name the field holds."""
        event.stop()

        name = event.value.strip()
        if not name:
            self.action_cancel()
            return

        if self._renaming is None:
            self._create(name)
        else:
            self._rename(self._renaming, name)

    def _create(self, name: str) -> None:
        """Create a board called `name` and stay on it, so more can follow."""
        board = self._attempt("create board", lambda: self.svc.create_board(name))
        # A name the service refused leaves the field open on it, so it can be
        # corrected rather than typed again.
        if board is None:
            return

        self._close_field()
        self._changed = True
        self._reload(board.slug)
        self.notify(f"Created {board.name}")

    def _rename(self, slug: Slug, name: str) -> None:
        """Rename the board `slug` to `name`, staying on it under its new slug."""
        board = self._attempt(
            "rename board", lambda: self.svc.rename_board(Path(f"/{slug}"), name)
        )
        if board is None:
            return

        self._close_field()
        self._changed = True
        self._reload(board.slug)
        self.notify(f"Renamed to {board.name}")

    # ── Deleting a board ──────────────────────────────────────────────────────

    def action_delete_board(self) -> None:
        """Ask whether to delete the highlighted board, then delete it."""
        board = self._highlighted_board()
        if board is None:
            return

        tasks = f"{board.task_count} task" + ("" if board.task_count == 1 else "s")
        prompt = Text(f"Delete board {board.name} (/{board.slug}) and its {tasks}?")

        self.app.push_screen(
            ConfirmScreen(prompt), lambda ok: self._delete(board, bool(ok))
        )

    def _delete(self, board: Board, confirmed: bool) -> None:
        """Delete `board` once the confirmation has come back."""
        if not confirmed:
            return

        deleted = self._attempt(
            "delete board", lambda: self.svc.delete_board(Path(f"/{board.slug}"))
        )
        if deleted is None:
            return

        self._changed = True
        self._reload()
        self.notify(f"Deleted {deleted.name}")

    # ── Errors ────────────────────────────────────────────────────────────────

    def _attempt(self, action: str, call: Callable[[], T]) -> T | None:
        """Run `call`, reporting a failure as a toast and returning None instead."""
        try:
            return call()
        except Exception as exc:
            description = str(exc) or exc.__class__.__name__
            logging.error("TUI %s failed: %s", action, description)
            self.notify(description, title=action, severity="error")
            return None
