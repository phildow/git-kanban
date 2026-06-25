"""Tests for FilesystemRepository.rename_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from models import Column
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound, ColumnNotFound, ColumnAlreadyExists


class TestFilesystemRenameColumn(unittest.TestCase):
    """rename_column renames the column directory and returns the updated Column."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()
        self._make_column("alpha", "todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_column(self, board: str, slug: str, name: str | None = None) -> None:
        """Create a column directory with the metadata fields required by rename_column."""
        (self.repo.boards_dir / board / slug).mkdir()
        display_name = name or slug
        self.repo.set_column_metadata(board, slug, "fields.name", display_name)
        self.repo.set_column_metadata(board, slug, "fields.slug", slug)
        self.repo.set_column_metadata(board, slug, "fields.id", str(uuid4()))

    def test_renames_directory(self) -> None:
        """Old directory is gone and new directory exists after rename."""
        self.repo.rename_column("alpha", "todo", "backlog", new_slug="backlog")
        self.assertFalse((self.repo.boards_dir / "alpha" / "todo").exists())
        self.assertTrue((self.repo.boards_dir / "alpha" / "backlog").is_dir())

    def test_returns_column_with_new_name(self) -> None:
        """Returns a Column with the new name and correct board."""
        col = self.repo.rename_column("alpha", "todo", "backlog", new_slug="backlog")
        self.assertIsInstance(col, Column)
        self.assertEqual(col.name, "backlog")
        self.assertEqual(col.board, "alpha")

    def test_preserves_task_files(self) -> None:
        """Task files inside the column are preserved under the new name."""
        (self.repo.boards_dir / "alpha" / "todo" / "fix-bug.md").touch()
        self.repo.rename_column("alpha", "todo", "backlog", new_slug="backlog")
        self.assertTrue((self.repo.boards_dir / "alpha" / "backlog" / "fix-bug.md").is_file())

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.rename_column("missing", "todo", "backlog", new_slug="backlog")

    def test_raises_when_source_column_missing(self) -> None:
        """Raises ColumnNotFound when the source column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.repo.rename_column("alpha", "missing", "backlog", new_slug="backlog")

    def test_raises_when_target_column_exists(self) -> None:
        """Raises ColumnAlreadyExists when a column with the new name already exists."""
        (self.repo.boards_dir / "alpha" / "done").mkdir()
        with self.assertRaises(ColumnAlreadyExists):
            self.repo.rename_column("alpha", "todo", "done", new_slug="done")


if __name__ == "__main__":
    unittest.main()
