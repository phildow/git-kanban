"""Integration tests for IndexService.diff against a real FilesystemRepository.

Tasks are created and deleted through KanbanService, which keeps the index
in sync via its write-through hooks. Files are also written and removed
directly on disk, bypassing the service entirely, to simulate out-of-band
filesystem changes. diff() must surface exactly those discrepancies.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.index.memory import InMemoryIndex
from kanban.services.git import GitService
from kanban.services.index import IndexDiff, IndexService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.filesystem import FilesystemRepository


class TestIndexServiceDiffFilesystem(unittest.TestCase):
    """diff() against a FilesystemRepository, mixing service and on-disk changes."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

        self.index_base = InMemoryIndex()
        self.index_service = IndexService(index_base=self.index_base, repository=self.repo)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=self.index_service,
            git_service=GitService(),
        )

        self.svc.create_board("main", columns=[("To Do", "todo"), ("Backlog", "backlog")])

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_raw_task_file(self, board: str, column: str, slug: str, title: str) -> None:
        """Write a task .md file straight to disk, bypassing the service and index."""
        path = self.repo.boards_dir / board / column / f"{slug}.md"
        path.write_text(
            "\n".join(["---", f"id: {uuid4()}", f"title: {title}", f"slug: {slug}", "---", ""]),
            encoding="utf-8",
        )

    def test_no_diff_after_service_creates_tasks(self) -> None:
        """Tasks created through the service are indexed immediately; diff() is empty."""
        self.svc.create_task("main/todo/Fix login bug", TaskCreateParams())
        self.svc.create_task("main/todo/Write docs", TaskCreateParams())

        result = self.index_service.diff()

        self.assertEqual(result.missing_from_repository, set())
        self.assertEqual(result.missing_from_index, set())

    def test_no_diff_after_service_deletes_a_task(self) -> None:
        """Deleting through the service removes the index entry too; diff() stays empty."""
        self.svc.create_task("main/todo/Fix login bug", TaskCreateParams())
        self.svc.delete_task("main/todo/fix-login-bug")

        result = self.index_service.diff()

        self.assertEqual(result.missing_from_repository, set())
        self.assertEqual(result.missing_from_index, set())

    def test_file_deleted_directly_on_disk_is_missing_from_repository(self) -> None:
        """Removing a .md file outside the service leaves a stale, orphaned index entry."""
        task = self.svc.create_task("main/todo/Fix login bug", TaskCreateParams())
        (self.repo.boards_dir / "main" / "todo" / "fix-login-bug.md").unlink()

        result = self.index_service.diff()

        self.assertEqual(result.missing_from_repository, {task.path})
        self.assertEqual(result.missing_from_index, set())

    def test_file_created_directly_on_disk_is_missing_from_index(self) -> None:
        """A .md file dropped straight onto disk is invisible to the index until indexed."""
        self._write_raw_task_file("main", "backlog", "add-rate-limiting", "Add rate limiting")

        result = self.index_service.diff()

        expected_path = Path("/main/backlog/add-rate-limiting")
        self.assertEqual(result.missing_from_index, {expected_path})
        self.assertEqual(result.missing_from_repository, set())

    def test_diff_reports_both_directions_after_mixed_changes(self) -> None:
        """A deletion and an out-of-band addition are both surfaced in one diff() call."""
        stale_task = self.svc.create_task("main/todo/Fix login bug", TaskCreateParams())
        (self.repo.boards_dir / "main" / "todo" / "fix-login-bug.md").unlink()

        self._write_raw_task_file("main", "backlog", "add-rate-limiting", "Add rate limiting")

        result = self.index_service.diff()

        self.assertEqual(result.missing_from_repository, {stale_task.path})
        self.assertEqual(result.missing_from_index, {Path("/main/backlog/add-rate-limiting")})

    def test_rebuild_resolves_missing_from_index_after_direct_file_creation(self) -> None:
        """rebuild() re-scans the repository, absorbing files added directly on disk."""
        self._write_raw_task_file("main", "backlog", "add-rate-limiting", "Add rate limiting")
        self.assertNotEqual(self.index_service.diff().missing_from_index, set())

        self.index_service.rebuild()

        result = self.index_service.diff()
        self.assertEqual(result.missing_from_index, set())

    def test_returns_index_diff_instance(self) -> None:
        """diff() returns an IndexDiff dataclass instance."""
        result = self.index_service.diff()
        self.assertIsInstance(result, IndexDiff)


if __name__ == "__main__":
    unittest.main()
