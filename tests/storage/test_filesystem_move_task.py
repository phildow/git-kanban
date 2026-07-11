"""Tests for FilesystemRepository.move_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from kanban.models import Task
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import ColumnNotFound, TaskNotFound, TaskAlreadyExists


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemMoveTask(unittest.TestCase):
    """move_task relocates a task file and keeps task order metadata consistent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str, column: str = "todo") -> Task:
        now = _now()
        return Task(id=uuid4(), 
                    title=title, 
                    slug=slug, 
                    board="proj", 
                    column=column,
                    created_at=now, 
                    updated_at=now)

    def test_file_appears_at_destination(self) -> None:
        """Task file exists at the destination column after move_task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, "done")
        dest = self.repo.boards_dir / "proj" / "done" / "alpha.md"
        self.assertTrue(dest.is_file())

    def test_file_removed_from_source(self) -> None:
        """Original task file is gone from the source column after move_task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, "done")
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertFalse(src.exists())

    def test_returns_task_with_updated_column(self) -> None:
        """Returned task reflects the destination column; board and slug are unchanged."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, "done")
        self.assertEqual(moved.board, "proj")
        self.assertEqual(moved.column, "done")
        self.assertEqual(moved.slug, "alpha")

    def test_updated_at_is_refreshed(self) -> None:
        """The moved task's updated_at is later than or equal to the original."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, "done")
        self.assertGreaterEqual(moved.updated_at, task.updated_at)

    def test_removed_from_source_order(self) -> None:
        """Task filename is absent from the source column's task order after move."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, "done")
        self.assertEqual(self.repo.get_tasks(board="proj", column="todo"), [])

    def test_added_to_destination_order(self) -> None:
        """Task filename appears in the destination column's task order after move."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, "done")
        dest_tasks = self.repo.get_tasks(board="proj", column="done")
        self.assertEqual(len(dest_tasks), 1)
        self.assertEqual(dest_tasks[0].title, "Alpha")

    def test_other_source_tasks_preserved_in_order(self) -> None:
        """Remaining tasks in the source column keep their order after one is moved."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        self.repo.move_task(t2, "done")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Gamma"])

    def test_same_column_is_noop_for_file(self) -> None:
        """Moving to the same column leaves the file in place."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, "todo")
        self.assertTrue((self.repo.boards_dir / "proj" / "todo" / "alpha.md").is_file())
        self.assertEqual(moved.column, "todo")

    def test_same_column_preserves_order(self) -> None:
        """Moving to the same column does not corrupt the task order."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.move_task(t1, "todo")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta"])

    def test_raises_task_not_found_for_missing_file(self) -> None:
        """Raises TaskNotFound when the source file does not exist on disk."""
        phantom = self._task("Ghost", "ghost")
        with self.assertRaises(TaskNotFound):
            self.repo.move_task(phantom, "done")

    def test_raises_column_not_found(self) -> None:
        """Raises ColumnNotFound when the destination column does not exist."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        with self.assertRaises(ColumnNotFound):
            self.repo.move_task(task, "no-such-column")

    def test_raises_task_already_exists_at_destination(self) -> None:
        """Raises TaskAlreadyExists when a file with the same slug is already in the destination."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Alpha copy", "alpha", "done"), "alpha")
        with self.assertRaises(TaskAlreadyExists):
            self.repo.move_task(t1, "done")

    def test_returns_slugs_not_display_names_when_they_differ(self) -> None:
        """board/column on the returned task are slugs, even when display names differ."""
        self.repo.create_board("My Project", slug="my-project")
        self.repo.create_column("my-project", "To Do", slug="todo")
        self.repo.create_column("my-project", "Done", slug="done")

        task = Task(
            id=uuid4(),
            title="Alpha",
            slug="alpha",
            board="my-project",
            column="todo",
        )
        created = self.repo.create_task(task, "alpha")

        moved = self.repo.move_task(created, "done")

        self.assertEqual(moved.board, "my-project")
        self.assertEqual(moved.column, "done")


if __name__ == "__main__":
    unittest.main()
