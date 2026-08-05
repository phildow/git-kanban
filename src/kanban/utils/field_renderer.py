"""
A renderer that reports a field of an object in place of the object.

`--path` and `--id` do not change what a command does, only what it prints, so
they are answered where output form is already decided — the renderer.  This one
stands in front of whichever renderer the command would otherwise have used and
replaces its output with the fields asked for, in a fixed order: the path first,
then the id.

It never prints anything itself.  The renderer behind it is asked to print the
fields, so the output goes wherever that renderer's output goes — the terminal
for the CLI and REPL, the capture buffer for the TUI — and takes that renderer's
form, a line per field or a JSON object.  That renderer is also still run, under
`silenced`, so whatever it records of what a command changed is recorded as
usual and only its output is dropped.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any

from ..models import Board, Column, Task, UserContext
from ..protocols.command_renderer import FIELD_ORDER, CommandRenderer, ObjectField
from ..services.kanban import GitCommit, KanbanStatus

# A renderer's rendering method, as this one calls it: the parsed arguments and
# whatever the command returned.  The second is `Any` because every one of them
# takes a different result type.
RenderCall = Callable[[argparse.Namespace, Any], None]


def fields_from_args(args: argparse.Namespace) -> tuple[ObjectField, ...]:
    """
    Return the fields `--path` and `--id` ask for, path first, empty if neither.

    The flags are only added to commands that return an object, so the arguments
    of a command that does not carries neither.
    """
    asked = {
        ObjectField.PATH: getattr(args, "show_path", False),
        ObjectField.ID: getattr(args, "show_id", False),
    }
    return tuple(field for field in FIELD_ORDER if asked[field])


class FieldRenderer(CommandRenderer):
    """Reports the fields of the object a command returned, in place of it."""

    def __init__(self, base: CommandRenderer, fields: tuple[ObjectField, ...]) -> None:
        """Stand in front of `base`, reporting `fields` of whatever it is handed."""
        self.base = base
        self.fields = fields

    def _object(self, call: RenderCall, args: argparse.Namespace, result: Board | Column | Task) -> None:
        """Run the wrapped renderer for its record alone, then report the fields."""
        with self.base.silenced():
            call(args, result)
        self.base.render_fields(args, result, self.fields)

    def _objects(self, call: RenderCall, args: argparse.Namespace, result: Sequence[Board | Column | Task]) -> None:
        """Report the fields of each object in a list the same way."""
        with self.base.silenced():
            call(args, result)
        self.base.render_fields_list(args, result, self.fields)

    # ── Initialisation and context ────────────────────────────────────────────
    #
    # Neither returns an object with a path and an id, so neither takes the
    # flags and neither is reached with this renderer in place.  They are passed
    # through rather than refused so the renderer remains a complete stand-in.

    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        """Pass an initialization through untouched."""
        self.base.render_init(args, result)

    def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
        """Pass the working board through untouched."""
        self.base.render_set_board(args, result)

    # ── Boards ────────────────────────────────────────────────────────────────

    def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
        """Report the fields of every board listed."""
        self._objects(self.base.render_board_list, args, result)

    def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
        """Report the fields of a created board."""
        self._object(self.base.render_board_create, args, result)

    def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
        """Report the fields of a board."""
        self._object(self.base.render_board_info, args, result)

    def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
        """Report the fields of a renamed board, under its new slug."""
        self._object(self.base.render_board_rename, args, result)

    def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
        """Report the fields of a deleted board."""
        self._object(self.base.render_board_delete, args, result)

    # ── Columns ───────────────────────────────────────────────────────────────

    def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
        """Report the fields of every column listed."""
        self._objects(self.base.render_column_list, args, result)

    def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
        """Report the fields of a column."""
        self._object(self.base.render_column_info, args, result)

    def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
        """Report the fields of a created column."""
        self._object(self.base.render_column_create, args, result)

    def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
        """Report the fields of a renamed column, under its new slug."""
        self._object(self.base.render_column_rename, args, result)

    def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
        """Report the fields of the columns in their new order."""
        self._objects(self.base.render_column_reorder, args, result)

    def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
        """Report the fields of a deleted column."""
        self._object(self.base.render_column_delete, args, result)

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
        """Report the fields of every task listed."""
        self._objects(self.base.render_task_list, args, result)

    def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a created task."""
        self._object(self.base.render_task_create, args, result)

    def render_task_view(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a task, in place of it and its body."""
        self._object(self.base.render_task_view, args, result)

    def render_task_info(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a task."""
        self._object(self.base.render_task_info, args, result)

    def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of an edited task."""
        self._object(self.base.render_task_edit, args, result)

    def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of an updated task."""
        self._object(self.base.render_task_update, args, result)

    def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a renamed task, under its new slug."""
        self._object(self.base.render_task_rename, args, result)

    def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a moved task, in the column it landed in."""
        self._object(self.base.render_task_move, args, result)

    def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
        """Report the fields of a task moved within its column."""
        with self.base.silenced():
            self.base.render_task_reorder(args, task_op)
        self.base.render_fields(args, task_op[0], self.fields)

    def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a deleted task."""
        self._object(self.base.render_task_delete, args, result)

    def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a task assigned or unassigned."""
        self._object(self.base.render_task_assign, args, result)

    def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a task tagged or untagged."""
        self._object(self.base.render_task_tag, args, result)

    def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
        """Report the fields of a task commented on."""
        self._object(self.base.render_task_comment, args, result)

    # ── Fields, search, log, status, config ───────────────────────────────────

    def render_fields(self, args: argparse.Namespace, result: Board | Column | Task, fields: tuple[ObjectField, ...]) -> None:
        """Report fields already asked for by field, which the base renderer prints."""
        self.base.render_fields(args, result, fields)

    def render_fields_list(self, args: argparse.Namespace, result: Sequence[Board | Column | Task], fields: tuple[ObjectField, ...]) -> None:
        """Report the fields of a list of objects the same way."""
        self.base.render_fields_list(args, result, fields)

    def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
        """Report the fields of every task found."""
        self._objects(self.base.render_search, args, result)

    def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
        """Pass a log through untouched; commits have neither field."""
        self.base.render_log(args, result)

    def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
        """Pass a status through untouched."""
        self.base.render_status(args, result)

    def render_set_config(self, args: argparse.Namespace, result: str | None) -> None:
        """Pass a set configuration value through untouched."""
        self.base.render_set_config(args, result)

    def render_get_config(self, args: argparse.Namespace, result: str | None) -> None:
        """Pass a configuration value through untouched."""
        self.base.render_get_config(args, result)

    def render_list_config(self, args: argparse.Namespace, result: dict[str, str | None]) -> None:
        """Pass the configuration through untouched."""
        self.base.render_list_config(args, result)


def for_fields(args: argparse.Namespace, base: CommandRenderer) -> CommandRenderer:
    """
    Return the renderer a command's arguments call for.

    `base` stands as it is unless --path or --id asks for fields alone, in which
    case it is put behind a FieldRenderer.
    """
    fields = fields_from_args(args)
    return FieldRenderer(base=base, fields=fields) if fields else base
