"""Tests for archiving: the archive column, and the tasks that sit in it."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.index.memory import InMemoryIndex
from kanban.models import Slug, TaskFilter
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.index import IndexService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


def _make_service() -> tuple[KanbanService, InMemoryRepository]:
    """Return a service backed by an in-memory repository holding an `alpha` board."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=IndexService(index_base=InMemoryIndex(), repository=repo),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )
    svc.create_board("alpha", columns=[("To Do", Slug("todo")), ("Done", Slug("done"))])
    return svc, repo


class TestArchiveColumn(unittest.TestCase):
    """The archive column is found by its role and created when a board lacks one."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()

    def test_new_board_has_an_archive_column(self) -> None:
        """create_board leaves the board with an archive column."""
        column = self.svc.archive_column(Slug("alpha"))

        self.assertIsNotNone(column)
        self.assertEqual(column.slug, "archive")

    def test_archive_column_is_found_after_a_rename(self) -> None:
        """The archive is identified by role, so renaming it does not lose it."""
        self.svc.rename_column(Path("/alpha/archive"), "Attic")

        column = self.svc.archive_column(Slug("alpha"))

        self.assertIsNotNone(column)
        self.assertEqual(column.slug, "attic")
        self.assertTrue(column.is_archive)

    def test_archive_column_is_none_when_the_board_has_none(self) -> None:
        """A board with no archive column reports none rather than guessing."""
        self.repo.delete_column(Slug("alpha"), Slug("archive"))

        self.assertIsNone(self.svc.archive_column(Slug("alpha")))

    def test_ensure_archive_column_returns_the_existing_one(self) -> None:
        """ensure_archive_column does not create a second archive."""
        existing = self.svc.archive_column(Slug("alpha"))

        self.assertEqual(self.svc.ensure_archive_column(Slug("alpha")).id, existing.id)

    def test_ensure_archive_column_creates_one_when_missing(self) -> None:
        """A board that predates archiving gets an archive column on demand."""
        self.repo.delete_column(Slug("alpha"), Slug("archive"))

        column = self.svc.ensure_archive_column(Slug("alpha"))

        self.assertTrue(column.is_archive)
        self.assertEqual(column.slug, "archive")

    def test_ensure_archive_column_refuses_to_take_over_an_ordinary_column(self) -> None:
        """An unmarked column already at the archive's slug is not adopted."""
        self.repo.delete_column(Slug("alpha"), Slug("archive"))
        self.repo.create_column(Slug("alpha"), "Archive", Slug("archive"))

        with self.assertRaises(ValueError):
            self.svc.ensure_archive_column(Slug("alpha"))

    def test_archive_column_is_scoped_to_the_named_board(self) -> None:
        """The board is named absolutely, not resolved against the active board."""
        self.svc.create_board("beta", columns=[("To Do", Slug("todo"))])
        self.svc.working_board = Slug("alpha")

        column = self.svc.archive_column(Slug("beta"))

        self.assertIsNotNone(column)
        self.assertEqual(column.board, "beta")


class TestArchiveTask(unittest.TestCase):
    """archive_task and unarchive_task move a task in and out of the archive."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.task = self.svc.create_task(
            Path("/alpha/todo"), TaskCreateParams(title="Fix login")
        )

    def test_archive_task_moves_it_into_the_archive(self) -> None:
        """The task lands in the archive column."""
        archived = self.svc.archive_task(self.task.path)

        self.assertEqual(archived.column, "archive")

    def test_archive_task_keeps_the_task_id(self) -> None:
        """Archiving is a move: identity is unchanged."""
        archived = self.svc.archive_task(self.task.path)

        self.assertEqual(archived.id, self.task.id)

    def test_unarchive_task_returns_it_to_the_first_column(self) -> None:
        """Without a named column the task goes back to where the workflow starts."""
        self.svc.archive_task(self.task.path)

        restored = self.svc.unarchive_task(Path("/alpha/archive/fix-login"))

        self.assertEqual(restored.column, "todo")

    def test_unarchive_task_honours_a_named_column(self) -> None:
        """A column given by the caller is where the task lands."""
        self.svc.archive_task(self.task.path)

        restored = self.svc.unarchive_task(
            Path("/alpha/archive/fix-login"), Slug("done")
        )

        self.assertEqual(restored.column, "done")

    def test_archive_task_creates_the_column_when_the_board_has_none(self) -> None:
        """Archiving on a board without an archive makes one first."""
        self.repo.delete_column(Slug("alpha"), Slug("archive"))

        archived = self.svc.archive_task(self.task.path)

        self.assertEqual(archived.column, "archive")
        self.assertTrue(self.svc.get_column(archived.path.parent).is_archive)


class TestMoveTaskIntoTheArchive(unittest.TestCase):
    """An ordinary move is all archiving and unarchiving are."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.task = self.svc.create_task(
            Path("/alpha/todo"), TaskCreateParams(title="Fix login")
        )

    def test_moving_into_the_archive_archives_the_task(self) -> None:
        """A plain move into the archive column is how a task is archived."""
        self.svc.move_task(self.task.path, Slug("archive"))

        self.assertEqual(
            [t.slug for t in self.svc.get_tasks(Path("/alpha/archive"))], ["fix-login"]
        )

    def test_moving_out_of_the_archive_unarchives_the_task(self) -> None:
        """A plain move out of the archive column is how a task comes back."""
        self.svc.move_task(self.task.path, Slug("archive"))

        moved = self.svc.move_task(Path("/alpha/archive/fix-login"), Slug("done"))

        self.assertEqual(moved.column, "done")
        self.assertEqual(self.svc.get_tasks(Path("/alpha/archive")), [])

    def test_an_archived_task_survives_an_update(self) -> None:
        """Editing an archived task leaves it in the archive."""
        archived = self.svc.archive_task(self.task.path)

        updated = self.svc.tag_task(archived.path, "bug")

        self.assertEqual(updated.column, "archive")


