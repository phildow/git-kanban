"""Tests for FilesystemRepository.create_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.models import Board
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardAlreadyExists


class TestFilesystemCreateBoard(unittest.TestCase):
    """create_board creates a directory and returns a Board, or raises on collision."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_creates_directory(self) -> None:
        """A directory named after the board is created inside boards_dir."""
        self.repo.create_board("alpha", slug="alpha")
        self.assertTrue((self.repo.boards_dir / "alpha").is_dir())

    def test_returns_board(self) -> None:
        """Returns a Board with the given name and an empty columns list."""
        board = self.repo.create_board("alpha", slug="alpha")
        self.assertIsInstance(board, Board)
        self.assertEqual(board.name, "alpha")
        self.assertEqual(board.column_count, 0)

    def test_writes_name_to_metadata(self) -> None:
        """Board name is written to the fields.name key in the board .metadata file."""
        self.repo.create_board("alpha", slug="alpha")
        name = self.repo.get_board_metadata("alpha", "fields.name")
        self.assertEqual(name, "alpha")

    def test_writes_slug_to_metadata(self) -> None:
        """Board slug is written to the fields.slug key in the board .metadata file."""
        self.repo.create_board("alpha", slug="alpha")
        slug = self.repo.get_board_metadata("alpha", "fields.slug")
        self.assertEqual(slug, "alpha")

    def test_writes_slug_to_metadata_with_spaces(self) -> None:
        """Board slug is kebab-cased from the name when the name contains spaces."""
        self.repo.create_board("my project", slug="my-project")
        slug = self.repo.get_board_metadata("my-project", "fields.slug")
        self.assertEqual(slug, "my-project")

    def test_raises_when_board_already_exists(self) -> None:
        """Creating a board whose directory already exists raises BoardAlreadyExists."""
        self.repo.create_board("alpha", slug="alpha")
        with self.assertRaises(BoardAlreadyExists):
            self.repo.create_board("alpha", slug="alpha")


if __name__ == "__main__":
    unittest.main()
