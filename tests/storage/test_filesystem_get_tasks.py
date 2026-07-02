"""Tests for FilesystemRepository.get_tasks."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardNotFound, ColumnNotFound


def _task_md(task_id: str, title: str, slug: str) -> str:
    return textwrap.dedent(f"""\
        ---
        id: {task_id}
        title: {title}
        slug: {slug}
        ---
    """)


class TestFilesystemGetTasks(unittest.TestCase):
    """get_tasks returns tasks scoped by board/column."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

        for board in ("alpha", "beta"):
            (self.repo.boards_dir / board).mkdir()
            for col in ("todo", "done"):
                (self.repo.boards_dir / board / col).mkdir()

        self._write("alpha", "todo", "task-a", "a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task A")
        self._write("alpha", "done", "task-b", "b3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task B")
        self._write("beta",  "todo", "task-c", "c3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task C")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, board: str, col: str, slug: str, uid: str, title: str) -> None:
        path = self.repo.boards_dir / board / col / f"{slug}.md"
        path.write_text(_task_md(uid, title, slug), encoding="utf-8")

    def test_returns_all_tasks_when_no_scope(self) -> None:
        """With no board or column, all tasks across all boards are returned."""
        tasks = self.repo.get_tasks()
        self.assertEqual(len(tasks), 3)

    def test_scopes_to_board(self) -> None:
        """With only board set, returns tasks from all columns of that board."""
        tasks = self.repo.get_tasks(board="alpha")
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(t.board == "alpha" for t in tasks))

    def test_scopes_to_board_and_column(self) -> None:
        """With board and column set, returns only tasks in that column."""
        tasks = self.repo.get_tasks(board="alpha", column="todo")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].slug, "task-a")

    def test_returns_empty_list_for_empty_column(self) -> None:
        """Returns an empty list when the scoped column has no task files."""
        tasks = self.repo.get_tasks(board="beta", column="done")
        self.assertEqual(tasks, [])

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when the requested board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_tasks(board="missing")

    def test_raises_when_column_missing(self) -> None:
        """Raises ColumnNotFound when the requested column does not exist on the board."""
        with self.assertRaises(ColumnNotFound):
            self.repo.get_tasks(board="alpha", column="missing")


if __name__ == "__main__":
    unittest.main()
