"""Tests for FilesystemRepository.board_exists."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository


class TestFilesystemBoardExists(unittest.TestCase):
    """board_exists returns True only for non-hidden board directories."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_false_when_missing(self) -> None:
        """Returns False when no directory with that name exists."""
        self.assertFalse(self.repo.board_exists("alpha"))

    def test_returns_true_when_directory_exists(self) -> None:
        """Returns True when a matching directory is present."""
        (self.repo.boards_dir / "alpha").mkdir()
        self.assertTrue(self.repo.board_exists("alpha"))

    def test_returns_false_for_hidden_directory(self) -> None:
        """Hidden directories are not valid boards."""
        (self.repo.boards_dir / ".hidden").mkdir()
        self.assertFalse(self.repo.board_exists(".hidden"))

    def test_returns_false_for_file(self) -> None:
        """A file with the board name is not a board."""
        (self.repo.boards_dir / "not-a-board").touch()
        self.assertFalse(self.repo.board_exists("not-a-board"))


if __name__ == "__main__":
    unittest.main()
