"""Shared renderer interface for CLI and REPL renderers."""

from __future__ import annotations

import argparse
from abc import ABC, abstractmethod

from ..models import UserContext


class CommandRenderer(ABC):
    """Common rendering interface used by CLI and REPL renderers."""

    @abstractmethod
    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        ...

    @abstractmethod
    def render_change_dir(self, args: argparse.Namespace, result: UserContext) -> None:
        ...

    @abstractmethod
    def render_board_list(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_board_create(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_board_rename(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_board_delete(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_column_list(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_column_create(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_column_rename(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_column_reorder(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_column_delete(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_list(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_create(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_show(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_edit(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_update(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_rename(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_move(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_reorder(self, args: argparse.Namespace, task_op) -> None:
        ...

    @abstractmethod
    def render_task_delete(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_task_assign(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_search(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_log(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_status(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_config_set(self, args: argparse.Namespace, result) -> None:
        ...

    @abstractmethod
    def render_config_get(self, args: argparse.Namespace, result) -> None:
        ...
