"""Shared renderer interface for CLI and REPL renderers."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Board, Column, ReorderOp, Task, UserContext
    from ..services.kanban import GitCommit, KanbanStatus


class ObjectField(StrEnum):
    """A field of a board, column, or task that a command can report on its own."""

    PATH = "path"
    ID = "id"


# The order fields are reported in, whatever order they were asked for.
FIELD_ORDER: tuple[ObjectField, ...] = (ObjectField.PATH, ObjectField.ID)


def field_value(result: Board | Column | Task, field: ObjectField) -> str:
    """Return one field of a board, column, or task as the text to report."""
    if field is ObjectField.PATH:
        return str(result.path)
    return str(result.id)


class CommandRenderer(ABC):
    """Common rendering interface used by CLI and REPL renderers."""

    # Set only for the duration of `silenced`.  A renderer that records what it
    # renders — the TUI's does — is still run while silent, for that record.
    _silent: bool = False

    @contextmanager
    def silenced(self) -> Iterator[None]:
        """
        Run the renderer for whatever it records rather than for its output.

        Every implementation drops what it would emit while this is held.  It is
        what lets one renderer stand in front of another, as `FieldRenderer`
        does, without the renderer behind it losing the record it keeps of what
        a command changed.
        """
        previous = self._silent
        self._silent = True
        try:
            yield
        finally:
            self._silent = previous

    @abstractmethod
    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        ...

    @abstractmethod
    def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
        ...

    @abstractmethod
    def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
        ...

    @abstractmethod
    def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
        ...

    @abstractmethod
    def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
        ...

    @abstractmethod
    def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
        ...

    @abstractmethod
    def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
        ...

    @abstractmethod
    def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
        ...

    @abstractmethod
    def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
        ...

    @abstractmethod
    def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
        ...

    @abstractmethod
    def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
        ...

    @abstractmethod
    def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
        ...

    @abstractmethod
    def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
        ...

    @abstractmethod
    def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
        ...

    @abstractmethod
    def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_view(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_info(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, ReorderOp]) -> None:
        ...

    @abstractmethod
    def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
        ...

    @abstractmethod
    def render_fields(self, args: argparse.Namespace, result: Board | Column | Task, fields: tuple[ObjectField, ...]) -> None:
        ...

    @abstractmethod
    def render_fields_list(self, args: argparse.Namespace, result: Sequence[Board | Column | Task], fields: tuple[ObjectField, ...]) -> None:
        ...

    @abstractmethod
    def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
        ...

    @abstractmethod
    def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
        ...

    @abstractmethod
    def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
        ...

    @abstractmethod
    def render_set_config(self, args: argparse.Namespace, result: str | None) -> None:
        ...

    @abstractmethod
    def render_get_config(self, args: argparse.Namespace, result: str | None) -> None:
        ...

    @abstractmethod
    def render_list_config(self, args: argparse.Namespace, result: dict[str, str | None]) -> None:
        ...
