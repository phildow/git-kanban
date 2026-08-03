"""Tests for KanbanService.get_tasks filtering."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from kanban.models import Slug, Task, TaskFilter, UserContext
from kanban.services.git import GitService
from kanban.services.index import IndexService
from kanban.index.memory import InMemoryIndex
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository


_UTC = timezone.utc
_SOON = datetime.now(_UTC) + timedelta(days=2)
_LATER = datetime.now(_UTC) + timedelta(days=30)


def _task(
    title: str,
    board: str = "main",
    column: str = "todo",
    *,
    assigned_to: str | None = None,
    priority: str | None = None,
    tags: list[str] | None = None,
    due_date: datetime | None = None,
    created_by: str | None = None,
) -> Task:
    slug = title.lower().replace(" ", "-")
    return Task(
        id=uuid4(),
        title=title,
        slug=slug,
        board=board,
        column=column,
        assigned_to=assigned_to,
        priority=priority,
        tags=tags or [],
        due_date=due_date,
        created_by=created_by,
    )


class TestKanbanServiceGetTasksFilter(unittest.TestCase):
    """KanbanService.get_tasks applies TaskFilter before sorting."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )
        self.svc.create_board("main", columns=[("To Do", "todo"), ("Done", "done")])

        self.t1 = self.repo.create_task(
            _task("Fix login bug", assigned_to="alice", priority="high",
                  tags=["bug"], due_date=_SOON, created_by="carol"),
            "fix-login-bug",
        )
        self.t2 = self.repo.create_task(
            _task("Write API docs", assigned_to="bob", priority="low",
                  tags=["docs"], due_date=_LATER, created_by="dave"),
            "write-api-docs",
        )
        self.t3 = self.repo.create_task(
            _task("Add rate limiting", assigned_to="alice", priority="high",
                  tags=["bug", "auth"], due_date=_SOON, created_by="carol"),
            "add-rate-limiting",
        )

    def test_no_filter_returns_all_tasks(self) -> None:
        """An empty TaskFilter returns all tasks unmodified."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(), sort=None)
        self.assertEqual({t.id for t in tasks}, {self.t1.id, self.t2.id, self.t3.id})

    def test_none_path_uses_working_board_when_available(self) -> None:
        """When path is None, get_tasks scopes to working_board if one is active."""
        self.svc.create_board("ops", columns=[("To Do", "todo")])
        other_task = self.repo.create_task(_task("Ops task", board="ops", column="todo"), "ops-task")

        self.svc.set_board(Slug("main"))
        tasks = self.svc.get_tasks(path=None, filter=TaskFilter(), sort=None)

        self.assertEqual({t.id for t in tasks}, {self.t1.id, self.t2.id, self.t3.id})
        self.assertNotIn(other_task.id, {t.id for t in tasks})

    def test_filter_by_assigned_to(self) -> None:
        """assigned_to narrows to tasks assigned to that user."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(assigned_to="alice"), sort=None)
        self.assertEqual({t.id for t in tasks}, {self.t1.id, self.t3.id})

    def test_filter_by_priority(self) -> None:
        """priority narrows to tasks with that priority level."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(priority="low"), sort=None)
        self.assertEqual([t.id for t in tasks], [self.t2.id])

    def test_filter_by_tag(self) -> None:
        """A single tag matches tasks carrying that tag."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(tags=["auth"]), sort=None)
        self.assertEqual([t.id for t in tasks], [self.t3.id])

    def test_filter_by_multiple_tags_returns_union(self) -> None:
        """Multiple tags match tasks that carry any one of them (OR semantics)."""
        # t2 has "docs", t3 has "auth" — both should be returned
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(tags=["docs", "auth"]), sort=None)
        self.assertEqual({t.id for t in tasks}, {self.t2.id, self.t3.id})

    def test_filter_by_multiple_tags_with_overlap(self) -> None:
        """Tasks matching more than one filter tag are included only once."""
        # t1 has "bug", t3 has "bug" and "auth" — t3 matches both filter tags but appears once
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(tags=["bug", "auth"]), sort=None)
        self.assertEqual({t.id for t in tasks}, {self.t1.id, self.t3.id})

    def test_filter_by_multiple_tags_one_unknown(self) -> None:
        """An unknown tag in the filter list is ignored; known tags still match."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(tags=["auth", "nonexistent"]), sort=None)
        self.assertEqual([t.id for t in tasks], [self.t3.id])

    def test_filter_by_created_by(self) -> None:
        """created_by narrows to tasks created by that user."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(created_by="dave"), sort=None)
        self.assertEqual([t.id for t in tasks], [self.t2.id])

    def test_filter_by_due_before(self) -> None:
        """due_before excludes tasks due on or after the cutoff."""
        cutoff = datetime.now(_UTC) + timedelta(days=10)
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(due_before=cutoff), sort=None)
        self.assertEqual({t.id for t in tasks}, {self.t1.id, self.t3.id})

    def test_filter_by_due_after(self) -> None:
        """due_after excludes tasks due on or before the cutoff."""
        cutoff = datetime.now(_UTC) + timedelta(days=10)
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(due_after=cutoff), sort=None)
        self.assertEqual([t.id for t in tasks], [self.t2.id])

    def test_combined_filter(self) -> None:
        """Multiple criteria are ANDed together."""
        f = TaskFilter(assigned_to="alice", priority="high", tags=["auth"])
        tasks = self.svc.get_tasks(path="/main", filter=f, sort=None)
        self.assertEqual([t.id for t in tasks], [self.t3.id])

    def test_filter_with_no_matches_returns_empty(self) -> None:
        """A filter that matches nothing returns an empty list."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(assigned_to="nobody"), sort=None)
        self.assertEqual(tasks, [])

    def test_filter_applied_before_sort(self) -> None:
        """Filtered tasks are sorted correctly."""
        tasks = self.svc.get_tasks(
            path="/main",
            filter=TaskFilter(assigned_to="alice"),
            sort="title",
        )
        self.assertEqual([t.title for t in tasks], ["Add rate limiting", "Fix login bug"])


class TestKanbanServiceGetTasksFilterNullValues(unittest.TestCase):
    """Tasks whose filtered property is None/empty are excluded by every filter criterion."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )
        self.svc.create_board("main", columns=[("To Do", "todo")])

        self.with_values = self.repo.create_task(
            _task("Has everything", assigned_to="alice", priority="high",
                  tags=["bug"], due_date=_SOON, created_by="carol"),
            "has-everything",
        )
        self.no_values = self.repo.create_task(
            _task("Has nothing"),
            "has-nothing",
        )

    def _ids(self, tasks) -> set:
        return {t.id for t in tasks}

    def test_null_assigned_to_excluded_by_assigned_to_filter(self) -> None:
        """Task with no assigned_to is not returned when filtering by assigned_to."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(assigned_to="alice"), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))

    def test_null_priority_excluded_by_priority_filter(self) -> None:
        """Task with no priority is not returned when filtering by priority."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(priority="high"), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))

    def test_empty_tags_excluded_by_tag_filter(self) -> None:
        """Task with no tags is not returned when filtering by tag."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(tags=["bug"]), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))

    def test_null_created_by_excluded_by_created_by_filter(self) -> None:
        """Task with no created_by is not returned when filtering by created_by."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(created_by="carol"), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))

    def test_null_due_date_excluded_by_due_before_filter(self) -> None:
        """Task with no due_date is not returned when filtering by due_before."""
        cutoff = datetime.now(_UTC) + timedelta(days=10)
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(due_before=cutoff), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))

    def test_null_due_date_excluded_by_due_after_filter(self) -> None:
        """Task with no due_date is not returned when filtering by due_after."""
        cutoff = datetime.now(_UTC) - timedelta(days=1)
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(due_after=cutoff), sort=None)
        self.assertIn(self.with_values.id, self._ids(tasks))
        self.assertNotIn(self.no_values.id, self._ids(tasks))


