"""Tests for FilesystemRepository.column_exists."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardNotFound


class TestFilesystemColumnExists(unittest.TestCase):
    """column_exists returns True only for non-hidden column directories."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_false_when_missing(self) -> None:
        """Returns False when no column directory with that name exists."""
        self.assertFalse(self.repo.column_exists("alpha", "todo"))

    def test_returns_true_when_directory_exists(self) -> None:
        """Returns True when a matching column directory is present."""
        (self.repo.boards_dir / "alpha" / "todo").mkdir()
        self.assertTrue(self.repo.column_exists("alpha", "todo"))

    def test_returns_false_for_hidden_directory(self) -> None:
        """Hidden directories are not valid columns."""
        (self.repo.boards_dir / "alpha" / ".hidden").mkdir()
        self.assertFalse(self.repo.column_exists("alpha", ".hidden"))

    def test_returns_false_for_file(self) -> None:
        """A file with the column name is not a column."""
        (self.repo.boards_dir / "alpha" / "todo").touch()
        self.assertFalse(self.repo.column_exists("alpha", "todo"))

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.column_exists("missing", "todo")


if __name__ == "__main__":
    unittest.main()
