"""
The board screen: the TUI's default screen.

The screen owns all interaction with the kanban service.  Widgets render what
they are handed and never query the service themselves.  The filesystem stays
the source of truth: the screen re-fetches after every mutation of its own, and
on demand with `r`.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator, cast
from uuid import uuid4

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.markup import escape
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, ListView, Static

from ...models import Board, Column, Slug, Task
from ...services.kanban import (
    KanbanService,
    TaskCreateParams,
    TaskUnsetParams,
    TaskUpdateParams,
)
from ...repl.completion_engine import CompletionEngine
from ...repl.parser import build_parser as build_repl_parser
from ..filter_query import FilterQuery, build_filter_parser, parse_filter
from ..formatting import board_subtitle
from ..widgets import (
    ColumnHeader,
    ColumnPanel,
    ColumnView,
    CommandBar,
    CompletingInput,
    FilterBar,
    ModeBar,
    SidebarPanel,
    format_hints,
)
from .board_switcher import BoardChoice, BoardSwitcherScreen, SwitchToBoard
from .column_prompt import ColumnPromptScreen
from .confirm import ConfirmScreen
from .help import HelpScreen
from .output import OutputScreen
from .task_detail import TaskDetailScreen
from .task_form import TaskFormResult, TaskFormScreen

if TYPE_CHECKING:
    from ..app import KanbanApp

# Hints for the modes that replace the footer, in the footer's own key/description
# form so the bar reads as a continuation of it rather than as something else.
MOVE_KEYS: list[tuple[str, str]] = [
    ("←/→ h/l", "Column"),
    ("↑/↓ j/k", "Position"),
    ("⇧", "To the end"),
    ("↵", "Commit"),
    ("esc", "Cancel"),
]
FILTER_KEYS: list[tuple[str, str]] = [
    ("tab", "Complete"),
    ("↵", "Keep filter"),
    ("esc", "Clear"),
]
COMMAND_KEYS: list[tuple[str, str]] = [
    ("tab", "Complete"),
    ("↵", "Run"),
    ("esc", "Cancel"),
]
NAME_KEYS: list[tuple[str, str]] = [
    ("↵", "Save"),
    ("esc", "Cancel"),
]

# How many completion candidates the hint bar will list before giving up.
COMPLETION_HINTS = 12

# What the board still answers to while a card is staged for a move: staging
# keys, and the two ways out.  A move is a mode — editing the card being moved,
# or refreshing the board out from under it, has no meaning half way through.
MOVE_MODE_ACTIONS = frozenset(
    {
        "nav_left",
        "nav_right",
        "nav_up",
        "nav_down",
        "nav_far_left",
        "nav_far_right",
        "nav_far_up",
        "nav_far_down",
        "nav_page_up",
        "nav_page_down",
        "nav_page_left",
        "nav_page_right",
        "activate",
        "move_task",
        "step_focus",
        "cancel",
    }
)

# A focused column header is a mode of its own, as a staged move is: it answers
# to the keys that manipulate a column — which are the header's own bindings —
# and to these, which move between the columns being manipulated and back down
# to the cards.  Everything else the board offers is refused, so `n`, `d`, and `r`
# reach the header rather than the card, and the footer shows the column's
# actions in place of the board's.
HEADER_ACTIONS = frozenset(
    {
        "nav_left",
        "nav_right",
        "step_focus",
    }
)

# Commands that need a real terminal — an editor or a confirmation prompt — and
# so cannot be driven from the command bar while the TUI owns the screen.
UNSUPPORTED_COMMANDS = {"edit"}


@dataclass
class MoveState:
    """
    The staged destination of the card being moved.

    Move mode is preview-only: `column_index` and `position` describe where the
    card would land, and nothing is written until the move is committed.
    """

    task:         Task
    column_index: int
    position:     int


class BoardScreen(Screen[None]):
    """The main board area: one column per board column, plus a collapsible sidebar."""

    # The footer shows one entry per action.  Where an action answers to several
    # keys, the first binding carries a `key_display` naming them all and the
    # rest are hidden, so the hints stay complete without repeating themselves.
    BINDINGS = [
        Binding("left,h", "nav_left", "Column", show=True, key_display="←/→ h/l"),
        Binding("up,k", "nav_up", "Card", show=True, key_display="↑/↓ j/k"),
        # The other half of each pair.  `system` keeps them out of the key
        # panel, which lists an entry per action however `show` is set — the
        # entries above already name all four keys.
        Binding("right,l", "nav_right", "Column", show=False, system=True),
        Binding("down,j", "nav_down", "Card", show=False, system=True),
        # Shift goes as far as it will go — the end of a column, the end of the
        # board — whether moving focus or a staged card.  Terminals report the
        # shifted arrows by name and the shifted letters as capitals.
        Binding("shift+left,H", "nav_far_left", "Move to end", show=False),
        Binding("shift+right,L", "nav_far_right", "Move to end", show=False),
        Binding("shift+up,K", "nav_far_up", "Move to end", show=False),
        Binding("shift+down,J", "nav_far_down", "Move to end", show=False),
        # Paging: within a column, and — as terminals spell "page left/right" —
        # across columns with ctrl.
        Binding("pageup", "nav_page_up", "Page cards", show=False),
        Binding("pagedown", "nav_page_down", "Page cards", show=False),
        Binding("ctrl+pageup", "nav_page_left", "Page columns", show=False),
        Binding("ctrl+pagedown", "nav_page_right", "Page columns", show=False),
        # Tab steps between the columns, staying on the half it was pressed on —
        # headers are out of the focus chain and reached with `c`.  A screen
        # binding replaces Textual's own tab rather than sitting beside it, so
        # the board has to move the focus itself, and so no header can be tabbed
        # into.  Mid-move it means something else again: the destination column,
        # by name.
        Binding("tab", "step_focus(1)", "Next", show=False),
        Binding("shift+tab", "step_focus(-1)", "Previous", show=False),
        Binding("enter", "activate", "Open", show=False),
        # An alias for Enter on the selected card.  Hidden from the footer,
        # where the column's own Enter binding already offers "Open".
        Binding("v", "view_task", "View", show=False),
        Binding("n", "new_task", "New", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("m", "move_task", "Move", show=True),
        Binding("slash", "command", "Command", show=True, key_display="/"),
        Binding("colon", "filter", "Filter", show=True, key_display=":"),
        Binding("s", "toggle_sidebar", "Sidebar", show=True),
        Binding("b", "switch_board", "Board", show=True),
        Binding("c", "focus_header", "Column", show=True),
        Binding("x", "toggle_density", "Collapse", show=True),
        Binding("r", "reload_board", "Refresh", show=True),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    move_mode: reactive[bool] = reactive(False)
    """True while a card is staged for a move."""

    dense: reactive[bool] = reactive(False)
    """True when cards are collapsed to single-line summaries."""

    def __init__(self, svc: KanbanService) -> None:
        """Create a board screen backed by `svc`."""
        super().__init__()
        self.svc = svc

        self._boards: list[Board] = []
        self._board: Board | None = None
        self._columns: list[Column] = []
        self._tasks: dict[Slug, list[Task]] = {}
        self._filter = FilterQuery()
        self._move: MoveState | None = None
        # The column the detail screen is reading from, while one is open.  The
        # modal holds focus, so the board's current column cannot be read off it.
        self._detail_view: ColumnView | None = None
        # The panel standing in for a column being named, before it exists.
        self._draft: ColumnPanel | None = None
        # Column and position the moving card is currently drawn at, or None
        # when no column is showing a staged position.
        self._preview: tuple[Slug, int] | None = None
        # Redraws are scheduled as workers and empty a column before refilling
        # it, so two of them running at once on the same column interleave and
        # leave it holding both sets of cards.  Every redraw takes this first,
        # which also keeps them in the order they were scheduled — so the draw
        # that ran last is the one with the most recent data.
        self._redraw = asyncio.Lock()

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        """Lay out the header, the columns, the sidebar, the input bars, and the footer."""
        yield Header()
        with Horizontal(id="board-body"):
            yield Horizontal(id="columns")
            yield SidebarPanel(self.svc, id="sidebar")
        yield FilterBar(id="filter-bar")
        yield CommandBar(id="command-bar")
        yield ModeBar(id="mode-bar")
        # Compact so more board keys fit.  The palette hint stays, docked to
        # the right of the bar where Textual puts it.
        yield Footer(compact=True)

    async def on_mount(self) -> None:
        """Attach the completers, load the board, and ask which board to show if none is active."""
        self._install_completers()
        await self.reload()

        # Without a working board the screen falls back to the first one, which
        # is a guess: ask instead.  With no boards at all there is nothing to
        # choose between, so the empty board's message stands.
        if self.svc.working_board is None and self._boards:
            self.action_switch_board()

    def _install_completers(self) -> None:
        """
        Give each bar the completions it should offer.

        Both reuse the REPL's completion engine, so Tab completes the same
        commands, flags, tags, and names it does there.  The filter bar is
        walked against its own parser, the command bar against the REPL's.
        """
        self.query_one(FilterBar).completer = CompletionEngine(
            self.svc, build_filter_parser()
        )
        self.query_one(CommandBar).completer = CompletionEngine(
            self.svc, build_repl_parser()
        )

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def column_views(self) -> list[ColumnView]:
        """Return the mounted column views, left to right."""
        return list(self.query(ColumnView))

    @property
    def column_panels(self) -> list[ColumnPanel]:
        """Return the mounted columns, left to right, headers included."""
        return list(self.query(ColumnPanel))

    @property
    def focused_column(self) -> ColumnView | None:
        """
        Return the focused column, falling back to the leftmost one.

        A column is two focus targets — its header and its cards — and either
        means the same column.  A modal covering the board takes the focus with
        it, but the detail screen still reads from a column of the board's, and
        that is the one the board is on until it closes.
        """
        if self._detail_view is not None:
            return self._detail_view

        focused = self.app.focused
        if isinstance(focused, ColumnView):
            return focused
        # Textual defers focus, so a header can be focused after the board it
        # was on has been rebuilt out from under it — the prune that removed it
        # had nothing to reset, since the focus had not been set yet.  A header
        # with no panel left is such a leftover, and names no column.
        if isinstance(focused, ColumnHeader) and isinstance(focused.parent, ColumnPanel):
            return focused.panel.view
        views = self.column_views
        return views[0] if views else None

    @property
    def focused_header(self) -> ColumnHeader | None:
        """Return the column header holding focus, if one does."""
        focused = self.app.focused
        return focused if isinstance(focused, ColumnHeader) else None

    @property
    def selected_task(self) -> Task | None:
        """Return the task highlighted in the focused column, if any."""
        column = self.focused_column
        return column.selected_task if column is not None else None

    @property
    def kanban_app(self) -> KanbanApp:
        """Return the running app, typed so its kanban members are visible."""
        return cast("KanbanApp", self.app)

    @property
    def sidebar(self) -> SidebarPanel | None:
        """Return the sidebar panel, or None before it has mounted."""
        return next(iter(self.query(SidebarPanel)), None)

    @property
    def mode_bar(self) -> ModeBar | None:
        """Return the contextual hint bar, or None before it has mounted."""
        return next(iter(self.query(ModeBar)), None)

    # ── Loading and rendering ─────────────────────────────────────────────────

    async def reload(
        self, select: Slug | None = None, *, focus_header: Slug | None = None
    ) -> None:
        """
        Re-query the service and rebuild the board.

        `select` highlights a task by slug once the rebuild is done; when it is
        omitted the current selection and focused column are preserved.
        `focus_header` lands on a column's header instead, which is where a
        change made from the header strip should leave the user.
        """
        column = self.focused_column
        focus_column = column.column.slug if column is not None else None
        if select is None and focus_header is None:
            selected = self.selected_task
            select = selected.slug if selected is not None else None

        self._fetch()
        async with self._redraw:
            await self._render_board(
                select=select, focus_column=focus_column, focus_header=focus_header
            )

        self._sync_subtitle()
        self._reload_sidebar()

    async def refresh_columns(
        self, columns: Iterable[Slug], select: Slug | None = None
    ) -> None:
        """
        Re-query only `columns` and redraw them, leaving the rest of the board alone.

        Used after an operation whose effects are confined to columns the screen
        already knows, such as a committed move.  Falls back to a full reload
        when the board or a named column is not on screen, since then the
        assumption that nothing else changed no longer holds.
        """
        board = self._board
        views = {view.column.slug: view for view in self.column_views}
        targets = list(dict.fromkeys(columns))

        if board is None or not targets or any(slug not in views for slug in targets):
            await self.reload(select)
            return

        async with self._redraw:
            # Queried under the lock so a draw waiting its turn re-reads rather
            # than redrawing with what the service said before it waited.
            with self._service_errors("load"):
                for slug in targets:
                    self._tasks[slug] = self.svc.get_tasks(Path(f"/{board.slug}/{slug}"))

            for slug in targets:
                await views[slug].set_tasks(self._visible(slug), dense=self.dense)

            self._select_task(select)

        self._sync_subtitle()
        self._reload_sidebar()

    def _sync_subtitle(self) -> None:
        """Update the header to match the tasks currently held."""
        task_count = sum(len(tasks) for tasks in self._tasks.values())
        self.sub_title = board_subtitle(self._board, task_count)

    def _reload_sidebar(self) -> None:
        """Re-query the sidebar, if it has mounted."""
        sidebar = self.sidebar
        if sidebar is not None:
            sidebar.reload()

    def _fetch(self) -> None:
        """Pull boards, columns, and tasks for the active board from the service."""
        with self._service_errors("load"):
            self._boards = self.svc.get_boards()

            slug = self.svc.working_board
            if slug is None or not any(board.slug == slug for board in self._boards):
                slug = self._boards[0].slug if self._boards else None

            if slug is None:
                self._board = None
                self._columns = []
                self._tasks = {}
                return

            self._board = self.svc.get_board(slug)
            self._columns = self.svc.get_columns(slug)

            tasks = self.svc.get_tasks(Path(f"/{slug}"))
            self._tasks = {
                column.slug: [task for task in tasks if task.column == column.slug]
                for column in self._columns
            }

    def _visible(self, column: Slug) -> list[Task]:
        """Return the tasks of `column` that survive the current filter."""
        tasks = self._tasks.get(column, [])
        if self._filter.is_empty:
            return tasks
        return [task for task in tasks if self._filter.matches(task)]

    async def _render_board(
        self,
        *,
        select: Slug | None = None,
        focus_column: Slug | None = None,
        focus_header: Slug | None = None,
    ) -> None:
        """Rebuild the column panels from the fetched data and restore focus."""
        container = self.query_one("#columns", Horizontal)
        # A rebuild takes the whole strip with it, draft column and all.
        self._draft = None
        await container.remove_children()

        if not self._columns:
            message = (
                "No boards yet — create one with `:` then `create --board <name>`"
                if not self._boards
                else "This board has no columns"
            )
            await container.mount(Static(message, classes="-empty"))
            return

        panels = [
            ColumnPanel(column, id=f"column-{column.slug}") for column in self._columns
        ]
        await container.mount_all(panels)

        for panel in panels:
            await panel.view.set_tasks(self._visible(panel.column.slug), dense=self.dense)

        self._restore_focus(
            panels, select=select, focus_column=focus_column, focus_header=focus_header
        )

    def _restore_focus(
        self,
        panels: list[ColumnPanel],
        *,
        select: Slug | None,
        focus_column: Slug | None,
        focus_header: Slug | None = None,
    ) -> None:
        """Focus the column that held focus and re-highlight the selected task."""
        if focus_header is not None:
            panel = next(
                (panel for panel in panels if panel.column.slug == focus_header), None
            )
            if panel is not None:
                panel.header.focus()
                return

        if self._select_task(select):
            return

        target = next(
            (panel for panel in panels if panel.column.slug == focus_column), panels[0]
        )
        target.view.focus()

    def _select_task(self, slug: Slug | None) -> bool:
        """Highlight and focus the task with `slug`.  Returns False when it is not shown."""
        if slug is None:
            return False

        for view in self.column_views:
            if view.select_task(slug):
                view.focus()
                return True
        return False

    async def _render_current(self, select: Slug | None = None) -> None:
        """
        Repopulate the columns from data already fetched, without touching the service.

        Used when the filter changes, which can add or remove cards anywhere, so
        every column is offered the new contents — but `_render_column` skips
        the ones that end up unchanged.

        Focus is left where it is: the caller may well be the filter bar, which
        the user is still typing into.
        """
        async with self._redraw:
            for view in self.column_views:
                await self._render_column(view.column.slug)

            if select is not None:
                self._select_task(select)

    def _reload_soon(
        self, select: Slug | None = None, *, focus_header: Slug | None = None
    ) -> None:
        """Schedule a reload from a synchronous context, such as a modal callback."""
        self.run_worker(
            self.reload(select, focus_header=focus_header), exclusive=False
        )

    def _render_soon(self, select: Slug | None = None) -> None:
        """Schedule a re-render from a synchronous context."""
        self.run_worker(self._render_current(select), exclusive=False)

    def _refresh_columns_soon(
        self, columns: Iterable[Slug], select: Slug | None = None
    ) -> None:
        """Schedule a targeted column refresh from a synchronous context."""
        self.run_worker(self.refresh_columns(columns, select), exclusive=False)

    # ── Navigation ────────────────────────────────────────────────────────────

    def action_nav_left(self) -> None:
        """Move focus, or the staged card, one column to the left."""
        if self.move_mode:
            self._stage_column(-1)
        else:
            self._focus_column(-1)

    def action_nav_right(self) -> None:
        """Move focus, or the staged card, one column to the right."""
        if self.move_mode:
            self._stage_column(1)
        else:
            self._focus_column(1)

    def action_nav_up(self) -> None:
        """Move the cursor, or the staged card, up one position."""
        if self.move_mode:
            self._stage_position(-1)
            return
        column = self.focused_column
        if column is not None:
            column.action_cursor_up()

    def action_nav_down(self) -> None:
        """Move the cursor, or the staged card, down one position."""
        if self.move_mode:
            self._stage_position(1)
            return
        column = self.focused_column
        if column is not None:
            column.action_cursor_down()

    def action_nav_far_left(self) -> None:
        """Stage the card in, or move focus to, the leftmost column."""
        if self.move_mode:
            self._stage_column_at(0)
        else:
            self._focus_column_at(0)

    def action_nav_far_right(self) -> None:
        """Stage the card in, or move focus to, the rightmost column."""
        if self.move_mode:
            self._stage_column_at(len(self._columns) - 1)
        else:
            self._focus_column_at(len(self.column_views) - 1)

    def action_nav_far_up(self) -> None:
        """Stage, or select, the card at the top of the column."""
        if self.move_mode:
            self._stage_position_at(0)
        else:
            self._select_card_at(0)

    def action_nav_far_down(self) -> None:
        """Stage, or select, the card at the bottom of the column."""
        move = self._move
        if self.move_mode:
            if move is not None:
                self._stage_position_at(self._staged_limit(move))
            return

        column = self.focused_column
        if column is not None:
            self._select_card_at(len(column.tasks) - 1)

    def action_nav_page_up(self) -> None:
        """Move a screenful of cards towards the top of the column."""
        self._page_cards(-1)

    def action_nav_page_down(self) -> None:
        """Move a screenful of cards towards the bottom of the column."""
        self._page_cards(1)

    def action_nav_page_left(self) -> None:
        """Move a screenful of columns towards the start of the board."""
        self._page_columns(-1)

    def action_nav_page_right(self) -> None:
        """Move a screenful of columns towards the end of the board."""
        self._page_columns(1)

    def _page_cards(self, direction: int) -> None:
        """Move `direction` pages through the focused column's cards."""
        column = self.focused_column
        if column is None:
            return

        step = direction * _cards_per_page(column)

        if self.move_mode:
            self._stage_position(step)
            return

        index = column.index or 0
        self._select_card_at(index + step)

    def _page_columns(self, direction: int) -> None:
        """Move `direction` pages through the board's columns."""
        step = direction * self._columns_per_page()

        if self.move_mode:
            self._stage_column(step)
            return

        self._focus_column(step)

    def _columns_per_page(self) -> int:
        """Return how many columns fit across the board at once."""
        views = self.column_views
        if not views:
            return 1

        column_width = max(1, views[0].outer_size.width)
        visible = self.query_one("#columns", Horizontal).container_size.width

        return max(1, visible // column_width)

    def _select_card_at(self, index: int) -> None:
        """Highlight the card at `index` in the focused column, clamped to its ends."""
        column = self.focused_column
        if column is None or not column.tasks:
            return

        column.index = max(0, min(index, len(column.tasks) - 1))

    def _focus_column(self, delta: int) -> None:
        """Move focus `delta` columns, clamped to the ends of the board."""
        views = self.column_views
        if not views:
            return

        current = views.index(self.focused_column) if self.focused_column in views else 0
        self._focus_column_at(current + delta)

    def _focus_column_at(self, index: int) -> None:
        """
        Focus the column at `index`, clamped to the ends of the board.

        Focus stays on the half of the column it is already on: moving along the
        header strip keeps to the headers, moving between card lists to the
        cards.
        """
        panels = self.column_panels
        if not panels:
            return

        panel = panels[max(0, min(index, len(panels) - 1))]
        if self.focused_header is not None:
            panel.header.focus()
        else:
            panel.view.focus()

    def action_step_focus(self, direction: int) -> None:
        """
        Step focus to the next column, wrapping at the ends of the board.

        Headers are out of the chain: a header is reached with `c`, never by
        tabbing into one, and tab stays on the half of the column it was pressed
        on — cards to cards, and along the header strip while a header is the
        mode.  Mid-move tab means something else again: the destination column,
        by name.
        """
        if self.move_mode:
            if direction > 0:
                self.action_move_to_column()
            return

        panels = self.column_panels
        if not panels:
            return

        column = self.focused_column
        index = (
            panels.index(column.panel)
            if column is not None and column.panel in panels
            else 0
        )

        target = panels[(index + direction) % len(panels)]
        if self.focused_header is not None:
            target.header.focus()
        else:
            target.view.focus()

    def action_focus_header(self) -> None:
        """Focus the header of the column in focus, which is the way into it."""
        column = self.focused_column
        if column is not None and isinstance(column.parent, ColumnPanel):
            column.panel.header.focus()

    def action_activate(self) -> None:
        """Commit the staged move, or open the focused card."""
        if self.move_mode:
            self._commit_move()
        else:
            self.action_view_task()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Open the detail screen when a card is selected with Enter or the mouse."""
        _ = event
        if not self.move_mode:
            self.action_view_task()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Scope the sidebar log to the highlighted task, or to the board when none."""
        _ = event
        self._scope_sidebar()

    def _scope_sidebar(self) -> None:
        """Point the sidebar log at the selected task, or at the board when there is none."""
        sidebar = self.sidebar
        if sidebar is None:
            return

        task = self.selected_task
        sidebar.set_scope(task.path if task is not None else self._board_path())

    def _board_path(self) -> Path:
        """Return the path of the active board, or the root when there is none."""
        return Path(f"/{self._board.slug}") if self._board is not None else Path("/")

    # ── Task actions ──────────────────────────────────────────────────────────

    def action_view_task(self) -> None:
        """Open the detail screen for the focused card."""
        column = self.focused_column
        task = self.selected_task
        if column is None or task is None:
            self.notify("No task selected", severity="warning")
            return

        # Held for as long as the modal is up: it is what the board is reading
        # from, and what its navigation keys move.
        self._detail_view = column
        self.app.push_screen(
            TaskDetailScreen(task, navigate=self._navigate_detail),
            self._detail_closed,
        )

    def _navigate_detail(self, columns: int, cards: int) -> Task | None:
        """
        Move the selection under the detail screen, and return what it lands on.

        The same movement the board's own arrows make — `columns` between
        columns, `cards` within one — so closing the screen leaves the user on
        the card they navigated to.  A column with nothing in it is not moved
        into: the detail screen always has a task to draw.

        Returns None when the selection did not move, which is what tells the
        detail screen it has nothing to redraw.
        """
        views = self.column_views
        view = self._detail_view
        if view is None or view not in views:
            return None

        if columns:
            target = views[
                max(0, min(views.index(view) + columns, len(views) - 1))
            ]
            if target is view or not target.tasks:
                return None

            if target.index is None:
                target.index = 0
            self._detail_view = target
            # Focus is per screen, so the board's own focus is still on the
            # column the modal was opened from and still drawn as focused.
            # Moving it is what moves the board's mark of where it is.
            target.focus()
            target.panel.scroll_visible()
            view = target
            # Changing column leaves the highlight where it was, so nothing
            # else tells the sidebar the selection moved.
            self._scope_sidebar()
        elif cards and view.tasks:
            view.index = max(0, min((view.index or 0) + cards, len(view.tasks) - 1))

        return view.selected_task

    def _detail_closed(self, task: Task | None) -> None:
        """
        Let go of the column the detail screen was reading from.

        Navigating already moved the board's focus to it, so there is nothing to
        restore — the screen is handed back exactly as it was left.  `task` is
        the task the user asked to edit, if they did.
        """
        self._detail_view = None

        if task is not None:
            self._edit_form(task)

    def action_new_task(self) -> None:
        """Open the task form to create a task in the focused column."""
        column = self.focused_column
        if column is None:
            self.notify("No column to create a task in", severity="warning")
            return

        target = column.column
        self.app.push_screen(
            TaskFormScreen(column=target, assignees=self._assignees(), tags=self._tags()),
            lambda result: self._create_task(target, result),
        )

    def action_edit_task(self) -> None:
        """Open the task form pre-filled with the focused card."""
        task = self.selected_task
        if task is None:
            self.notify("No task selected", severity="warning")
            return

        self._edit_form(task)

    def _edit_form(self, task: Task) -> None:
        """Open the task form on `task`, wherever the request came from."""
        self.app.push_screen(
            TaskFormScreen(task=task, assignees=self._assignees(), tags=self._tags()),
            lambda result: self._update_task(task, result),
        )

    def _assignees(self) -> list[str]:
        """Return the names already in use on the active board, for the form's dropdown."""
        assignees: list[str] = []
        with self._service_errors("assignees"):
            assignees = self.svc.get_assigned_tos(self.svc.working_board)
        return assignees

    def _tags(self) -> list[str]:
        """Return the tags already in use on the active board, for the form's dropdown."""
        tags: list[str] = []
        with self._service_errors("tags"):
            tags = self.svc.get_tags(self.svc.working_board)
        return tags

    def action_delete_task(self) -> None:
        """Ask for confirmation, then delete the focused card."""
        task = self.selected_task
        if task is None:
            self.notify("No task selected", severity="warning")
            return

        self.app.push_screen(
            ConfirmScreen("Delete Task?", task=task),
            lambda confirmed: self._delete_task(task, confirmed),
        )

    def _create_task(self, column: Column, result: TaskFormResult | None) -> None:
        """Create a task from the form result, or do nothing when cancelled."""
        if result is None:
            return

        created: Task | None = None
        with self._service_errors("create"):
            created = self.svc.create_task(
                Path(f"/{column.board}/{column.slug}"),
                TaskCreateParams(
                    title=result.title,
                    assigned_to=result.assigned_to,
                    priority=result.priority,
                    tags=result.tags,
                    due_date=result.due_date,
                    description=result.description,
                ),
            )
            if created is not None and result.comment:
                created = self.svc.comment_task(created.path, result.comment)

        if created is not None:
            self._announce(f"Created {_task_name(created.title)}")
            # A new task only lands in the column it was created in.
            self._refresh_columns_soon([created.column], created.slug)

    def _update_task(self, task: Task, result: TaskFormResult | None) -> None:
        """Apply the form result to `task`, clearing the fields the user emptied."""
        if result is None:
            return

        updated: Task | None = None
        with self._service_errors("update"):
            updated = self.svc.update_task(
                task.path,
                TaskUpdateParams(
                    title=result.title,
                    assigned_to=result.assigned_to,
                    priority=result.priority,
                    due_date=result.due_date,
                    tags=result.tags,
                    description=result.description or None,
                ),
            )

            # update_task only ever sets values and unions tags, so emptied
            # fields and removed tags have to go through unset_task.
            unsets = TaskUnsetParams(
                assigned_to=result.assigned_to is None and task.assigned_to is not None,
                priority=result.priority is None and task.priority is not None,
                due_date=result.due_date is None and task.due_date is not None,
                tags=sorted(set(task.tags) - set(result.tags)),
                description=not result.description and bool(task.description),
            )
            if any(
                [
                    unsets.assigned_to,
                    unsets.priority,
                    unsets.due_date,
                    unsets.tags,
                    unsets.description,
                ]
            ):
                updated = self.svc.unset_task(updated.path, unsets)

            # Comments are appended, never rewritten, so this is its own call.
            if result.comment:
                updated = self.svc.comment_task(updated.path, result.comment)

        if updated is not None:
            self._announce(f"Updated {_task_name(updated.title)}")
            # The form cannot move a task, so an edit stays in one column.
            self._refresh_columns_soon([updated.column], updated.slug)

    def _delete_task(self, task: Task, confirmed: bool) -> None:
        """Delete `task` once the confirmation modal comes back positive."""
        if not confirmed:
            return

        deleted: Task | None = None
        with self._service_errors("delete"):
            deleted = self.svc.delete_task(task.path)

        if deleted is not None:
            self._announce(f"Deleted {_task_name(deleted.title)}")
            # A deleted task only leaves a gap in the column it was in.
            self._refresh_columns_soon([deleted.column])

    # ── Column actions ────────────────────────────────────────────────────────
    #
    # The headers post what they were asked for; the service calls all happen
    # here, as they do for every other widget on the board.  A column arriving,
    # leaving, or changing its name is not confined to columns the screen
    # already knows, so each of these ends in a full reload rather than a
    # targeted refresh — landing on the header, which is where the user is.

    def on_column_header_new_requested(
        self, event: ColumnHeader.NewRequested
    ) -> None:
        """Draw a column to the right of the one asking, and name it there."""
        event.stop()
        self.run_worker(self._begin_draft(event.header), exclusive=False)

    def on_column_header_named(self, event: ColumnHeader.Named) -> None:
        """Create the column a draft header was naming, or rename an existing one."""
        event.stop()
        if event.header.draft:
            self._create_column(event.header, event.name)
        else:
            self._rename_column(event.header, event.name)

    def on_column_header_naming_changed(
        self, event: ColumnHeader.NamingChanged
    ) -> None:
        """Swap the footer for the field's own hints while a column is named."""
        event.stop()
        if event.naming:
            self._show_hints(format_hints(NAME_KEYS))
        else:
            self._hide_hints()

    def on_column_header_naming_cancelled(
        self, event: ColumnHeader.NamingCancelled
    ) -> None:
        """Drop a draft column that was never named."""
        event.stop()
        if event.header.draft:
            self.run_worker(self._discard_draft(event.header.panel), exclusive=False)

    def on_column_header_delete_requested(
        self, event: ColumnHeader.DeleteRequested
    ) -> None:
        """Ask whether to delete the column, then delete it."""
        event.stop()
        column = event.column
        count = len(self._tasks.get(column.slug, []))
        tasks = f"{count} task" + ("" if count == 1 else "s")
        # Named the way the board names it: the column in the colour its header
        # carries, and the path on a line of its own beneath the question, muted
        # the way a task's path reads, so it addresses what is being deleted
        # rather than joining in the asking.
        prompt = (
            f"Delete column {_place_name(column.name)} and its {tasks}?\n"
            f"{_path_name(column.path)}"
        )

        self.app.push_screen(
            ConfirmScreen(prompt), lambda ok: self._delete_column(column, bool(ok))
        )

    def on_column_header_reorder_requested(
        self, event: ColumnHeader.ReorderRequested
    ) -> None:
        """Move the column along the board."""
        event.stop()
        self._reorder_column(event.column, event.delta)

    async def _begin_draft(self, header: ColumnHeader) -> None:
        """
        Draw an empty column to the right of `header`'s and open its name field.

        The draft stands where the column will stand, so where it is drawn is
        the position the column is created at.
        """
        board = self._board
        if board is None or self._draft is not None:
            return

        draft = Column(
            id=uuid4(),
            name="",
            slug=Slug(""),
            board=board.slug,
            position=header.column.position + 1,
        )
        panel = ColumnPanel(draft, draft=True)

        async with self._redraw:
            await self.query_one("#columns", Horizontal).mount(
                panel, after=header.panel
            )

        self._draft = panel
        panel.scroll_visible()
        panel.header.begin_naming()

    async def _discard_draft(self, panel: ColumnPanel) -> None:
        """
        Remove a draft column, handing focus to the header it was drawn beside.

        Only when the draft was holding focus, or nothing is: a field closed
        because the user clicked elsewhere has already given focus away, and
        taking it back would undo the click.
        """
        panels = self.column_panels
        index = panels.index(panel) if panel in panels else 0

        focused = self.app.focused
        held_focus = (
            focused is None or focused is panel or panel in focused.ancestors
        )

        self._draft = None
        async with self._redraw:
            await panel.remove()

        remaining = self.column_panels
        if held_focus and remaining:
            remaining[max(0, min(index - 1, len(remaining) - 1))].header.focus()

    def _create_column(self, header: ColumnHeader, name: str) -> None:
        """Create the column the draft header names, where the draft was drawn."""
        board = self._board
        if board is None:
            return

        # Where the draft stands is where the column belongs; a new column is
        # created at the end of the board, so it has to be moved back to it.
        panels = self.column_panels
        position = panels.index(header.panel) if header.panel in panels else None

        created: Column | None = None
        with self._service_errors("create column"):
            created = self.svc.create_column(Path(f"/{board.slug}"), name)
            if position is not None:
                self.svc.reorder_column(created.path, position)

        # A name the service refused leaves the field open on it, so it can be
        # corrected rather than typed again.
        if created is None:
            return

        # The draft goes when the board is rebuilt, so it is not focused: the
        # reload lands on the header of the column that was created.
        header.end_naming(focus=False)
        self._draft = None
        self._announce(f"Created {_place_name(created.name)}")
        self._reload_soon(focus_header=created.slug)

    def _rename_column(self, header: ColumnHeader, name: str) -> None:
        """Rename the column the header names, staying on it under its new slug."""
        column = header.column
        if name == column.name:
            header.end_naming()
            return

        renamed: Column | None = None
        with self._service_errors("rename column"):
            renamed = self.svc.rename_column(column.path, name)

        if renamed is None:
            return

        # As with a create: this header is replaced by the reload, which lands
        # on the one drawn for the column under its new name.
        header.end_naming(focus=False)
        self._announce(f"Renamed to {_place_name(renamed.name)}")
        self._reload_soon(focus_header=renamed.slug)

    def _delete_column(self, column: Column, confirmed: bool) -> None:
        """Delete `column` once the confirmation modal comes back positive."""
        if not confirmed:
            return

        # Read before the delete, while the column is still on the board.
        neighbour = self._neighbour(column)

        deleted: Column | None = None
        with self._service_errors("delete column"):
            deleted = self.svc.delete_column(column.path)

        if deleted is None:
            return

        self._announce(f"Deleted {_place_name(deleted.name)}")
        self._reload_soon(focus_header=neighbour)

    def _reorder_column(self, column: Column, delta: int) -> None:
        """Move `column` `delta` places along the board, staying on its header."""
        slugs = [candidate.slug for candidate in self._columns]
        if column.slug not in slugs:
            return

        index = slugs.index(column.slug)
        target = index + delta
        if not 0 <= target < len(slugs):
            return

        columns: list[Column] | None = None
        with self._service_errors("reorder column"):
            # The service answers with the whole new order, which is what the
            # screen has to agree with once the panels have moved.
            columns = self.svc.reorder_column(column.path, target)

        if columns is None:
            return

        self._columns = columns
        self.run_worker(self._move_column(index, target), exclusive=False)

    async def _move_column(self, index: int, target: int) -> None:
        """
        Move the panel at `index` to `target`, leaving the rest of the board alone.

        A reorder changes where two columns sit and nothing else — not their
        cards, not their counts — so the panels are moved within the container
        rather than rebuilt.  Nothing is redrawn, which is what keeps the cards,
        the scroll positions, and the focused header exactly as they were.

        Falls back to a full reload when the panels on screen do not answer to
        the indices the reorder was worked out from.
        """
        async with self._redraw:
            panels = self.column_panels
            if not (0 <= index < len(panels) and 0 <= target < len(panels)):
                await self.reload()
                return

            moving, beside = panels[index], panels[target]
            container = self.query_one("#columns", Horizontal)
            if target > index:
                container.move_child(moving, after=beside)
            else:
                container.move_child(moving, before=beside)

            # Both have a new position; the two panels are the only ones whose
            # record of themselves the reorder changed.
            for panel in self.column_panels:
                fresh = next(
                    (c for c in self._columns if c.slug == panel.column.slug), None
                )
                if fresh is not None and fresh.position != panel.column.position:
                    panel.set_column(fresh)

    def _neighbour(self, column: Column) -> Slug | None:
        """Return the column that will stand where `column` stands once it is gone."""
        slugs = [candidate.slug for candidate in self._columns]
        if column.slug not in slugs:
            return None

        index = slugs.index(column.slug)
        remaining = slugs[:index] + slugs[index + 1 :]
        if not remaining:
            return None

        return remaining[min(index, len(remaining) - 1)]

    # ── Move mode ─────────────────────────────────────────────────────────────

    def action_move_task(self) -> None:
        """Stage the focused card for a move."""
        if self.move_mode:
            self._commit_move()
            return

        task = self.selected_task
        if task is None:
            self.notify("No task selected", severity="warning")
            return

        column_index = next(
            (i for i, column in enumerate(self._columns) if column.slug == task.column),
            None,
        )
        if column_index is None:
            self.notify("Task is not in a visible column", severity="warning")
            return

        visible = self._visible(task.column)
        position = next(
            (i for i, candidate in enumerate(visible) if candidate.slug == task.slug), 0
        )

        self._move = MoveState(task=task, column_index=column_index, position=position)
        # The board already shows the card here, so the preview starts in sync
        # and the first keystroke is the first redraw.
        self._preview = (task.column, position)
        self.move_mode = True

    def action_move_to_column(self) -> None:
        """Ask for a destination column by slug, and move the card there."""
        move = self._move
        if move is None:
            return

        self.app.push_screen(
            ColumnPromptScreen(
                self._columns, current=self._columns[move.column_index].slug
            ),
            self._move_to_named_column,
        )

    def _move_to_named_column(self, slug: Slug | None) -> None:
        """
        Move the card to the column the prompt came back with.

        Naming a column commits the move outright — the user has already said
        where the card goes, so there is nothing left to confirm.  The staged
        column is therefore never previewed: the card would be drawn where it
        is going only to be drawn there again by the refresh that follows the
        commit.
        """
        move = self._move
        if slug is None or move is None:
            return

        index = next(
            (i for i, column in enumerate(self._columns) if column.slug == slug), None
        )
        if index is None:
            return

        move.column_index = index
        move.position = min(move.position, self._staged_limit(move))
        self._commit_move()

    def _stage_column(self, delta: int) -> None:
        """Stage the card `delta` columns away."""
        move = self._move
        if move is not None:
            self._stage_column_at(move.column_index + delta)

    def _stage_column_at(self, index: int) -> None:
        """Stage the card in column `index`, clamped to the ends of the board."""
        move = self._move
        if move is None:
            return

        target = max(0, min(index, len(self._columns) - 1))
        if target == move.column_index:
            return

        move.column_index = target
        move.position = min(move.position, self._staged_limit(move))
        self._mark_staged()

    def _stage_position(self, delta: int) -> None:
        """Stage the card `delta` places higher or lower."""
        move = self._move
        if move is not None:
            self._stage_position_at(move.position + delta)

    def _stage_position_at(self, position: int) -> None:
        """Stage the card at `position`, clamped to the ends of the staged column."""
        move = self._move
        if move is None:
            return

        target = max(0, min(position, self._staged_limit(move)))
        if target == move.position:
            return

        move.position = target
        self._mark_staged()

    def _staged_limit(self, move: MoveState) -> int:
        """
        Return the highest position the card can be staged at.

        Its own column already counts the card; any other column gains one when
        the move is committed, so it has one more slot than it shows.
        """
        target = self._columns[move.column_index]
        count = len(self._visible(target.slug))

        if target.slug == move.task.column:
            return max(count - 1, 0)
        return count

    def _mark_staged(self) -> None:
        """
        Show where the card would land: the card moves there and the column is marked.

        Only the columns the card is leaving and joining are redrawn, so staging
        stays smooth however wide the board is.
        """
        move = self._move
        views = self.column_views
        if move is None or not views:
            return

        self._sync_preview(move)

        target = views[move.column_index]
        for view in views:
            view.staging = view is target

        target.scroll_visible()
        self._show_hints(self._move_hints(move))

    def _move_hints(self, move: MoveState) -> str:
        """Return the move-mode hints, naming the staged destination and position."""
        target = self._columns[move.column_index]
        slots = self._staged_limit(move) + 1
        destination = (
            f"[$accent]→ /{escape(target.slug)}[/]"
            f" [$text-muted]{move.position + 1}/{slots}[/]"
        )
        return f"{destination}   {format_hints(MOVE_KEYS)}"

    def _set_moving_card(self, moving: bool) -> None:
        """Mark, or unmark, the card being moved."""
        move = self._move

        for view in self.column_views:
            for card in view.cards:
                card.set_moving(
                    moving and move is not None and card.card_task.slug == move.task.slug
                )

    def _sync_preview(self, move: MoveState) -> None:
        """
        Draw the card where it is staged, across columns and within one.

        At most two columns are touched per keystroke — the one the card is
        leaving and the one it is joining — so the rest of the board never
        redraws.  Staying inside a column touches only that column.  Nothing is
        written until the move is committed.
        """
        staged = self._columns[move.column_index].slug
        desired = (staged, move.position)

        if desired == self._preview:
            return

        previous = self._preview
        self._preview = desired

        columns = [staged] if previous is None else [previous[0], staged]
        for column in dict.fromkeys(columns):
            self._draw_soon(
                column,
                order=self._preview_order(column, move),
                select=move.task.slug if column == staged else None,
            )

    def _preview_order(self, column: Slug, move: MoveState) -> list[Task]:
        """
        Return what `column` should show while the card is staged.

        The card is lifted out of whichever column holds it and dropped into the
        staged one, which covers a move across columns and a reorder within one.
        """
        tasks = [task for task in self._visible(column) if task.slug != move.task.slug]

        if column == self._columns[move.column_index].slug:
            index = max(0, min(move.position, len(tasks)))
            tasks.insert(index, move.task)

        return tasks

    def _clear_preview(self, move: MoveState) -> None:
        """Put the card back where it started, after a cancelled move."""
        preview = self._preview
        if preview is None:
            return

        self._preview = None
        origin = move.task.column

        for column in dict.fromkeys([preview[0], origin]):
            self._draw_soon(
                column, select=move.task.slug if column == origin else None
            )

    def _draw_soon(
        self,
        column: Slug,
        *,
        order: list[Task] | None = None,
        select: Slug | None = None,
    ) -> None:
        """Schedule a single-column redraw from a synchronous context."""
        self.run_worker(
            self._draw_column(column, order=order, select=select), exclusive=False
        )

    async def _draw_column(
        self,
        column: Slug,
        *,
        order: list[Task] | None = None,
        select: Slug | None = None,
    ) -> None:
        """Redraw one column, waiting for any redraw already in progress."""
        async with self._redraw:
            await self._render_column(column, order=order, select=select)

    async def _render_column(
        self,
        column: Slug,
        *,
        order: list[Task] | None = None,
        select: Slug | None = None,
    ) -> None:
        """
        Redraw one column from data already held, leaving the rest of the board alone.

        `order` overrides the column's ordering, which is how a staged position
        is previewed without writing anything.

        Callers must hold `_redraw`: emptying and refilling a column takes
        several passes through the event loop, and another draw arriving part
        way through leaves the column holding cards from both.
        """
        view = next(
            (v for v in self.column_views if v.column.slug == column), None
        )
        if view is None:
            return

        desired = self._visible(column) if order is None else order

        # Staging can arrive at the arrangement already on screen — entering and
        # leaving a column without reordering, say.  Redrawing would be a no-op.
        if [task.slug for task in desired] != [task.slug for task in view.tasks]:
            await view.set_tasks(desired, dense=self.dense)

        if select is not None and view.select_task(select):
            # Focus follows the card so it keeps the highlight of a live
            # selection rather than the dimmer blurred one.
            view.focus()

        # set_tasks builds fresh cards, so the moving card needs marking again.
        self._set_moving_card(self.move_mode)

    def _commit_move(self) -> None:
        """Write the staged move: one move_task when the column changed, then reorder."""
        move = self._move
        if move is None:
            return

        task = move.task
        source = task.column
        target = self._columns[move.column_index]
        preview = self._preview
        moved: Task | None = None

        with self._service_errors("move"):
            if target.slug != task.column:
                task = self.svc.move_task(task.path, target.slug)
            self._reorder_to(task, move.position)
            moved = task

        self.move_mode = False
        self._move = None
        self._preview = None

        if moved is not None:
            self._announce(
                f"Moved {_task_name(moved.title)} to {_place_name(target.name)}"
            )

        # A move only disturbs the column it left and the one it landed in —
        # plus, when the card was staged elsewhere on the way, the column that
        # was last previewing it and is still drawing it there.
        disturbed = [source, target.slug]
        if preview is not None:
            disturbed.append(preview[0])

        self._refresh_columns_soon(
            disturbed, moved.slug if moved is not None else None
        )

    def _reorder_to(self, task: Task, position: int) -> None:
        """
        Nudge `task` to `position` within its column.

        The repository's reorder API is op-based — "up", "down", "top",
        "bottom" — rather than index-based, so an interior position is reached
        by repeating the appropriate op.
        """
        order = [t.slug for t in self.svc.get_tasks(Path(f"/{task.board}/{task.column}"))]
        if task.slug not in order:
            return

        current = order.index(task.slug)
        position = max(0, min(position, len(order) - 1))

        if position == current:
            return
        if position == 0:
            self.svc.reorder_task(task.path, "top")
            return
        if position == len(order) - 1:
            self.svc.reorder_task(task.path, "bottom")
            return

        op = "up" if position < current else "down"
        for _ in range(abs(position - current)):
            self.svc.reorder_task(task.path, op)

    def _cancel_move(self) -> None:
        """
        Leave move mode without writing anything.

        Only a column that previewed the card in a new position has to be put
        back; everything else still shows the arrangement it was fetched with.
        """
        move = self._move
        self.move_mode = False
        self._move = None

        if move is not None:
            self._clear_preview(move)

    def watch_move_mode(self, move_mode: bool) -> None:
        """Lock the columns and swap the footer for the move-mode hints."""
        for view in self.column_views:
            view.locked = move_mode
            if not move_mode:
                view.staging = False

        self._set_moving_card(move_mode)

        if move_mode:
            self._mark_staged()
        else:
            self._hide_hints()

    # ── Board, sidebar, density ───────────────────────────────────────────────

    def action_switch_board(self) -> None:
        """Open the board switcher, which also creates, renames, and deletes boards."""
        active = self._board.slug if self._board is not None else None
        self.app.push_screen(
            BoardSwitcherScreen(self.svc, active=active), self._switch_board
        )

    def _switch_board(self, choice: BoardChoice | None) -> None:
        """
        Act on the switcher's result: change board, or reload after a change.

        The switcher writes its own creates, renames, and deletes, so a result
        that names no board still means the boards on screen are stale.  Only
        `None` — nothing chosen and nothing altered — leaves the screen alone.
        """
        if choice is None:
            return

        if isinstance(choice, SwitchToBoard):
            with self._service_errors("board"):
                self.svc.set_board(choice.slug)

        self._reload_soon()

    def action_toggle_sidebar(self) -> None:
        """Collapse or expand the sidebar."""
        sidebar = self.sidebar
        if sidebar is not None:
            sidebar.toggle()

    def action_toggle_density(self) -> None:
        """Collapse cards to one line, or expand them again."""
        self.dense = not self.dense

    def watch_dense(self, dense: bool) -> None:
        """Propagate the density change to every column."""
        for view in self.column_views:
            view.set_dense(dense)

    def action_reload_board(self) -> None:
        """Re-read the board from the filesystem."""
        self._reload_soon()
        self.notify("Refreshed")

    def action_help(self) -> None:
        """Open the bindings reference."""
        self.app.push_screen(HelpScreen())

    # ── Filter and command bars ───────────────────────────────────────────────

    def action_filter(self) -> None:
        """Open the inline filter bar."""
        bar = self.query_one(FilterBar)
        bar.add_class("-visible")
        bar.focus()
        self._show_hints(self._bar_hints(bar))

    def action_command(self) -> None:
        """Open the command bar."""
        bar = self.query_one(CommandBar)
        bar.add_class("-visible")
        bar.focus()
        self._show_hints(self._bar_hints(bar))

    def _bar_hints(self, bar: Input) -> str:
        """Return the hints belonging to whichever bar is open."""
        keys = FILTER_KEYS if isinstance(bar, FilterBar) else COMMAND_KEYS
        return format_hints(keys)

    def action_cancel(self) -> None:
        """Escape: close an open bar, clear the filter, or cancel a staged move."""
        command_bar = self.query_one(CommandBar)
        if command_bar.has_class("-visible"):
            command_bar.value = ""
            self._close_bar(command_bar)
            return

        filter_bar = self.query_one(FilterBar)
        if filter_bar.has_class("-visible") or not self._filter.is_empty:
            filter_bar.value = ""
            self._filter = FilterQuery()
            filter_bar.remove_class("-invalid")
            self._close_bar(filter_bar)
            self._render_soon()
            return

        if self.move_mode:
            self._cancel_move()

    def _close_bar(self, bar: FilterBar | CommandBar) -> None:
        """Hide an input bar and hand focus back to the board."""
        bar.remove_class("-visible")
        self._hide_hints()

        column = self.focused_column
        if column is not None:
            column.focus()

    def on_completing_input_ambiguous(self, event: CompletingInput.Ambiguous) -> None:
        """
        Show the candidates Tab could not choose between.

        They are muted so they read as suggestions rather than as the key
        hints they stand in for.
        """
        candidates = "   ".join(
            escape(candidate) for candidate in event.candidates[:COMPLETION_HINTS]
        )
        self._show_hints(candidates, muted=True)

    def on_input_changed(self, event: FilterBar.Changed) -> None:
        """Live-filter the visible cards as the user types in the filter bar."""
        # Closing a bar clears it, and that change arrives after the close.  A
        # hidden bar has no hints to restore.
        if not event.input.has_class("-visible"):
            return

        # Typing moves past any completion candidates still on the hint bar.
        self._show_hints(self._bar_hints(event.input))

        if not isinstance(event.input, FilterBar):
            return
        parsed = parse_filter(event.value)

        # A half-typed flag is not an empty filter: keep the last query that
        # parsed so the board holds still until the user finishes typing.
        event.input.set_class(parsed is None, "-invalid")
        if parsed is None:
            return

        self._filter = parsed
        self._render_soon()

    def on_input_submitted(self, event: FilterBar.Submitted) -> None:
        """Keep the filter and return to the board, or run the typed command."""
        if isinstance(event.input, FilterBar):
            self._close_bar(event.input)
            return

        if isinstance(event.input, CommandBar):
            line = event.value.strip()
            event.input.value = ""
            self._close_bar(event.input)
            if line:
                self._run_command(line)

    def _run_command(self, line: str) -> None:
        """
        Parse `line` with the REPL parser and run it against the kanban service.

        Output is captured rather than printed, since the terminal belongs to
        the TUI.  Commands that need a terminal of their own — an editor or a
        confirmation prompt — are refused rather than left to hang.
        """
        from ...repl.parser import build_parser

        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            self.notify(str(exc), title="command", severity="error")
            return

        if tokens and tokens[0] in UNSUPPORTED_COMMANDS:
            self.notify(
                f"`{tokens[0]}` needs its own terminal; run it from the REPL",
                title="command",
                severity="warning",
            )
            return

        buffer = StringIO()
        renderer = self.kanban_app.command_renderer

        try:
            with redirect_stdout(buffer), redirect_stderr(buffer):
                args = build_parser().parse_args(tokens)
        except SystemExit:
            # argparse reports usage errors by exiting; show what it printed.
            self.app.push_screen(OutputScreen(line, buffer.getvalue()))
            return

        if not hasattr(args, "func"):
            self.notify("No command handler registered", title="command", severity="error")
            return

        with self._service_errors("command"):
            with redirect_stdout(buffer), redirect_stderr(buffer):
                args.func(args, self.svc, renderer)

        output = f"{buffer.getvalue()}{renderer.take_output()}".strip()
        self._reload_soon()

        if output:
            self.app.push_screen(OutputScreen(line, output))

    def _show_hints(self, hints: str, *, muted: bool = False) -> None:
        """Swap the footer for a contextual hint bar."""
        mode_bar = self.mode_bar
        if mode_bar is None:
            return
        mode_bar.show(hints, muted=muted)
        self._set_footer_visible(False)

    def _hide_hints(self) -> None:
        """Restore the footer."""
        mode_bar = self.mode_bar
        if mode_bar is not None:
            mode_bar.hide()
        self._set_footer_visible(True)

    def _set_footer_visible(self, visible: bool) -> None:
        """Show or hide the footer, which the mode bar replaces."""
        for footer in self.query(Footer):
            footer.display = visible

    # ── Errors ────────────────────────────────────────────────────────────────

    def _announce(self, message: str) -> None:
        """
        Show a toast reporting what happened.

        The message is read as markup, so any name the user wrote has to go
        through `_task_name` or `_place_name`, which style and escape it.
        """
        self.notify(message)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """
        Disable the board's actions that the focused thing has no use for.

        A card staged for a move keeps the staging keys; a focused column header
        keeps only what moves between columns and back to the cards, so that the
        column's own actions are all it answers to; a column being named gives up
        everything to the field.

        A disabled binding is not matched, so the key bubbles past the board
        rather than doing something that was not asked for — and the footer
        drops it, so the hints follow focus.
        """
        _ = parameters

        if self.move_mode:
            return action in MOVE_MODE_ACTIONS

        focused = self.app.focused
        if isinstance(focused, ColumnHeader):
            return action in HEADER_ACTIONS
        if focused is not None and isinstance(focused.parent, ColumnHeader):
            return False

        return True

    @contextmanager
    def _service_errors(self, action: str) -> Iterator[None]:
        """Report a failed service call as a toast instead of tearing down the app."""
        try:
            yield
        except Exception as exc:
            description = str(exc) or exc.__class__.__name__
            logging.error("TUI %s failed: %s", action, description)
            self.notify(description, title=action, severity="error")


def _cards_per_page(column: ColumnView) -> int:
    """
    Return how many of a column's cards fit on screen at once.

    Cards vary in height with their metadata, so this works from the average
    height of the ones the column is holding rather than assuming a size.
    """
    count = len(column.tasks)
    if count == 0:
        return 1

    card_height = max(1, column.virtual_size.height // count)
    return max(1, column.container_size.height // card_height)


def _styled(name: str, style: str) -> str:
    """
    Return `name` marked up in `style`.

    Titles and names come from the user, so they are escaped: a `[` in one
    would otherwise be read as the start of a style tag.
    """
    return f"[{style}]{escape(name)}[/]"


def _task_name(title: str) -> str:
    """Return a task's title in the accent colour."""
    return _styled(title, "$accent")


def _place_name(name: str) -> str:
    """Return a column or board name in the primary colour."""
    return _styled(name, "$primary")


def _path_name(path: Path) -> str:
    """Return a path muted, the way `TaskHeading` renders the path of a task."""
    return _styled(str(path), "$text-muted")


