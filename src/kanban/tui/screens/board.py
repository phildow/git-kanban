"""
The board screen: the TUI's default screen.

The screen owns all interaction with the kanban service.  Widgets render what
they are handed and never query the service themselves.  The filesystem stays
the source of truth: the screen re-fetches after every mutation of its own,
when the terminal regains focus, and on demand with `r`.
"""

from __future__ import annotations

import logging
import shlex
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, ListView, Static

from ...models import Board, Column, Slug, Task
from ...services.kanban import (
    KanbanService,
    TaskCreateParams,
    TaskUnsetParams,
    TaskUpdateParams,
)
from ..formatting import board_subtitle
from ..widgets import (
    ColumnView,
    CommandBar,
    FilterBar,
    ModeBar,
    SidebarPanel,
)
from .board_switcher import BoardChoice, BoardSwitcherScreen, CreateBoard
from .confirm import ConfirmScreen
from .help import HelpScreen
from .output import OutputScreen
from .task_detail import TaskDetailScreen
from .task_form import TaskFormResult, TaskFormScreen

if TYPE_CHECKING:
    from ..app import KanbanApp

MOVE_HINTS = "  ←/→ h/l  column    ↑/↓ j/k  position    enter  commit    esc  cancel"
FILTER_HINTS = "  type to filter    enter  keep filter    esc  clear"
COMMAND_HINTS = "  REPL syntax    enter  run    esc  cancel"

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

    BINDINGS = [
        Binding("left,h", "nav_left", "Column", show=True),
        Binding("right,l", "nav_right", "Column", show=False),
        Binding("up,k", "nav_up", "Card", show=False),
        Binding("down,j", "nav_down", "Card", show=False),
        Binding("enter", "activate", "Open", show=False),
        Binding("n", "new_task", "New", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("m", "move_task", "Move", show=True),
        Binding("b", "switch_board", "Board", show=True),
        Binding("slash", "filter", "Filter", show=True),
        Binding("colon", "command", "Command", show=True),
        Binding("s", "toggle_sidebar", "Sidebar", show=True),
        Binding("c", "toggle_density", "Density", show=False),
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
        self._filter: str = ""
        self._move: MoveState | None = None

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
        yield Footer()

    async def on_mount(self) -> None:
        """Load the board once the screen is attached."""
        await self.reload()

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def column_views(self) -> list[ColumnView]:
        """Return the mounted column views, left to right."""
        return list(self.query(ColumnView))

    @property
    def focused_column(self) -> ColumnView | None:
        """Return the focused column, falling back to the leftmost one."""
        focused = self.app.focused
        if isinstance(focused, ColumnView):
            return focused
        views = self.column_views
        return views[0] if views else None

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

    async def reload(self, select: Slug | None = None) -> None:
        """
        Re-query the service and rebuild the board.

        `select` highlights a task by slug once the rebuild is done; when it is
        omitted the current selection and focused column are preserved.
        """
        column = self.focused_column
        focus_column = column.column.slug if column is not None else None
        if select is None:
            selected = self.selected_task
            select = selected.slug if selected is not None else None

        self._fetch()
        await self._render_board(select=select, focus_column=focus_column)

        task_count = sum(len(tasks) for tasks in self._tasks.values())
        self.sub_title = board_subtitle(self._board, len(self._columns), task_count)

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
        if not self._filter:
            return tasks
        needle = self._filter
        return [task for task in tasks if _matches(task, needle)]

    async def _render_board(self, *, select: Slug | None = None, focus_column: Slug | None = None) -> None:
        """Rebuild the column views from the fetched data and restore focus."""
        container = self.query_one("#columns", Horizontal)
        await container.remove_children()

        if not self._columns:
            message = (
                "No boards yet — create one with `:` then `create --board <name>`"
                if not self._boards
                else "This board has no columns"
            )
            await container.mount(Static(message, classes="-empty"))
            return

        views = [
            ColumnView(column, id=f"column-{column.slug}") for column in self._columns
        ]
        await container.mount_all(views)

        for view in views:
            await view.set_tasks(self._visible(view.column.slug), dense=self.dense)

        self._restore_focus(views, select=select, focus_column=focus_column)

    def _restore_focus(
        self,
        views: list[ColumnView],
        *,
        select: Slug | None,
        focus_column: Slug | None,
    ) -> None:
        """Focus the column that held focus and re-highlight the selected task."""
        if select is not None:
            for view in views:
                if view.select_task(select):
                    view.focus()
                    return

        target = next(
            (view for view in views if view.column.slug == focus_column), views[0]
        )
        target.focus()

    async def _render_current(self, select: Slug | None = None) -> None:
        """Repopulate the columns from data already fetched, without touching the service."""
        views = self.column_views
        if not views:
            return

        column = self.focused_column
        focus_column = column.column.slug if column is not None else None

        for view in views:
            await view.set_tasks(self._visible(view.column.slug), dense=self.dense)

        self._restore_focus(views, select=select, focus_column=focus_column)

    def _reload_soon(self, select: Slug | None = None) -> None:
        """Schedule a reload from a synchronous context, such as a modal callback."""
        self.run_worker(self.reload(select), exclusive=False)

    def _render_soon(self, select: Slug | None = None) -> None:
        """Schedule a re-render from a synchronous context."""
        self.run_worker(self._render_current(select), exclusive=False)

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

    def _focus_column(self, delta: int) -> None:
        """Move focus `delta` columns, clamped to the ends of the board."""
        views = self.column_views
        if not views:
            return

        current = views.index(self.focused_column) if self.focused_column in views else 0
        target = max(0, min(current + delta, len(views) - 1))
        views[target].focus()

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
        task = self.selected_task
        if task is None:
            self.notify("No task selected", severity="warning")
            return
        self.app.push_screen(TaskDetailScreen(task))

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
            ConfirmScreen(f"Delete {task.path}?"),
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
                ),
            )

        if created is not None:
            self.notify(f"Created {created.path}")
            self._reload_soon(created.slug)

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
                ),
            )

            # update_task only ever sets values and unions tags, so emptied
            # fields and removed tags have to go through unset_task.
            unsets = TaskUnsetParams(
                assigned_to=result.assigned_to is None and task.assigned_to is not None,
                priority=result.priority is None and task.priority is not None,
                due_date=result.due_date is None and task.due_date is not None,
                tags=sorted(set(task.tags) - set(result.tags)),
            )
            if any([unsets.assigned_to, unsets.priority, unsets.due_date, unsets.tags]):
                updated = self.svc.unset_task(updated.path, unsets)

        if updated is not None:
            self.notify(f"Updated {updated.path}")
            self._reload_soon(updated.slug)

    def _delete_task(self, task: Task, confirmed: bool) -> None:
        """Delete `task` once the confirmation modal comes back positive."""
        if not confirmed:
            return

        deleted: Task | None = None
        with self._service_errors("delete"):
            deleted = self.svc.delete_task(task.path)

        if deleted is not None:
            self.notify(f"Deleted {deleted.path}")
            self._reload_soon()

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
        self.move_mode = True

    def _stage_column(self, delta: int) -> None:
        """Stage the card in an adjacent column, clamped to the ends of the board."""
        move = self._move
        if move is None:
            return

        target = max(0, min(move.column_index + delta, len(self._columns) - 1))
        if target == move.column_index:
            return

        move.column_index = target
        move.position = min(move.position, len(self._visible(self._columns[target].slug)))
        self._render_staged_soon()

    def _stage_position(self, delta: int) -> None:
        """Stage the card higher or lower within the staged column."""
        move = self._move
        if move is None:
            return

        limit = len(self._staged_tasks()[self._columns[move.column_index].slug]) - 1
        target = max(0, min(move.position + delta, max(limit, 0)))
        if target == move.position:
            return

        move.position = target
        self._render_staged_soon()

    def _staged_tasks(self) -> dict[Slug, list[Task]]:
        """Return the visible tasks with the moving card placed at its staged position."""
        staged = {column.slug: self._visible(column.slug) for column in self._columns}
        move = self._move
        if move is None:
            return staged

        for slug, tasks in staged.items():
            staged[slug] = [task for task in tasks if task.slug != move.task.slug]

        target = self._columns[move.column_index].slug
        position = max(0, min(move.position, len(staged[target])))
        staged[target].insert(position, move.task)
        return staged

    def _render_staged_soon(self) -> None:
        """Schedule a redraw of the staged arrangement."""
        self.run_worker(self._render_staged(), exclusive=False)

    async def _render_staged(self) -> None:
        """Redraw the columns showing where the card would land.  Writes nothing."""
        move = self._move
        if move is None:
            return

        staged = self._staged_tasks()
        for view in self.column_views:
            await view.set_tasks(staged[view.column.slug], dense=self.dense)

        views = self.column_views
        if not views:
            return

        target = views[move.column_index]
        target.index = min(move.position, max(len(target.tasks) - 1, 0))
        target.focus()

        card = target.card_for(move.task.slug)
        if card is not None:
            card.set_moving(True)

    def _commit_move(self) -> None:
        """Write the staged move: one move_task when the column changed, then reorder."""
        move = self._move
        if move is None:
            return

        task = move.task
        target = self._columns[move.column_index]
        moved: Task | None = None

        with self._service_errors("move"):
            if target.slug != task.column:
                task = self.svc.move_task(task.path, target.slug)
            self._reorder_to(task, move.position)
            moved = task

        self.move_mode = False
        self._move = None

        if moved is not None:
            self.notify(f"Moved to /{moved.board}/{target.slug}")
            self._reload_soon(moved.slug)
        else:
            self._reload_soon()

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
        """Leave move mode without writing anything, back where the card started."""
        move = self._move
        self.move_mode = False
        self._move = None
        self._render_soon(move.task.slug if move is not None else None)

    def watch_move_mode(self, move_mode: bool) -> None:
        """Lock the columns and swap the footer for the move-mode hints."""
        for view in self.column_views:
            view.locked = move_mode

        if move_mode:
            self._show_hints(MOVE_HINTS)
            self._render_staged_soon()
        else:
            self._hide_hints()

    # ── Board, sidebar, density ───────────────────────────────────────────────

    def action_switch_board(self) -> None:
        """Open the board switcher."""
        active = self._board.slug if self._board is not None else None
        self.app.push_screen(
            BoardSwitcherScreen(self._boards, active=active), self._switch_board
        )

    def _switch_board(self, choice: BoardChoice | None) -> None:
        """Act on the switcher's result: change board, create one, or do nothing."""
        if choice is None:
            return

        if isinstance(choice, CreateBoard):
            self._create_board(choice.name)
            return

        with self._service_errors("board"):
            self.svc.set_board(choice.slug)
        self._reload_soon()

    def _create_board(self, name: str) -> None:
        """Create a board with the default columns and switch to it."""
        board: Board | None = None
        with self._service_errors("board"):
            board = self.svc.create_board(name)
            self.svc.set_board(board.slug)

        if board is not None:
            self.notify(f"Created /{board.slug}")
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
        self._show_hints(FILTER_HINTS)

    def action_command(self) -> None:
        """Open the command bar."""
        bar = self.query_one(CommandBar)
        bar.add_class("-visible")
        bar.focus()
        self._show_hints(COMMAND_HINTS)

    def action_cancel(self) -> None:
        """Escape: close an open bar, clear the filter, or cancel a staged move."""
        command_bar = self.query_one(CommandBar)
        if command_bar.has_class("-visible"):
            command_bar.value = ""
            self._close_bar(command_bar)
            return

        filter_bar = self.query_one(FilterBar)
        if filter_bar.has_class("-visible") or self._filter:
            filter_bar.value = ""
            self._filter = ""
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

    def on_input_changed(self, event: FilterBar.Changed) -> None:
        """Live-filter the visible cards as the user types in the filter bar."""
        if not isinstance(event.input, FilterBar):
            return
        self._filter = event.value.strip().lower()
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

    def _show_hints(self, hints: str) -> None:
        """Swap the footer for a contextual hint bar."""
        mode_bar = self.mode_bar
        if mode_bar is None:
            return
        mode_bar.show(hints)
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

    @contextmanager
    def _service_errors(self, action: str) -> Iterator[None]:
        """Report a failed service call as a toast instead of tearing down the app."""
        try:
            yield
        except Exception as exc:
            description = str(exc) or exc.__class__.__name__
            logging.error("TUI %s failed: %s", action, description)
            self.notify(description, title=action, severity="error")


def _matches(task: Task, needle: str) -> bool:
    """Return True when `needle` appears in a task's title, assignee, or tags."""
    haystack = [task.title.lower(), task.slug.lower()]
    if task.assigned_to:
        haystack.append(task.assigned_to.lower())
    haystack.extend(tag.lower() for tag in task.tags)
    return any(needle in value for value in haystack)