class TestArchivedTasksInListings(unittest.TestCase):
    """Listings leave archived tasks out unless the archive is what was asked for."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.open_task = self.svc.create_task(
            Path("/alpha/todo"), TaskCreateParams(title="Fix login")
        )
        self.archived = self.svc.archive_task(
            self.svc.create_task(
                Path("/alpha/todo"), TaskCreateParams(title="Old news")
            ).path
        )

    def _slugs(self, tasks) -> list[str]:
        return [task.slug for task in tasks]

    def test_board_listing_omits_archived_tasks(self) -> None:
        """A board-wide listing shows the workflow, not the archive."""
        tasks = self.svc.get_tasks(Path("/alpha"))

        self.assertEqual(self._slugs(tasks), ["fix-login"])

    def test_archive_column_listing_shows_them(self) -> None:
        """Naming the archive column is how archived tasks are listed."""
        tasks = self.svc.get_tasks(Path("/alpha/archive"))

        self.assertEqual(self._slugs(tasks), ["old-news"])

    def test_include_archived_returns_them_board_wide(self) -> None:
        """The filter's include_archived is how every task there is comes back."""
        tasks = self.svc.get_tasks(Path("/alpha"), TaskFilter(include_archived=True))

        self.assertEqual(sorted(self._slugs(tasks)), ["fix-login", "old-news"])

    def test_include_archived_with_a_column_raises(self) -> None:
        """A column listing is already the whole of one column; widening it is an error."""
        with self.assertRaises(ValueError):
            self.svc.get_tasks(Path("/alpha/todo"), TaskFilter(include_archived=True))

    def test_include_archived_with_the_archive_excluded_raises(self) -> None:
        """Including and excluding the archive are opposite requests."""
        with self.assertRaises(ValueError):
            self.svc.get_tasks(
                Path("/alpha"),
                TaskFilter(exclude_columns=["archive"], include_archived=True),
            )

    def test_include_archived_with_the_archive_renamed_and_excluded_raises(self) -> None:
        """The archive is recognised by role, so its new slug is refused too."""
        self.svc.rename_column(Path("/alpha/archive"), "Cold Storage")

        with self.assertRaises(ValueError):
            self.svc.get_tasks(
                Path("/alpha"),
                TaskFilter(exclude_columns=["cold-storage"], include_archived=True),
            )

    def test_include_archived_with_another_column_excluded_is_allowed(self) -> None:
        """Excluding an ordinary column says nothing about the archive."""
        tasks = self.svc.get_tasks(
            Path("/alpha"),
            TaskFilter(exclude_columns=["done"], include_archived=True),
        )

        self.assertEqual(sorted(self._slugs(tasks)), ["fix-login", "old-news"])

    def test_a_default_filter_leaves_the_archive_out(self) -> None:
        """The filter a caller builds without a thought for the archive omits it."""
        tasks = self.svc.get_tasks(Path("/alpha"), TaskFilter())

        self.assertEqual(self._slugs(tasks), ["fix-login"])

    def test_unscoped_listing_omits_archived_tasks(self) -> None:
        """A listing across every board leaves the archives out too."""
        self.svc.working_board = None

        tasks = self.svc.get_tasks()

        self.assertEqual(self._slugs(tasks), ["fix-login"])

    def test_archived_task_is_resolved_by_its_bare_slug(self) -> None:
        """The REPL addresses an archived task by slug, as it does any other."""
        self.svc.working_board = Slug("alpha")

        task = self.svc.get_task(Slug("old-news"))

        self.assertEqual(task.column, "archive")

    def test_archived_slug_is_still_taken(self) -> None:
        """A slug in the archive cannot be reused by a new task."""
        from kanban.storage.base import TaskAlreadyExists

        with self.assertRaises(TaskAlreadyExists):
            self.svc.create_task(Path("/alpha/todo"), TaskCreateParams(title="Old news"))


class TestArchivedTasksInSearch(unittest.TestCase):
    """Search leaves the archive out, as a listing does, until asked for it."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task(Path("/alpha/todo"), TaskCreateParams(title="Login form"))
        self.svc.archive_task(
            self.svc.create_task(
                Path("/alpha/todo"), TaskCreateParams(title="Login page")
            ).path
        )

    def test_search_omits_archived_tasks(self) -> None:
        """An archived task is not among the results of an ordinary search."""
        results = self.svc.search("login")

        self.assertEqual([task.slug for task in results], ["login-form"])

    def test_search_includes_archived_tasks_when_asked(self) -> None:
        """include_archived is how a search reaches the archive."""
        results = self.svc.search("login", filter=TaskFilter(include_archived=True))

        self.assertEqual(
            sorted(task.slug for task in results), ["login-form", "login-page"]
        )

    def test_search_including_and_excluding_the_archive_raises(self) -> None:
        """The two are opposite requests here as they are in a listing."""
        with self.assertRaises(ValueError):
            self.svc.search(
                "login",
                filter=TaskFilter(exclude_columns=["archive"], include_archived=True),
            )

    def test_search_scoped_to_a_board_omits_its_archive(self) -> None:
        """Scoping to a board does not change what the archive means."""
        results = self.svc.search("login", board=Slug("alpha"))

        self.assertEqual([task.slug for task in results], ["login-form"])


if __name__ == "__main__":
    unittest.main()