class TestKanbanServiceGetTasksExcludeColumns(unittest.TestCase):
    """TaskFilter.exclude_columns drops tasks belonging to the named columns."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=GitService(),
        )
        # "Later" rather than "Archive": this suite is about excluding an
        # ordinary column, and a column slugged `archive` is the board's archive,
        # which board-wide listings leave out on their own.
        self.svc.create_board("main", columns=[("To Do", "todo"), ("Done", "done"), ("Later", "later")])

        self.todo_task = self.repo.create_task(_task("Fix login bug", column="todo"), "fix-login-bug")
        self.done_task = self.repo.create_task(_task("Write API docs", column="done"), "write-api-docs")
        self.later_task = self.repo.create_task(_task("Old task", column="later"), "old-task")

    def _ids(self, tasks) -> set:
        return {t.id for t in tasks}

    def test_excludes_tasks_in_named_column(self) -> None:
        """A single excluded column drops only that column's tasks."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(exclude_columns=["done"]), sort=None)
        self.assertEqual(self._ids(tasks), {self.todo_task.id, self.later_task.id})

    def test_excludes_tasks_in_multiple_named_columns(self) -> None:
        """Multiple excluded columns drop tasks from all of them."""
        tasks = self.svc.get_tasks(
            path="/main", filter=TaskFilter(exclude_columns=["done", "later"]), sort=None
        )
        self.assertEqual(self._ids(tasks), {self.todo_task.id})

    def test_empty_exclude_columns_returns_all_tasks(self) -> None:
        """An empty exclude_columns list filters nothing."""
        tasks = self.svc.get_tasks(path="/main", filter=TaskFilter(exclude_columns=[]), sort=None)
        self.assertEqual(self._ids(tasks), {self.todo_task.id, self.done_task.id, self.later_task.id})

    def test_exclude_columns_combined_with_other_filters(self) -> None:
        """exclude_columns is ANDed with other active filter criteria."""
        self.repo.create_task(
            _task("Assigned in done", column="done", assigned_to="alice"), "assigned-in-done"
        )
        tasks = self.svc.get_tasks(
            path="/main",
            filter=TaskFilter(assigned_to="alice", exclude_columns=["done"]),
            sort=None,
        )
        self.assertEqual(tasks, [])


if __name__ == "__main__":
    unittest.main()
