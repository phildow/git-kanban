"""Tests for KanbanService.create_board column creation behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import UserContext
from services.git import GitService
from services.index import IndexService
from services.kanban import KanbanService
from storage.memory import InMemoryRepository


class TestKanbanServiceCreateBoard(unittest.TestCase):
    """create_board creates the board and the requested columns."""

    def setUp(self) -> None:
        temp_dir = tempfile.gettempdir()
        self.repo = InMemoryRepository(root=Path(temp_dir))
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
            user_context=UserContext(),
        )

    def test_default_columns_are_created_when_none_passed(self) -> None:
        """Omitting columns creates the four standard columns."""
        self.svc.create_board("alpha")
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["todo", "in-progress", "in-review", "done"])

    def test_explicit_columns_are_created(self) -> None:
        """Columns passed explicitly are the ones created."""
        self.svc.create_board("alpha", columns=["backlog", "wip", "done"])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["backlog", "wip", "done"])

    def test_empty_columns_creates_no_columns(self) -> None:
        """Passing an empty list creates no columns."""
        self.svc.create_board("alpha", columns=[])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, [])

    def test_returned_board_has_correct_columns(self) -> None:
        """The returned Board carries the created Column objects."""
        board = self.svc.create_board("alpha", columns=["todo", "done"])
        self.assertEqual([c.name for c in board.columns], ["todo", "done"])

    def test_returned_board_has_default_columns_when_none_passed(self) -> None:
        """The returned Board carries all four default Column objects."""
        board = self.svc.create_board("alpha")
        self.assertEqual(
            [c.name for c in board.columns],
            ["todo", "in-progress", "in-review", "done"],
        )


if __name__ == "__main__":
    unittest.main()
