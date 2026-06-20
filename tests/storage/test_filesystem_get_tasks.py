"""Tests for FilesystemRepository.get_tasks."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID

from models import TaskFilter
from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound, ColumnNotFound


_UTC = timezone.utc


def _task_md(
    task_id: str,
    title: str,
    slug: str,
    *,
    assignee: str = "",
    priority: str = "",
    tags: str = "",
    due_date: str = "",
    created_by: str = "",
) -> str:
    return textwrap.dedent(f"""\
        ---
        id: {task_id}
        title: {title}
        slug: {slug}
        assignee: {assignee}
        priority: {priority}
        tags: [{tags}]
        due_date: {due_date}
        created_by: {created_by}
        ---
    """)


class TestFilesystemGetTasks(unittest.TestCase):
    """get_tasks returns tasks scoped by board/column with optional filtering."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

        for board in ("alpha", "beta"):
            (self.repo.boards_dir / board).mkdir()
            for col in ("todo", "done"):
                (self.repo.boards_dir / board / col).mkdir()

        self._write("alpha", "todo", "task-a", "a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task A",
                    assignee="alice", priority="high", tags="bug", due_date="2026-06-01")
        self._write("alpha", "done", "task-b", "b3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task B",
                    assignee="bob", priority="low", tags="feature")
        self._write("beta",  "todo", "task-c", "c3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d", "Task C",
                    assignee="alice", priority="high", tags="bug", due_date="2026-07-01")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, board: str, col: str, slug: str, uid: str, title: str, **kwargs) -> None:
        path = self.repo.boards_dir / board / col / f"{slug}.md"
        path.write_text(_task_md(uid, title, slug, **kwargs), encoding="utf-8")

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

    def test_filter_by_assignee(self) -> None:
        """TaskFilter.assignee narrows results to tasks assigned to that user."""
        tasks = self.repo.get_tasks(filter=TaskFilter(assignee="alice"))
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(t.assignee == "alice" for t in tasks))

    def test_filter_by_priority(self) -> None:
        """TaskFilter.priority narrows results to tasks with that priority."""
        tasks = self.repo.get_tasks(filter=TaskFilter(priority="high"))
        self.assertEqual(len(tasks), 2)

    def test_filter_by_tag(self) -> None:
        """TaskFilter.tag narrows results to tasks carrying that tag."""
        tasks = self.repo.get_tasks(filter=TaskFilter(tag="feature"))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].slug, "task-b")

    def test_filter_by_due_before(self) -> None:
        """TaskFilter.due_before excludes tasks due on or after the cutoff."""
        cutoff = datetime(2026, 6, 15, tzinfo=_UTC)
        tasks = self.repo.get_tasks(filter=TaskFilter(due_before=cutoff))
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].slug, "task-a")

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
