"""Tests for FilesystemRepository.create_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import Column
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound, ColumnAlreadyExists


class TestFilesystemCreateColumn(unittest.TestCase):
    """create_column creates a subdirectory inside the board directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_creates_directory(self) -> None:
        """A subdirectory is created inside the board directory."""
        self.repo.create_column("alpha", "todo")
        self.assertTrue((self.repo.boards_dir / "alpha" / "todo").is_dir())

    def test_returns_column(self) -> None:
        """Returns a Column with the correct name and board."""
        col = self.repo.create_column("alpha", "todo")
        self.assertIsInstance(col, Column)
        self.assertEqual(col.name, "todo")
        self.assertEqual(col.board, "alpha")

    def test_position_is_zero_for_first_column(self) -> None:
        """First column in a board gets position 0."""
        col = self.repo.create_column("alpha", "todo")
        self.assertEqual(col.position, 0)

    def test_position_increments_for_subsequent_columns(self) -> None:
        """Each subsequent column gets the next position."""
        col1 = self.repo.create_column("alpha", "todo")
        col2 = self.repo.create_column("alpha", "in-progress")
        self.assertEqual(col1.position, 0)
        self.assertEqual(col2.position, 1)

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board directory does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.create_column("missing", "todo")

    def test_raises_when_column_already_exists(self) -> None:
        """Raises ColumnAlreadyExists when the column directory already exists."""
        self.repo.create_column("alpha", "todo")
        with self.assertRaises(ColumnAlreadyExists):
            self.repo.create_column("alpha", "todo")


if __name__ == "__main__":
    unittest.main()
