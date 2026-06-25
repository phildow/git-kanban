"""Tests for FilesystemRepository.get_columns."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from models import Column
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound


class TestFilesystemGetColumns(unittest.TestCase):
    """get_columns reads column directories from a board directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_column(self, board: str, slug: str, name: str | None = None) -> None:
        """Create a column directory with the metadata fields required by get_columns."""
        (self.repo.boards_dir / board / slug).mkdir()
        display_name = name or slug
        self.repo.set_column_metadata(board, slug, "fields.name", display_name)
        self.repo.set_column_metadata(board, slug, "fields.slug", slug)
        self.repo.set_column_metadata(board, slug, "fields.id", str(uuid4()))

    def test_returns_empty_list_when_no_columns(self) -> None:
        """Returns an empty list when the board has no column directories."""
        self.assertEqual(self.repo.get_columns("alpha"), [])

    def test_returns_column_for_each_directory(self) -> None:
        """One Column per subdirectory, named after the directory."""
        self._make_column("alpha", "todo")
        self._make_column("alpha", "done")
        names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertIn("todo", names)
        self.assertIn("done", names)

    def test_columns_are_sorted_by_name(self) -> None:
        """Columns are returned in alphabetical order."""
        self._make_column("alpha", "todo")
        self._make_column("alpha", "done")
        columns = self.repo.get_columns("alpha")
        self.assertEqual([c.name for c in columns], ["done", "todo"])

    def test_positions_reflect_sort_order(self) -> None:
        """Position values match the alphabetical index of each column."""
        self._make_column("alpha", "todo")
        self._make_column("alpha", "done")
        columns = self.repo.get_columns("alpha")
        for i, col in enumerate(columns):
            self.assertEqual(col.position, i)

    def test_ignores_hidden_directories(self) -> None:
        """Directories starting with `.` are excluded."""
        (self.repo.boards_dir / "alpha" / ".hidden").mkdir()
        self._make_column("alpha", "todo")
        names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(names, ["todo"])

    def test_ignores_files(self) -> None:
        """Plain files are not returned as columns."""
        (self.repo.boards_dir / "alpha" / "not-a-column.md").touch()
        self._make_column("alpha", "todo")
        names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(names, ["todo"])

    def test_returns_column_dataclass_with_correct_board(self) -> None:
        """Each result is a Column with the correct board name."""
        self._make_column("alpha", "todo")
        col = self.repo.get_columns("alpha")[0]
        self.assertIsInstance(col, Column)
        self.assertEqual(col.board, "alpha")

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_columns("missing")


if __name__ == "__main__":
    unittest.main()
