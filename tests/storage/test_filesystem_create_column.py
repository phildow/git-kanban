"""Tests for FilesystemRepository.create_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.models import Column
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.kanban import BoardNotFound, ColumnAlreadyExists


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
        self.repo.create_column("alpha", "todo", slug="todo")
        self.assertTrue((self.repo.boards_dir / "alpha" / "todo").is_dir())

    def test_returns_column(self) -> None:
        """Returns a Column with the correct name and board."""
        col = self.repo.create_column("alpha", "todo", slug="todo")
        self.assertIsInstance(col, Column)
        self.assertEqual(col.name, "todo")
        self.assertEqual(col.board, "alpha")

    def test_position_is_zero_for_first_column(self) -> None:
        """First column in a board gets position 0."""
        col = self.repo.create_column("alpha", "todo", slug="todo")
        self.assertEqual(col.position, 0)

    def test_position_increments_for_subsequent_columns(self) -> None:
        """Each subsequent column gets the next position."""
        col1 = self.repo.create_column("alpha", "todo", slug="todo")
        col2 = self.repo.create_column("alpha", "in-progress", slug="in-progress")
        self.assertEqual(col1.position, 0)
        self.assertEqual(col2.position, 1)

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board directory does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.create_column("missing", "todo", slug="todo")

    def test_raises_when_column_already_exists(self) -> None:
        """Raises ColumnAlreadyExists when the column directory already exists."""
        self.repo.create_column("alpha", "todo", slug="todo")
        with self.assertRaises(ColumnAlreadyExists):
            self.repo.create_column("alpha", "todo", slug="todo")

    def test_fields_name_written_to_metadata(self) -> None:
        """create_column writes the column name to fields.name in the .metadata file."""
        self.repo.create_column("alpha", "todo", slug="todo")
        value = self.repo.get_column_metadata("alpha", "todo", "fields.name")
        self.assertEqual(value, "todo")

    def test_fields_name_written_for_each_column(self) -> None:
        """fields.name is independent per column and reflects each column's name."""
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "in-progress", slug="in-progress")
        self.assertEqual(self.repo.get_column_metadata("alpha", "todo", "fields.name"), "todo")
        self.assertEqual(self.repo.get_column_metadata("alpha", "in-progress", "fields.name"), "in-progress")

    def test_fields_name_survives_reload(self) -> None:
        """fields.name is still readable from a fresh repository instance."""
        self.repo.create_column("alpha", "todo", slug="todo")
        fresh = FilesystemRepository(root=self.root)
        value = fresh.get_column_metadata("alpha", "todo", "fields.name")
        self.assertEqual(value, "todo")


if __name__ == "__main__":
    unittest.main()
