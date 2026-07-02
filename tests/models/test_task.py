"""Tests for `Task.filename` and `Task.path`."""

from __future__ import annotations

import unittest

from pathlib import Path
from uuid import uuid4

from kanban.models import Task


class TestTaskFilenameAndPath(unittest.TestCase):
    """Verifies the `filename` and `path` properties of `Task`."""

    def test_filename_is_slug_with_md_extension(self):
        """`filename` returns the task's slug suffixed with `.md`."""
        task = Task(
            id=uuid4(),
            title="Fix login bug",
            slug="fix-login-bug",
            board="my-project",
            column="todo",
        )
        self.assertEqual(task.filename, "fix-login-bug.md")

    def test_path_is_absolute_and_includes_board_and_column_and_filename(self):
        """`path` is an absolute path containing the board's slug, the column's slug, and the task's filename."""
        task = Task(
            id=uuid4(),
            title="Fix login bug",
            slug="fix-login-bug",
            board="my-project",
            column="todo",
        )
        self.assertEqual(task.path, Path("/my-project/todo/fix-login-bug.md"))
        self.assertTrue(task.path.is_absolute())


if __name__ == "__main__":
    unittest.main()
