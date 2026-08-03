"""Tests for what the filesystem stores about archiving.

A column's role lives in its `.metadata` file; nothing about archiving is
stored on the task itself, which is archived by sitting in that column.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository


class TestFilesystemColumnRole(unittest.TestCase):
    """A column's role is written to and read back from its .metadata file."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = FilesystemRepository(root=Path(self._tmp.name))
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_role_is_stored_in_column_metadata(self) -> None:
        """create_column writes `fields.role` for a column given one."""
        self.repo.create_column("proj", "Archive", slug="archive", role="archive")

        self.assertEqual(
            self.repo.get_column_metadata("proj", "archive", "fields.role"), "archive"
        )

    def test_created_column_carries_its_role(self) -> None:
        """The returned Column reports the role it was created with."""
        column = self.repo.create_column("proj", "Archive", slug="archive", role="archive")

        self.assertEqual(column.role, "archive")
        self.assertTrue(column.is_archive)

    def test_ordinary_column_has_no_role_key(self) -> None:
        """A column with no role leaves the key out of its metadata."""
        self.repo.create_column("proj", "To Do", slug="todo")

        self.assertIsNone(self.repo.get_column_metadata("proj", "todo", "fields.role"))

    def test_get_column_reads_the_role_back(self) -> None:
        """get_column returns the stored role."""
        self.repo.create_column("proj", "Archive", slug="archive", role="archive")

        self.assertTrue(self.repo.get_column("proj", "archive").is_archive)

    def test_get_columns_reads_the_role_back(self) -> None:
        """get_columns returns the stored role for each column."""
        self.repo.create_column("proj", "To Do", slug="todo")
        self.repo.create_column("proj", "Archive", slug="archive", role="archive")

        roles = {column.slug: column.role for column in self.repo.get_columns("proj")}

        self.assertEqual(roles, {"todo": None, "archive": "archive"})

    def test_role_survives_a_rename(self) -> None:
        """Renaming a column rewrites its name and slug, not its role."""
        self.repo.create_column("proj", "Archive", slug="archive", role="archive")

        renamed = self.repo.rename_column("proj", "archive", "Attic", new_slug="attic")

        self.assertTrue(renamed.is_archive)


if __name__ == "__main__":
    unittest.main()
