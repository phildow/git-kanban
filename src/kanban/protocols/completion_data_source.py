"""Protocol for services that provide REPL completion data."""

from __future__ import annotations

from typing import Protocol

from ..models import Board, Column, Task


class CompletionDataSource(Protocol):
    """The subset of KanbanService used by REPL completion."""

    def get_boards(self) -> list[Board]:
        ...

    def get_columns(self, board: str) -> list[Column]:
        ...

    def get_tasks(self, path: str | None = None) -> list[Task]:
        ...

    def path_components(self, path: str | None = None) -> tuple[str | None, str | None, str | None]:
        ...

    def get_tags(self, board: str | None = None) -> list[str]:
        ...

    def get_assigned_tos(self, board: str | None = None) -> list[str]:
        ...

    @property
    def working_board(self) -> str | None:
        ...
