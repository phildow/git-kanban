"""Tests for FilesystemRepository.get_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import Column
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound, ColumnNotFound


class TestFilesystemGetColumn(unittest.TestCase):
    """get_column returns a Column for an existing directory, or raises."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()
        (self.repo.boards_dir / "alpha" / "done").mkdir()
        (self.repo.boards_dir / "alpha" / "todo").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_column(self) -> None:
        """Returns a Column with the correct name and board."""
        col = self.repo.get_column("alpha", "todo")
        self.assertIsInstance(col, Column)
        self.assertEqual(col.name, "todo")
        self.assertEqual(col.board, "alpha")

    def test_position_reflects_alphabetical_order(self) -> None:
        """Position is the 0-based alphabetical index among sibling columns."""
        done = self.repo.get_column("alpha", "done")
        todo = self.repo.get_column("alpha", "todo")
        self.assertEqual(done.position, 0)
        self.assertEqual(todo.position, 1)

    def test_task_count_is_zero_when_empty(self) -> None:
        """task_count is 0 when the column directory contains no files."""
        col = self.repo.get_column("alpha", "todo")
        self.assertEqual(col.task_count, 0)

    def test_task_count_reflects_number_of_files(self) -> None:
        """task_count counts non-hidden files in the column directory."""
        (self.repo.boards_dir / "alpha" / "todo" / "fix-bug.md").touch()
        (self.repo.boards_dir / "alpha" / "todo" / "add-tests.md").touch()
        col = self.repo.get_column("alpha", "todo")
        self.assertEqual(col.task_count, 2)

    def test_task_count_ignores_hidden_files(self) -> None:
        """Hidden files are not counted toward task_count."""
        (self.repo.boards_dir / "alpha" / "todo" / ".metadata").touch()
        (self.repo.boards_dir / "alpha" / "todo" / "fix-bug.md").touch()
        col = self.repo.get_column("alpha", "todo")
        self.assertEqual(col.task_count, 1)

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_column("missing", "todo")

    def test_raises_when_column_missing(self) -> None:
        """Raises ColumnNotFound when the column does not exist on the board."""
        with self.assertRaises(ColumnNotFound):
            self.repo.get_column("alpha", "missing")

    def test_raises_for_hidden_directory(self) -> None:
        """Hidden directories are not valid columns."""
        (self.repo.boards_dir / "alpha" / ".hidden").mkdir()
        with self.assertRaises(ColumnNotFound):
            self.repo.get_column("alpha", ".hidden")


if __name__ == "__main__":
    unittest.main()
