"""Tests for FilesystemRepository.get_boards."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import Board
from storage.filesystem import FilesystemRepository


class TestFilesystemListBoards(unittest.TestCase):
    """get_boards reads board directories from disk."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_empty_list_when_no_boards(self) -> None:
        """No subdirectories means an empty list."""
        self.assertEqual(self.repo.get_boards(), [])

    def test_returns_board_for_each_directory(self) -> None:
        """One Board per subdirectory, named after the directory."""
        (self.repo.boards_dir / "alpha").mkdir()
        (self.repo.boards_dir / "beta").mkdir()
        boards = self.repo.get_boards()
        self.assertEqual([b.name for b in boards], ["alpha", "beta"])

    def test_boards_are_sorted_by_name(self) -> None:
        """Boards are returned in alphabetical order."""
        (self.repo.boards_dir / "zebra").mkdir()
        (self.repo.boards_dir / "alpha").mkdir()
        boards = self.repo.get_boards()
        self.assertEqual([b.name for b in boards], ["alpha", "zebra"])

    def test_ignores_hidden_directories(self) -> None:
        """Directories starting with `.` are excluded."""
        (self.repo.boards_dir / ".hidden").mkdir()
        (self.repo.boards_dir / "alpha").mkdir()
        boards = self.repo.get_boards()
        self.assertEqual([b.name for b in boards], ["alpha"])

    def test_ignores_files(self) -> None:
        """Plain files in the boards directory are not returned as boards."""
        (self.repo.boards_dir / "not-a-board.txt").touch()
        (self.repo.boards_dir / "alpha").mkdir()
        boards = self.repo.get_boards()
        self.assertEqual([b.name for b in boards], ["alpha"])

    def test_returns_board_dataclass(self) -> None:
        """Each result is a Board instance with an empty columns list."""
        (self.repo.boards_dir / "alpha").mkdir()
        boards = self.repo.get_boards()
        self.assertIsInstance(boards[0], Board)
        self.assertEqual(boards[0].columns, [])


if __name__ == "__main__":
    unittest.main()
