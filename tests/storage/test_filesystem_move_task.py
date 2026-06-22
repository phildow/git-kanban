"""Tests for FilesystemRepository.move_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import Task
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound, ColumnNotFound, TaskNotFound, TaskAlreadyExists


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemMoveTask(unittest.TestCase):
    """move_task relocates a task file and keeps task order metadata consistent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.repo.create_column("proj", "done")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str, column: str = "todo") -> Task:
        now = _now()
        return Task(id=uuid4(), title=title, slug=slug, board="proj", column=column,
                    created_at=now, updated_at=now)

    def test_file_appears_at_destination(self) -> None:
        """Task file exists at the destination after move_task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "done")
        dest = self.repo.boards_dir / "proj" / "done" / "alpha.md"
        self.assertTrue(dest.is_file())

    def test_file_removed_from_source(self) -> None:
        """Original task file is gone from the source column after move_task."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "done")
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertFalse(src.exists())

    def test_returns_task_with_updated_location(self) -> None:
        """Returned task reflects the destination board and column."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("proj") / "done")
        self.assertEqual(moved.board, "proj")
        self.assertEqual(moved.column, "done")
        self.assertEqual(moved.slug, "alpha")

    def test_updated_at_is_refreshed(self) -> None:
        """The moved task's updated_at is later than the original."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("proj") / "done")
        self.assertGreaterEqual(moved.updated_at, task.updated_at)

    def test_removed_from_source_order(self) -> None:
        """Task filename is absent from the source column's task order after move."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "done")
        src_tasks = self.repo.get_tasks(board="proj", column="todo")
        self.assertEqual(src_tasks, [])

    def test_added_to_destination_order(self) -> None:
        """Task filename appears in the destination column's task order after move."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "done")
        dest_tasks = self.repo.get_tasks(board="proj", column="done")
        self.assertEqual(len(dest_tasks), 1)
        self.assertEqual(dest_tasks[0].title, "Alpha")

    def test_other_source_tasks_preserved_in_order(self) -> None:
        """Remaining tasks in the source column keep their order after one is moved."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        self.repo.move_task(t2, Path("proj") / "done")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Gamma"])

    def test_move_across_boards(self) -> None:
        """A task can be moved to a column on a different board."""
        self.repo.create_board("other")
        self.repo.create_column("other", "backlog")
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("other") / "backlog")
        self.assertEqual(moved.board, "other")
        self.assertEqual(moved.column, "backlog")
        dest = self.repo.boards_dir / "other" / "backlog" / "alpha.md"
        self.assertTrue(dest.is_file())
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertFalse(src.exists())

    def test_same_location_is_noop_for_file(self) -> None:
        """Moving to the same board and column leaves the file in place."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("proj") / "todo")
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertTrue(src.is_file())
        self.assertEqual(moved.board, "proj")
        self.assertEqual(moved.column, "todo")

    def test_same_location_preserves_order(self) -> None:
        """Moving to the same board and column does not corrupt the task order."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.move_task(t1, Path("proj") / "todo")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta"])

    def test_rename_in_place_new_file_exists(self) -> None:
        """Renamed file exists at the new path in the same column."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("proj") / "todo" / "alpha-v2")
        dest = self.repo.boards_dir / "proj" / "todo" / "alpha-v2.md"
        self.assertTrue(dest.is_file())
        self.assertEqual(moved.slug, "alpha-v2")

    def test_rename_in_place_old_file_gone(self) -> None:
        """Original file is removed after rename in place."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "todo" / "alpha-v2")
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertFalse(src.exists())

    def test_rename_in_place_preserves_order_position(self) -> None:
        """Rename in place keeps the task at its original position in column order."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        self.repo.move_task(t2, Path("proj") / "todo" / "beta-v2")
        slugs = [t.slug for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(slugs, ["alpha", "beta-v2", "gamma"])

    def test_rename_in_place_slug_updated_in_frontmatter(self) -> None:
        """The slug field in the task frontmatter is updated after rename."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.move_task(task, Path("proj") / "todo" / "alpha-v2")
        dest = self.repo.boards_dir / "proj" / "todo" / "alpha-v2.md"
        content = dest.read_text(encoding="utf-8")
        self.assertIn("slug: alpha-v2", content)

    def test_move_with_rename(self) -> None:
        """A task can be moved to a different column with a new slug in one call."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        moved = self.repo.move_task(task, Path("proj") / "done" / "alpha-done")
        self.assertEqual(moved.board, "proj")
        self.assertEqual(moved.column, "done")
        self.assertEqual(moved.slug, "alpha-done")
        dest = self.repo.boards_dir / "proj" / "done" / "alpha-done.md"
        self.assertTrue(dest.is_file())
        src = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertFalse(src.exists())

    def test_raises_task_not_found_for_missing_file(self) -> None:
        """Raises TaskNotFound when the source file does not exist on disk."""
        phantom = self._task("Ghost", "ghost")
        with self.assertRaises(TaskNotFound):
            self.repo.move_task(phantom, Path("proj") / "done")

    def test_raises_board_not_found(self) -> None:
        """Raises BoardNotFound when the destination board does not exist."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        with self.assertRaises(BoardNotFound):
            self.repo.move_task(task, Path("no-such-board") / "todo")

    def test_raises_column_not_found(self) -> None:
        """Raises ColumnNotFound when the destination column does not exist."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        with self.assertRaises(ColumnNotFound):
            self.repo.move_task(task, Path("proj") / "no-such-column")

    def test_raises_task_already_exists_at_destination(self) -> None:
        """Raises TaskAlreadyExists when a file with the same slug is already in the destination column."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Alpha copy", "alpha", "done"), "alpha")
        with self.assertRaises(TaskAlreadyExists):
            self.repo.move_task(t1, Path("proj") / "done")


if __name__ == "__main__":
    unittest.main()
