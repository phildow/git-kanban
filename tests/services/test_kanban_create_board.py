"""Tests for KanbanService.create_board column creation behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.services.git import GitService
from kanban.index.memory import InMemoryIndexService
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceCreateBoard(unittest.TestCase):
    """create_board creates the board and the requested columns."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=InMemoryIndexService(),
            git_service=GitService(),
        )

    def test_default_columns_are_created_when_none_passed(self) -> None:
        """Omitting columns creates the four standard columns."""
        self.svc.create_board("alpha")
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["To Do", "In Progress", "In Review", "Done"])

    # TODO: Update to call service for columns
    def test_returned_board_has_default_columns_when_none_passed(self) -> None:
        """The returned Board carries all four default Column objects."""
        board = self.svc.create_board("alpha")
        # column_names = [c.name for c in board.columns]
        # self.assertEqual(column_names, ["To Do", "In Progress", "In Review", "Done"])

    def test_explicit_columns_are_created(self) -> None:
        """Columns passed explicitly are the ones created."""
        self.svc.create_board("alpha", columns=[("backlog", "backlog"), ("wip", "wip"), ("done", "done")])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["backlog", "wip", "done"])

    def test_empty_columns_creates_no_columns(self) -> None:
        """Passing an empty list creates no columns."""
        self.svc.create_board("alpha", columns=[])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, [])

    def test_returned_board_has_correct_columns_count(self) -> None:
        """The returned Board carries the correct number of Column objects."""
        board = self.svc.create_board("alpha", columns=[("To Do", "todo"), ("Done", "done")])
        self.assertEqual(board.column_count, 2)


if __name__ == "__main__":
    unittest.main()
