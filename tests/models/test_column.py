"""Tests for `Column.path`."""

from __future__ import annotations

import unittest

from pathlib import Path
from uuid import uuid4

from kanban.models import Column


class TestColumnAPath(unittest.TestCase):
    """Verifies the `path` property of `Column`."""

    def test_path_is_absolute_and_includes_board_and_slug(self):
        """`path` is an absolute path containing the board's slug and the column's slug."""
        column = Column(id=uuid4(), name="To Do", slug="todo", board="my-project", position=0)
        self.assertEqual(column.path, Path("/my-project/todo"))
        self.assertTrue(column.path.is_absolute())


class TestColumnRole(unittest.TestCase):
    """Verifies the `role` field of `Column` and the archive it marks."""

    def _column(self, role: str | None = None) -> Column:
        """Return a column carrying `role`."""
        return Column(
            id=uuid4(), name="Archive", slug="archive", board="my-project", position=4, role=role
        )

    def test_columns_have_no_role_by_default(self):
        """An ordinary column carries no role."""
        column = Column(id=uuid4(), name="To Do", slug="todo", board="my-project", position=0)
        self.assertIsNone(column.role)
        self.assertFalse(column.is_archive)

    def test_archive_role_marks_the_archive(self):
        """`is_archive` reports the column archived tasks belong to."""
        self.assertTrue(self._column(role="archive").is_archive)

    def test_another_role_is_not_the_archive(self):
        """Only the archive role marks the archive."""
        self.assertFalse(self._column(role="backlog").is_archive)


if __name__ == "__main__":
    unittest.main()
