"""Tests for FilesystemRepository.delete_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from kanban.models import Task
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.kanban import TaskNotFound


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemDeleteTask(unittest.TestCase):
    """delete_task removes the file from disk and from the column task order."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str) -> Task:
        now = _now()
        return Task(id=uuid4(), 
                    title=title, 
                    slug=slug, 
                    board="proj", 
                    column="todo",
                    created_at=now, 
                    updated_at=now)

    def test_file_is_removed(self) -> None:
        """The task file no longer exists on disk after delete_task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        path = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertTrue(path.is_file())
        self.repo.delete_task(task)
        self.assertFalse(path.exists())

    def test_task_removed_from_order(self) -> None:
        """Deleted task slug is absent from the column task order metadata."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.delete_task(task)
        order = self.repo.get_column_metadata("proj", "todo", "tasks.order") or ""
        filenames = [f.strip() for f in order.split("\n") if f.strip()]
        self.assertNotIn("alpha.md", filenames)

    def test_remaining_tasks_preserved_in_order(self) -> None:
        """Other tasks stay in order after one is deleted."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        self.repo.delete_task(t2)
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Gamma"])

    def test_raises_for_unknown_task(self) -> None:
        """Raises TaskNotFound when no task with the given UUID exists."""
        missing_task = Task(
            id=uuid4(), 
            title="Missing",
            slug="missing",
            board="proj",
            column="todo",
            created_at=_now(),
            updated_at=_now())
            
        with self.assertRaises(TaskNotFound):
            self.repo.delete_task(missing_task)

    def test_deleted_task_not_returned_by_get_tasks(self) -> None:
        """get_tasks omits the deleted task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.delete_task(task)
        tasks = self.repo.get_tasks(board="proj", column="todo")
        self.assertEqual(tasks, [])
        

if __name__ == "__main__":
    unittest.main()
