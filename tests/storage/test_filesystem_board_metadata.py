"""Tests for FilesystemRepository.get_board_metadata and set_board_metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository


class TestFilesystemBoardMetadata(unittest.TestCase):
    """Values written with set_board_metadata can be read back with get_board_metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("alpha")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_written_value_is_readable(self) -> None:
        """A value written with set_board_metadata is returned by get_board_metadata."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha Board")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha Board")

    def test_multiple_keys_in_same_section(self) -> None:
        """Multiple keys in the same section are stored and retrieved independently."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "info.description", "My board")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.description"), "My board")

    def test_multiple_sections(self) -> None:
        """Keys in different sections are stored and retrieved independently."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "settings.color", "blue")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha")
        self.assertEqual(self.repo.get_board_metadata("alpha", "settings.color"), "blue")

    def test_overwrite_existing_value(self) -> None:
        """Writing to an existing key replaces the previous value."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Old")
        self.repo.set_board_metadata("alpha", "info.display-name", "New")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "New")

    def test_set_none_removes_key(self) -> None:
        """Setting a value to None removes the key; subsequent reads return None."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "info.display-name", None)
        self.assertIsNone(self.repo.get_board_metadata("alpha", "info.display-name"))

    def test_returns_none_for_missing_key(self) -> None:
        """Returns None when the section exists but the key does not."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.assertIsNone(self.repo.get_board_metadata("alpha", "info.nonexistent"))

    def test_returns_none_for_missing_section(self) -> None:
        """Returns None when neither section nor key has been written."""
        self.assertIsNone(self.repo.get_board_metadata("alpha", "no-such-section.key"))

    def test_metadata_is_scoped_to_board(self) -> None:
        """Metadata written for one board is not visible on another board."""
        self.repo.create_board("beta")
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.assertIsNone(self.repo.get_board_metadata("beta", "info.display-name"))

    def test_raises_for_invalid_keypath(self) -> None:
        """Raises KeyError when the keypath has no dot separator."""
        with self.assertRaises(KeyError):
            self.repo.get_board_metadata("alpha", "nodot")
        with self.assertRaises(KeyError):
            self.repo.set_board_metadata("alpha", "nodot", "value")


class TestFilesystemColumnOrderWithOtherMetadata(unittest.TestCase):
    """Column order (a multi-line INI value) survives reads and writes alongside other metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_column_order_preserved_after_writing_other_metadata(self) -> None:
        """Column order is unchanged after an unrelated key is written to the same file."""
        for col in ("todo", "in-progress", "done"):
            self.repo.create_column("proj", col)
        self.repo.set_board_metadata("proj", "info.display-name", "My Project")
        columns = [c.name for c in self.repo.get_columns("proj")]
        self.assertEqual(columns, ["todo", "in-progress", "done"])

    def test_other_metadata_preserved_after_adding_column(self) -> None:
        """An unrelated metadata key is unchanged after a new column is created."""
        self.repo.set_board_metadata("proj", "info.display-name", "My Project")
        self.repo.create_column("proj", "todo")
        self.repo.create_column("proj", "done")
        self.assertEqual(self.repo.get_board_metadata("proj", "info.display-name"), "My Project")

    def test_column_order_preserved_across_multiple_write_cycles(self) -> None:
        """Column order survives interleaved writes from both column ops and other metadata."""
        self.repo.create_column("proj", "todo")
        self.repo.set_board_metadata("proj", "info.color", "blue")
        self.repo.create_column("proj", "in-progress")
        self.repo.set_board_metadata("proj", "info.color", "green")
        self.repo.create_column("proj", "done")
        columns = [c.name for c in self.repo.get_columns("proj")]
        self.assertEqual(columns, ["todo", "in-progress", "done"])
        self.assertEqual(self.repo.get_board_metadata("proj", "info.color"), "green")

    def test_column_order_preserved_with_multiple_other_sections(self) -> None:
        """Column order is correct when several other sections exist in the metadata file."""
        for col in ("todo", "in-progress", "done"):
            self.repo.create_column("proj", col)
        self.repo.set_board_metadata("proj", "info.display-name", "My Project")
        self.repo.set_board_metadata("proj", "settings.color", "blue")
        self.repo.set_board_metadata("proj", "access.owner", "alice")
        columns = [c.name for c in self.repo.get_columns("proj")]
        self.assertEqual(columns, ["todo", "in-progress", "done"])

    def test_reorder_column_preserved_alongside_other_metadata(self) -> None:
        """reorder_column produces the correct order even when other keys are present."""
        for col in ("todo", "in-progress", "done"):
            self.repo.create_column("proj", col)
        self.repo.set_board_metadata("proj", "info.display-name", "My Project")
        self.repo.reorder_column("proj", "done", 0)
        columns = [c.name for c in self.repo.get_columns("proj")]
        self.assertEqual(columns, ["done", "todo", "in-progress"])
        self.assertEqual(self.repo.get_board_metadata("proj", "info.display-name"), "My Project")


if __name__ == "__main__":
    unittest.main()
