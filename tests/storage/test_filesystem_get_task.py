"""Tests for FilesystemRepository.get_task and _parse_task_file."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from datetime import datetime, UTC
from pathlib import Path
from uuid import UUID

from kanban.models import Task
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardNotFound, ColumnNotFound, TaskNotFound


_TASK_ID = UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")


def _write_task(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


class TestFilesystemGetTask(unittest.TestCase):
    """get_task reads and parses a markdown task file."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        (self.repo.boards_dir / "alpha").mkdir()
        (self.repo.boards_dir / "alpha" / "todo").mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task_path(self, filename: str) -> Path:
        return self.repo.boards_dir / "alpha" / "todo" / f"{filename}.md"

    def test_returns_task_with_correct_location(self) -> None:
        """Returned Task has board and column set from the path arguments."""
        _write_task(self._task_path("fix-bug"), f"""\
            ---
            id: {_TASK_ID}
            title: Fix bug
            slug: fix-bug
            ---
        """)
        task = self.repo.get_task("alpha", "todo", "fix-bug")
        self.assertEqual(task.board, "alpha")
        self.assertEqual(task.column, "todo")

    def test_parses_all_frontmatter_fields(self) -> None:
        """All frontmatter fields are mapped to the correct Task attributes."""
        _write_task(self._task_path("fix-bug"), f"""\
            ---
            id: {_TASK_ID}
            title: Fix bug
            slug: fix-bug
            assigned_to: alice
            created_by: bob
            priority: high
            due_date: 2026-06-20
            tags: [bug, auth]
            created_at: 2026-06-12T10:00:00+00:00
            updated_at: 2026-06-13T08:00:00+00:00
            ---
            Body text here.
        """)
        task = self.repo.get_task("alpha", "todo", "fix-bug")
        self.assertEqual(task.id, _TASK_ID)
        self.assertEqual(task.title, "Fix bug")
        self.assertEqual(task.slug, "fix-bug")
        self.assertEqual(task.assigned_to, "alice")
        self.assertEqual(task.created_by, "bob")
        self.assertEqual(task.priority, "high")
        self.assertEqual(task.due_date, datetime(2026, 6, 20, tzinfo=UTC).replace(tzinfo=task.due_date.tzinfo))
        self.assertEqual(task.tags, ["bug", "auth"])
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.updated_at)

    def test_parses_body(self) -> None:
        """Content after the closing frontmatter delimiter becomes the body."""
        _write_task(self._task_path("fix-bug"), f"""\
            ---
            id: {_TASK_ID}
            title: Fix bug
            slug: fix-bug
            ---
            # Description

            Some details here.
        """)
        task = self.repo.get_task("alpha", "todo", "fix-bug")
        self.assertIn("Description", task.body)
        self.assertIn("Some details here", task.body)

    def test_empty_tags_returns_empty_list(self) -> None:
        """A missing or empty tags field produces an empty list."""
        _write_task(self._task_path("fix-bug"), f"""\
            ---
            id: {_TASK_ID}
            title: Fix bug
            slug: fix-bug
            ---
        """)
        task = self.repo.get_task("alpha", "todo", "fix-bug")
        self.assertEqual(task.tags, [])

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_task("missing", "todo", "fix-bug")

    def test_raises_when_column_missing(self) -> None:
        """Raises ColumnNotFound when the column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.repo.get_task("alpha", "missing", "fix-bug")

    def test_raises_when_task_file_missing(self) -> None:
        """Raises TaskNotFound when no .md file with that name exists."""
        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "missing")


if __name__ == "__main__":
    unittest.main()
