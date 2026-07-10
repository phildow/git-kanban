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


if __name__ == "__main__":
    unittest.main()
