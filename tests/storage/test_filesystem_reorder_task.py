"""Tests for FilesystemRepository.reorder_task."""

from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from kanban.models import Task
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import TaskNotFound


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemReorderTask(unittest.TestCase):
    """reorder_task changes the position of a task within its column and refreshes updated_at."""

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
        return Task(id=uuid4(), title=title, slug=slug, board="proj", column="todo",
                    created_at=now, updated_at=now)

    def _titles(self) -> list[str]:
        return [t.title for t in self.repo.get_tasks(board="proj", column="todo")]

    def _setup_three(self) -> tuple[Task, Task, Task]:
        """Create Alpha, Beta, Gamma in order and return the created tasks."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        return t1, t2, t3

    # ------------------------------------------------------------------
    # up
    # ------------------------------------------------------------------

    def test_up_moves_task_one_position_earlier(self) -> None:
        """'up' moves a task one position toward the front of the column order."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "up")
        self.assertEqual(self._titles(), ["Beta", "Alpha", "Gamma"])

    def test_up_from_top_is_noop_for_order(self) -> None:
        """'up' on the first task leaves the column order unchanged."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "up")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_up_from_bottom(self) -> None:
        """'up' on the last task moves it one position earlier."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "up")
        self.assertEqual(self._titles(), ["Alpha", "Gamma", "Beta"])

    # ------------------------------------------------------------------
    # down
    # ------------------------------------------------------------------

    def test_down_moves_task_one_position_later(self) -> None:
        """'down' moves a task one position toward the end of the column order."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "down")
        self.assertEqual(self._titles(), ["Alpha", "Gamma", "Beta"])

    def test_down_from_bottom_is_noop_for_order(self) -> None:
        """'down' on the last task leaves the column order unchanged."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "down")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_down_from_top(self) -> None:
        """'down' on the first task moves it one position later."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "down")
        self.assertEqual(self._titles(), ["Beta", "Alpha", "Gamma"])

    # ------------------------------------------------------------------
    # top
    # ------------------------------------------------------------------

    def test_top_moves_task_to_first_position(self) -> None:
        """'top' moves a task to the front of the column order."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "top")
        self.assertEqual(self._titles(), ["Gamma", "Alpha", "Beta"])

    def test_top_from_top_is_noop_for_order(self) -> None:
        """'top' on the first task leaves the column order unchanged."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "top")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_top_from_middle(self) -> None:
        """'top' on a middle task places it first and shifts others down."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "top")
        self.assertEqual(self._titles(), ["Beta", "Alpha", "Gamma"])

    # ------------------------------------------------------------------
    # bottom
    # ------------------------------------------------------------------

    def test_bottom_moves_task_to_last_position(self) -> None:
        """'bottom' moves a task to the end of the column order."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "bottom")
        self.assertEqual(self._titles(), ["Beta", "Gamma", "Alpha"])

    def test_bottom_from_bottom_is_noop_for_order(self) -> None:
        """'bottom' on the last task leaves the column order unchanged."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "bottom")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_bottom_from_middle(self) -> None:
        """'bottom' on a middle task places it last and shifts others up."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "bottom")
        self.assertEqual(self._titles(), ["Alpha", "Gamma", "Beta"])

    # ------------------------------------------------------------------
    # above / below
    # ------------------------------------------------------------------

    def test_above_moves_task_before_a_later_one(self) -> None:
        """'above' places a task immediately before the one it is given."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "above", "gamma")
        self.assertEqual(self._titles(), ["Beta", "Alpha", "Gamma"])

    def test_above_moves_task_before_an_earlier_one(self) -> None:
        """'above' works backwards through the column as well as forwards."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "above", "beta")
        self.assertEqual(self._titles(), ["Alpha", "Gamma", "Beta"])

    def test_below_moves_task_after_an_earlier_one(self) -> None:
        """'below' places a task immediately after the one it is given."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "below", "alpha")
        self.assertEqual(self._titles(), ["Alpha", "Gamma", "Beta"])

    def test_below_moves_task_after_a_later_one(self) -> None:
        """'below' works forwards through the column as well as backwards."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "below", "beta")
        self.assertEqual(self._titles(), ["Beta", "Alpha", "Gamma"])

    def test_above_the_first_task_is_the_top(self) -> None:
        """'above' the first task puts the moved task at the head of the column."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t3, "above", "alpha")
        self.assertEqual(self._titles(), ["Gamma", "Alpha", "Beta"])

    def test_below_the_last_task_is_the_bottom(self) -> None:
        """'below' the last task puts the moved task at the end of the column."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "below", "gamma")
        self.assertEqual(self._titles(), ["Beta", "Gamma", "Alpha"])

    def test_above_itself_is_noop_for_order(self) -> None:
        """A task positioned against itself stays where it is."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "above", "beta")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_below_itself_is_noop_for_order(self) -> None:
        """A task positioned below itself stays where it is."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "below", "beta")
        self.assertEqual(self._titles(), ["Alpha", "Beta", "Gamma"])

    def test_relative_order_is_written_to_the_column_metadata(self) -> None:
        """A relative move is recorded in the column's .metadata, not only in memory."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t1, "below", "gamma")
        reread = FilesystemRepository(root=self.root)
        titles = [t.title for t in reread.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Beta", "Gamma", "Alpha"])

    def test_above_raises_value_error_without_a_reference(self) -> None:
        """'above' with no task to position against is not a usable request."""
        t1, t2, t3 = self._setup_three()
        with self.assertRaises(ValueError):
            self.repo.reorder_task(t2, "above")

    def test_below_raises_task_not_found_for_unknown_reference(self) -> None:
        """'below' a task the column does not hold raises TaskNotFound."""
        t1, t2, t3 = self._setup_three()
        with self.assertRaises(TaskNotFound):
            self.repo.reorder_task(t2, "below", "ghost")

    # ------------------------------------------------------------------
    # updated_at
    # ------------------------------------------------------------------

    def test_updated_at_is_refreshed(self) -> None:
        """reorder_task updates the task's updated_at timestamp."""
        t1, t2, t3 = self._setup_three()
        original_updated_at = t2.updated_at
        time.sleep(0.01)
        result = self.repo.reorder_task(t2, "up")
        self.assertGreater(result.updated_at, original_updated_at)

    def test_updated_at_persisted_to_disk(self) -> None:
        """The refreshed updated_at is written to the task file and readable back."""
        t1, t2, t3 = self._setup_three()
        time.sleep(0.01)
        result = self.repo.reorder_task(t2, "up")
        reloaded = self.repo.get_task("proj", "todo", "beta")
        self.assertEqual(reloaded.updated_at, result.updated_at)

    def test_updated_at_refreshed_even_when_order_unchanged(self) -> None:
        """updated_at is refreshed even when the task is already at the boundary."""
        t1, t2, t3 = self._setup_three()
        original_updated_at = t1.updated_at
        time.sleep(0.01)
        result = self.repo.reorder_task(t1, "up")
        self.assertGreater(result.updated_at, original_updated_at)

    # ------------------------------------------------------------------
    # return value
    # ------------------------------------------------------------------

    def test_returns_task_with_correct_identifiers(self) -> None:
        """Returned task preserves the board, column, and slug of the original."""
        t1, t2, t3 = self._setup_three()
        result = self.repo.reorder_task(t2, "down")
        self.assertEqual(result.board, "proj")
        self.assertEqual(result.column, "todo")
        self.assertEqual(result.slug, "beta")

    def test_other_tasks_unaffected(self) -> None:
        """Tasks that were not reordered retain their own data."""
        t1, t2, t3 = self._setup_three()
        self.repo.reorder_task(t2, "top")
        reloaded_alpha = self.repo.get_task("proj", "todo", "alpha")
        self.assertEqual(reloaded_alpha.title, "Alpha")
        reloaded_gamma = self.repo.get_task("proj", "todo", "gamma")
        self.assertEqual(reloaded_gamma.title, "Gamma")

    # ------------------------------------------------------------------
    # single-task column
    # ------------------------------------------------------------------

    def test_single_task_up_is_noop(self) -> None:
        """'up' with one task in the column leaves the order intact."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.reorder_task(task, "up")
        self.assertEqual(self._titles(), ["Alpha"])

    def test_single_task_down_is_noop(self) -> None:
        """'down' with one task in the column leaves the order intact."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.reorder_task(task, "down")
        self.assertEqual(self._titles(), ["Alpha"])

    # ------------------------------------------------------------------
    # error cases
    # ------------------------------------------------------------------

    def test_raises_task_not_found_for_unknown_task(self) -> None:
        """Raises TaskNotFound when the task slug is not present in the column order."""
        phantom = self._task("Ghost", "ghost")
        with self.assertRaises(TaskNotFound):
            self.repo.reorder_task(phantom, "up")

    def test_raises_value_error_for_invalid_op(self) -> None:
        """Raises ValueError when op is not one of up/down/top/bottom."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        with self.assertRaises(ValueError):
            self.repo.reorder_task(task, "sideways")


if __name__ == "__main__":
    unittest.main()
