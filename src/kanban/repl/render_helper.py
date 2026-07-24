
from ..models import Board, Column, Slug
from ..services.kanban import KanbanService

class RenderHelper:
    def __init__(self, service: KanbanService):
        self.svc = service

    def board_for_slug(self, slug: Slug) -> Board:
        """Given a board slug, return the corresponding board."""
        return self.svc.get_board(slug)
    
    def column_for_slug(self, column_slug: Slug) -> Column:
        """Given a column slug, return the corresponding column resolved against the working board."""
        return self.svc.get_column(column_slug)
