"""Tests for IndexService.diff, using InMemoryRepository and InMemoryIndex."""

from __future__ import annotations

import unittest

from kanban.index.memory import InMemoryIndex
from kanban.services.index import IndexDiff, IndexService
from kanban.storage.memory import InMemoryRepository
from tests.index.helpers import make_task


class TestIndexServiceDiff(unittest.TestCase):
    """diff() compares index_base.known_paths() against repository.get_tasks()."""

    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.repo.create_board("Main", slug="main")
        self.repo.create_column("main", "To Do", slug="todo")
        self.repo.create_column("main", "Done", slug="done")

        self.index_base = InMemoryIndex()
        self.service = IndexService(index_base=self.index_base, repository=self.repo)

    def _add_task(self, title: str, *, board: str = "main", column: str = "todo", slug: str | None = None):
        """Create a task in the repository and return it."""
        task = make_task(title=title, board=board, column=column, slug=slug)
        return self.repo.create_task(task, task.slug)

    def test_no_diff_when_index_matches_repository(self) -> None:
        """diff() reports nothing missing when every task is indexed."""
        task = self._add_task("Fix login bug")
        self.index_base.upsert_task(task)

        result = self.service.diff()

        self.assertEqual(result.missing_from_repository, set())
        self.assertEqual(result.missing_from_index, set())

    def test_task_created_outside_the_index_is_missing_from_index(self) -> None:
        """A repository task never upserted into the index is missing_from_index."""
        task = self._add_task("Fix login bug")

        result = self.service.diff()

        self.assertEqual(result.missing_from_index, {task.path})
        self.assertEqual(result.missing_from_repository, set())

    def test_stale_index_entry_is_missing_from_repository(self) -> None:
        """A task removed from the repository but still indexed is missing_from_repository."""
        stale = make_task(title="Deleted task", board="main", column="todo")
        self.index_base.upsert_task(stale)

        result = self.service.diff()

        self.assertEqual(result.missing_from_repository, {stale.path})
        self.assertEqual(result.missing_from_index, set())

    def test_diff_reports_both_directions_simultaneously(self) -> None:
        """Independent discrepancies in each direction are both reported."""
        indexed_task = self._add_task("Fix login bug")
        self.index_base.upsert_task(indexed_task)

        unindexed_task = self._add_task("Write docs", slug="write-docs")

        stale = make_task(title="Deleted task", board="main", column="done")
        self.index_base.upsert_task(stale)

        result = self.service.diff()

        self.assertEqual(result.missing_from_index, {unindexed_task.path})
        self.assertEqual(result.missing_from_repository, {stale.path})

    def test_empty_index_and_repository_have_no_diff(self) -> None:
        """An empty repository and empty index have nothing to report."""
        result = self.service.diff()

        self.assertEqual(result.missing_from_repository, set())
        self.assertEqual(result.missing_from_index, set())

    def test_diff_is_scoped_to_board(self) -> None:
        """board= restricts the comparison to that board on both sides."""
        self.repo.create_board("Ops", slug="ops")
        self.repo.create_column("ops", "Backlog", slug="backlog")

        main_task = self._add_task("Main task", board="main", column="todo")
        self.index_base.upsert_task(main_task)

        # Unindexed task in a different board must not leak into the "main" diff.
        self._add_task("Ops task", board="ops", column="backlog")

        result = self.service.diff(board="main")

        self.assertEqual(result.missing_from_index, set())
        self.assertEqual(result.missing_from_repository, set())

    def test_returns_index_diff_instance(self) -> None:
        """diff() returns an IndexDiff dataclass instance."""
        result = self.service.diff()
        self.assertIsInstance(result, IndexDiff)


if __name__ == "__main__":
    unittest.main()
