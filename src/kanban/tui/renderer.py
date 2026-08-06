"""A renderer that captures command output instead of printing it."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from io import StringIO
from typing import Any

from rich.console import Console

from ..models import Board, Column, ReorderOp, Task, UserContext
from ..repl.rich_renderer import RichRenderer
from ..services.render_service import RenderService

# Wide enough that tables do not wrap awkwardly in the output panel.
CAPTURE_WIDTH = 100

# The render calls that report a command which changed nothing the board draws:
# every listing and lookup, and the config, whose values are not board data —
# the board re-reads the settings it draws from after every command instead, so
# a display setting takes effect without a rebuild.  Named here so a test can
# hold the two halves of the interface together — every render call is either
# one of these or one of the overrides below, and a command added to the one
# without the other is a command the board would draw stale.
READ_ONLY_RENDERERS = frozenset(
    {
        "render_board_list",
        "render_board_info",
        "render_column_list",
        "render_column_info",
        "render_task_list",
        "render_task_view",
        "render_task_info",
        "render_search",
        "render_fields",
        "render_fields_list",
        "render_log",
        "render_status",
        "render_set_config",
        "render_get_config",
        "render_list_config",
    }
)


@dataclass(frozen=True)
class CommandEffect:
    """
    What a command changed, as much of it as the board needs to redraw.

    `tasks` holds the tasks a command wrote, each carrying the board and column
    it ended up in — enough for the board to redraw those columns and no others.
    `structural` marks a change that cannot be scoped that way: a board or
    column created, renamed, reordered, or removed, which leaves the board no
    choice but to rebuild.  An effect with neither is a command that changed
    nothing on screen.
    """

    tasks: tuple[Task, ...] = ()
    structural: bool = False

    @property
    def is_empty(self) -> bool:
        """Return True when nothing the board draws has changed."""
        return not self.tasks and not self.structural


class TUIRenderer(RichRenderer):
    """
    The REPL's renderer, redirected into a buffer, recording what it renders.

    The TUI owns the terminal, so commands run from the command bar cannot
    print.  This renderer reuses every REPL rendering rule and only changes
    where the output goes; the board screen drains the buffer and shows it in
    the panel above the command bar.

    It also notes what each command changed.  The handlers hand the renderer the
    domain object the service returned, which is the last place the two are
    together: the board screen sees a line of text and a parsed command line,
    neither of which says which column a task ended up in.  Draining that record
    alongside the output is what lets the board redraw the columns a command
    touched rather than the whole of itself.
    """

    def __init__(self, render_service: RenderService) -> None:
        """Create a renderer that writes into an internal buffer."""
        super().__init__(render_service=render_service)
        self._buffer = StringIO()
        self._effect = CommandEffect()
        self.console = Console(file=self._buffer, width=CAPTURE_WIDTH, color_system="auto", highlight=False)

    def _emit(self, args: argparse.Namespace, value: Any) -> None:
        """Write a renderable into the buffer rather than to the terminal."""
        if value is None or self._silent:
            return
        self.console.print(value)

    def take_output(self) -> str:
        """Return everything rendered since the last call and reset the buffer."""
        output = self._buffer.getvalue()
        self._buffer.seek(0)
        self._buffer.truncate(0)
        return output

    def take_effect(self) -> CommandEffect:
        """Return what has been changed since the last call and reset the record."""
        effect = self._effect
        self._effect = CommandEffect()
        return effect

    def _record_task(self, task: Task) -> None:
        """Note a task a command wrote, for the board to redraw its column."""
        self._effect = replace(self._effect, tasks=self._effect.tasks + (task,))

    def _record_structural(self) -> None:
        """Note a change the board cannot scope to the columns it draws."""
        self._effect = replace(self._effect, structural=True)

    # ── Structural changes ────────────────────────────────────────────────────
    #
    # A board or column arriving, leaving, changing name, or changing place.
    # None of these is confined to columns already on screen, so each of them
    # rebuilds the board.

    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        """Report an initialization; only one that succeeded changed anything."""
        super().render_init(args, result)
        if result:
            self._record_structural()

    def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
        """Report the working board, which is the whole of what the board draws."""
        super().render_set_board(args, result)
        self._record_structural()

    def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
        """Report a created board."""
        super().render_board_create(args, result)
        self._record_structural()

    def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
        """Report a renamed board."""
        super().render_board_rename(args, result)
        self._record_structural()

    def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
        """Report a deleted board."""
        super().render_board_delete(args, result)
        self._record_structural()

    def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
        """Report a created column."""
        super().render_column_create(args, result)
        self._record_structural()

    def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
        """Report a renamed column."""
        super().render_column_rename(args, result)
        self._record_structural()

    def render_column_reorder(
        self, args: argparse.Namespace, result: list[Column]
    ) -> None:
        """Report the reordered columns."""
        super().render_column_reorder(args, result)
        self._record_structural()

    def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
        """Report a deleted column."""
        super().render_column_delete(args, result)
        self._record_structural()

    # ── Task changes ──────────────────────────────────────────────────────────
    #
    # Each of these reports the task as it now stands, naming the board and
    # column holding it — which is what the board scopes a redraw to.

    def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
        """Report a created task."""
        super().render_task_create(args, result)
        self._record_task(result)

    def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
        """Report an edited task."""
        super().render_task_edit(args, result)
        self._record_task(result)

    def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
        """Report an updated task, which an update may also have moved."""
        super().render_task_update(args, result)
        self._record_task(result)

    def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
        """Report a renamed task, under its new slug."""
        super().render_task_rename(args, result)
        self._record_task(result)

    def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
        """Report a moved task, in the column it landed in."""
        super().render_task_move(args, result)
        self._record_task(result)

    def render_task_reorder(
        self, args: argparse.Namespace, task_op: tuple[Task, ReorderOp]
    ) -> None:
        """Report a task moved within its column."""
        super().render_task_reorder(args, task_op)
        self._record_task(task_op[0])

    def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
        """Report a deleted task, which names the column it was deleted from."""
        super().render_task_delete(args, result)
        self._record_task(result)

    def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
        """Report a task assigned or unassigned."""
        super().render_task_assign(args, result)
        self._record_task(result)

    def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
        """Report a task tagged or untagged."""
        super().render_task_tag(args, result)
        self._record_task(result)

    def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
        """Report a task commented on."""
        super().render_task_comment(args, result)
        self._record_task(result)
