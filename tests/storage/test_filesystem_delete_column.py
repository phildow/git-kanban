"""Tests for FilesystemRepository.delete_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardNotFound, ColumnNotFound


class TestFilesystemDeleteColumn(unittest.TestCase):
    """delete_column removes the column directory tree or raises on missing board/column."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()
        (self.repo.boards_dir / "alpha" / "todo").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_removes_column_directory(self) -> None:
        """Column directory no longer exists after deletion."""
        self.repo.delete_column("alpha", "todo")
        self.assertFalse((self.repo.boards_dir / "alpha" / "todo").exists())

    def test_removes_nested_contents(self) -> None:
        """Task files inside the column are also removed."""
        (self.repo.boards_dir / "alpha" / "todo" / "fix-bug.md").touch()
        (self.repo.boards_dir / "alpha" / "todo" / "add-tests.md").touch()
        self.repo.delete_column("alpha", "todo")
        self.assertFalse((self.repo.boards_dir / "alpha" / "todo").exists())

    def test_does_not_affect_other_columns(self) -> None:
        """Deleting one column leaves sibling columns untouched."""
        (self.repo.boards_dir / "alpha" / "done").mkdir()
        self.repo.delete_column("alpha", "todo")
        self.assertTrue((self.repo.boards_dir / "alpha" / "done").is_dir())

    def test_does_not_affect_board(self) -> None:
        """The board directory itself is preserved."""
        self.repo.delete_column("alpha", "todo")
        self.assertTrue((self.repo.boards_dir / "alpha").is_dir())

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.delete_column("missing", "todo")

    def test_raises_when_column_missing(self) -> None:
        """Raises ColumnNotFound when the column does not exist on the board."""
        with self.assertRaises(ColumnNotFound):
            self.repo.delete_column("alpha", "missing")


if __name__ == "__main__":
    unittest.main()
