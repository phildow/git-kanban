from pathlib import Path

from ..models import Board, Column, Slug
from .kanban import KanbanService

class RenderService:
    """
    Resolves lightweight domain lookups for renderers.

    Provides a narrow surface over `KanbanService` used by renderers to
    resolve slugs and paths to domain objects for display.
    """

    def __init__(self, service: KanbanService):
        self.svc = service

    def board_for_slug(self, slug: Slug) -> Board:
        """Given a board slug, return the corresponding board.

        Raises BoardNotFound if no board exists for the given slug.
        """
        return self.svc.get_board(slug)

    def column_for_slug(self, slug: Slug) -> Column:
        """Given a column slug, return the corresponding column resolved against the working board.

        Raises ColumnNotFound if no column exists for the given slug.
        """
        return self.svc.get_column(slug)

    def column_for_path(self, path: Path) -> Column:
        """Given a column path, return the corresponding column resolved against the working board.

        Raises ColumnNotFound if no column exists at the given path.
        """
        return self.svc.get_column(path)
