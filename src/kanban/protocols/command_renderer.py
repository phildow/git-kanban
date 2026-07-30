"""Shared renderer interface for CLI and REPL renderers."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Board, Column, Task, UserContext
    from ..services.kanban import GitCommit, KanbanStatus


class CommandRenderer(ABC):
    """Common rendering interface used by CLI and REPL renderers."""

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
    def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
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
    def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
        ...

    @abstractmethod
    def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
        ...

    @abstractmethod
    def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
        ...

    @abstractmethod
    def render_set_config(self, args: argparse.Namespace, result: None) -> None:
        ...

    @abstractmethod
    def render_get_config(self, args: argparse.Namespace, result: str) -> None:
        ...
