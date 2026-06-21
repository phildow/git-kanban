"""Tests for FilesystemRepository.bootstrap."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from models import Task
from storage.filesystem import FilesystemRepository


class TestFilesystemBootstrap(unittest.TestCase):
    """bootstrap seeds the main board with default columns and starter tasks."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_creates_main_board(self) -> None:
        """The main board exists after bootstrap."""
        self.repo.bootstrap()
        self.assertTrue(self.repo.board_exists("main"))

    def test_creates_default_columns(self) -> None:
        """All four standard columns are created under main."""
        self.repo.bootstrap()
        columns = [c.name for c in self.repo.get_columns("main")]
        self.assertEqual(columns, ["todo", "in-progress", "in-review", "done"])

    def test_returns_task_list(self) -> None:
        """Returns a non-empty list of Task objects."""
        tasks = self.repo.bootstrap()
        self.assertIsInstance(tasks, list)
        self.assertTrue(len(tasks) > 0)
        self.assertTrue(all(isinstance(t, Task) for t in tasks))

    def test_todo_tasks_exist(self) -> None:
        """Three tutorial tasks are seeded into the todo column."""
        tasks = self.repo.bootstrap()
        todo_tasks = [t for t in tasks if t.column == "todo"]
        self.assertEqual(len(todo_tasks), 3)
        titles = [t.title for t in todo_tasks]
        self.assertIn("list your boards and tasks", titles)
        self.assertIn("create a new task", titles)
        self.assertIn("move a task to another column", titles)
        for t in todo_tasks:
            self.assertEqual(t.board, "main")

    def test_in_progress_task_has_metadata(self) -> None:
        """The in-progress seed task is seeded with priority and assignee."""
        tasks = self.repo.bootstrap()
        in_progress = [t for t in tasks if t.column == "in-progress"]
        self.assertEqual(len(in_progress), 1)
        self.assertEqual(in_progress[0].title, "update a task with details")
        self.assertEqual(in_progress[0].priority, "high")
        self.assertEqual(in_progress[0].assignee, "alice")

    def test_bike_ride_task_in_done(self) -> None:
        """The 'go for a bike ride' task is seeded into the done column."""
        tasks = self.repo.bootstrap()
        done_tasks = [t for t in tasks if t.column == "done"]
        self.assertEqual(len(done_tasks), 1)
        self.assertEqual(done_tasks[0].title, "go for a bike ride")

    def test_tasks_have_ids(self) -> None:
        """Each bootstrapped task has a non-zero UUID assigned."""
        from uuid import UUID
        tasks = self.repo.bootstrap()
        for task in tasks:
            self.assertIsNotNone(task.id)
            self.assertNotEqual(task.id, UUID(int=0))

    def test_task_files_on_disk(self) -> None:
        """Task files are written to the correct column directories."""
        self.repo.bootstrap()
        expected = [
            self.repo.boards_dir / "main" / "todo" / "list-your-boards-and-tasks.md",
            self.repo.boards_dir / "main" / "todo" / "create-a-new-task.md",
            self.repo.boards_dir / "main" / "todo" / "move-a-task-to-another-column.md",
            self.repo.boards_dir / "main" / "in-progress" / "update-a-task-with-details.md",
            self.repo.boards_dir / "main" / "done" / "go-for-a-bike-ride.md",
        ]
        for path in expected:
            self.assertTrue(path.is_file(), f"Missing: {path.name}")


if __name__ == "__main__":
    unittest.main()
