"""Tests for `Board.filename` and `Board.path`."""

from __future__ import annotations

import unittest

from pathlib import Path
from uuid import uuid4

from kanban.models import Board


class TestBoardFilenameAndPath(unittest.TestCase):
    """Verifies the `filename` and `path` properties of `Board`."""

    def test_filename_is_slug(self):
        """`filename` returns the board's slug."""
        board = Board(id=uuid4(), name="My Project", slug="my-project")
        self.assertEqual(board.filename, "my-project")

    def test_path_is_absolute_and_includes_slug(self):
        """`path` is an absolute path containing just the board's slug."""
        board = Board(id=uuid4(), name="My Project", slug="my-project")
        self.assertEqual(board.path, Path("/my-project"))
        self.assertTrue(board.path.is_absolute())


if __name__ == "__main__":
    unittest.main()
