"""Tests for FilesystemRepository.get_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import Board
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound


class TestFilesystemGetBoard(unittest.TestCase):
    """get_board finds a board directory and returns a Board, or raises."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_board_for_existing_directory(self) -> None:
        """A board directory that exists is returned as a Board."""
        (self.repo.boards_dir / "alpha").mkdir()
        board = self.repo.get_board("alpha")
        self.assertIsInstance(board, Board)
        self.assertEqual(board.name, "alpha")

    def test_raises_when_board_missing(self) -> None:
        """Requesting a non-existent board raises BoardNotFound."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_board("missing")

    def test_raises_for_hidden_directory(self) -> None:
        """Hidden directories are not valid boards."""
        (self.repo.boards_dir / ".hidden").mkdir()
        with self.assertRaises(BoardNotFound):
            self.repo.get_board(".hidden")

    def test_raises_when_path_is_a_file(self) -> None:
        """A file with the board name is not a valid board."""
        (self.repo.boards_dir / "not-a-board").touch()
        with self.assertRaises(BoardNotFound):
            self.repo.get_board("not-a-board")

    def test_returns_board_with_empty_columns(self) -> None:
        """Returned Board has an empty columns list (columns loaded separately)."""
        (self.repo.boards_dir / "alpha").mkdir()
        board = self.repo.get_board("alpha")
        self.assertEqual(board.columns, [])


if __name__ == "__main__":
    unittest.main()
