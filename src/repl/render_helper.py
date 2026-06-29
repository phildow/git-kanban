
from models import Slug
from services.kanban import KanbanService

class RenderHelper:
    def __init__(self, service: KanbanService):
        self.svc = service
        
    def board_name_from_slug(self, slug: Slug) -> str:
        """
        Given a board slug, return the corresponding board name.
        """
        boards = self.svc.get_boards()
        for board in boards:
            if board.slug == slug:
                return board.name
        raise ValueError(f"No board found with slug '{slug}'")

    def column_name_from_slug(self, board_slug: Slug, column_slug: Slug) -> str:
        """
        Given a board slug and a column slug, return the corresponding column name.
        """
        columns = self.svc.get_columns(board_slug)
        for column in columns:
            if column.slug == column_slug:
                return column.name
        raise ValueError(f"No column found with slug '{column_slug}' in board '{board_slug}'")
    