"""Protocol for services that provide REPL completion data."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from kanban.models.slug import Slug

from ..models import Board, Column, Task, TaskFilter


class CompletionDataSource(Protocol):
    """The subset of KanbanService used by REPL completion."""

    def get_boards(self) -> list[Board]:
        ...

    def get_columns(self, board: Path | Slug | None) -> list[Column]:
        ...

    def get_tasks(self, path: Path | None = None, filter: TaskFilter = TaskFilter()) -> list[Task]:
        ...

    def path_components(self, path: str | Path | Slug | None = None) -> tuple[Slug | None, Slug | None, Slug | None]:
        ...

    def get_tags(self, board: Slug | None = None) -> list[str]:
        ...

    def get_assigned_tos(self, board: Slug | None = None) -> list[str]:
        ...

    @property
    def working_board(self) -> Slug | None:
        ...
