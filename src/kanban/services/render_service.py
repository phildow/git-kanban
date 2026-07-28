from pathlib import Path

from ..models import Board, Column, Slug
from .kanban import KanbanService


class RenderService:
    """Resolves lightweight domain lookups for renderers.

    Provides a narrow surface over `KanbanService` used by renderers to
    resolve slugs and paths to domain objects for display.
    """

    def __init__(self, service: KanbanService):
        self.svc = service

    def board_for_slug(self, slug: Slug) -> Board | None:
        """Given a board slug, return the corresponding board or None if not found."""
        return self.svc.get_board(slug)

    def column_for_slug(self, slug: Slug) -> Column | None:
        """Given a column slug, return the corresponding column resolved against the working board, or None if not found."""
        return self.svc.get_column(slug)

    def column_for_path(self, path: Path) -> Column | None:
        """Given a column path, return the corresponding column resolved against the working board, or None if not found."""
        return self.svc.get_column(path)
