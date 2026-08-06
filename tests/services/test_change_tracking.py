"""Tests that ChangeTrackingService composes messages and forwards calls."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import UUID, uuid4

from kanban.models.slug import Slug
from kanban.models.task import Task
from kanban.services.change_tracking import ChangeTrackingService
from kanban.storage.memory import InMemoryRepository
from kanban.tracking import (
    CommitData,
    CommitMessageBuilder,
    InMemoryChangeTracker,
    TaskCommitData,
)

ID = UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")


def task_data(action: str = "create", title: str = "Fix login bug") -> TaskCommitData:
    """Return task commit data for action, on a task in /main/todo."""
    return TaskCommitData(
        id=ID,
        path="/main/todo/fix-login-bug",
        action=action,
        board="Main",
        column="To Do",
        title=title,
    )


class ChangeTrackingTestCase(unittest.TestCase):
    """A service over an in-memory tracker and a board with two columns."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()

        self.repository = InMemoryRepository(root=temp_dir)
        self.change_tracker = InMemoryChangeTracker()
        self.service = ChangeTrackingService(self.change_tracker, self.repository)

        self.board = self.repository.create_board("Main", Slug("main"))
        self.todo = self.repository.create_column(Slug("main"), "To Do", Slug("todo"))
        self.doing = self.repository.create_column(
            Slug("main"), "In Progress", Slug("in-progress")
        )

    @property
    def message(self) -> str:
        """Return the message of the last commit written."""
        return self.change_tracker.messages[-1]

    @property
    def subject(self) -> str:
        """Return the subject line of the last commit written."""
        return self.message.splitlines()[0]

    def trailer(self, key: str) -> str:
        """Return the value of key in the last commit's trailers."""
        for line in self.message.splitlines():
            if line.startswith(f"{key}: "):
                return line.removeprefix(f"{key}: ")
        raise AssertionError(f"No {key} trailer in {self.message!r}")

    def make_task(
        self,
        title:  str = "Fix login bug",
        column: Slug = Slug("todo"),
    ) -> Task:
        """Return a task created in the given column of the main board."""
        slug = Slug(title.lower().replace(" ", "-"))
        task = Task(
            id=uuid4(),
            title=title,
            slug=slug,
            board=Slug("main"),
            column=column,
        )
        return self.repository.create_task(task, slug)


class TestBoardCommits(ChangeTrackingTestCase):
    """Board operations commit the message the schema describes."""

    def test_create(self):
        """A created board names itself."""
        self.service.commit_board_create(self.board)

        self.assertEqual(self.subject, "board(create) Main")
        self.assertEqual(self.trailer("Entity"), "board")
        self.assertEqual(self.trailer("Path"), "/main")

    def test_rename(self):
        """A renamed board names both sides."""
        self.board.name = "Main Project"

        self.service.commit_board_rename(self.board, "Main")

        self.assertEqual(self.subject, "board(rename) Main → Main Project")
        self.assertEqual(self.trailer("Action"), "rename")

    def test_delete(self):
        """A deleted board names itself."""
        self.service.commit_board_delete(self.board)

        self.assertEqual(self.subject, "board(delete) Main")
        self.assertEqual(self.trailer("Action"), "delete")


class TestColumnCommits(ChangeTrackingTestCase):
    """Column operations carry the board they belong to."""

    def test_create(self):
        """A created column names itself and its board."""
        self.service.commit_column_create(self.todo)

        self.assertEqual(self.subject, "column(create) To Do")
        self.assertEqual(self.trailer("Board"), "Main")
        self.assertEqual(self.trailer("Path"), "/main/todo")

    def test_rename(self):
        """A renamed column names both sides."""
        self.todo.name = "Todo"

        self.service.commit_column_rename(self.todo, "To Do")

        self.assertEqual(self.subject, "column(rename) To Do → Todo")

    def test_reorder_reports_the_position_held(self):
        """A reordered column reports where it now sits."""
        self.service.commit_column_reorder(self.doing)

        self.assertEqual(self.subject, "column(reorder) In Progress → position 1")
        self.assertEqual(self.trailer("Action"), "reorder")

    def test_delete(self):
        """A deleted column names itself."""
        self.service.commit_column_delete(self.todo)

        self.assertEqual(self.subject, "column(delete) To Do")


class TestTaskCommits(ChangeTrackingTestCase):
    """Task operations resolve the board and column names from the repository."""

    def setUp(self) -> None:
        super().setUp()
        self.task = self.make_task()

    def test_create(self):
        """A created task names itself, and its trailers locate it."""
        self.service.commit_task_create(self.task)

        self.assertEqual(self.subject, "task(create) Fix login bug")
        self.assertEqual(self.trailer("Board"), "Main")
        self.assertEqual(self.trailer("Column"), "To Do")
        self.assertEqual(self.trailer("Path"), "/main/todo/fix-login-bug")

    def test_update(self):
        """An update names the task alone."""
        self.service.commit_task_update(self.task)

        self.assertEqual(self.subject, "task(update) Fix login bug")

    def test_unset(self):
        """An unset names the task alone."""
        self.service.commit_task_unset(self.task)

        self.assertEqual(self.trailer("Action"), "unset")

    def test_comment(self):
        """A comment names the task alone."""
        self.service.commit_task_comment(self.task)

        self.assertEqual(self.subject, "task(comment) Fix login bug")

    def test_delete(self):
        """A delete names the task alone."""
        self.service.commit_task_delete(self.task)

        self.assertEqual(self.subject, "task(delete) Fix login bug")

    def test_rename(self):
        """A rename names both titles."""
        self.task.title = "Fix the login bug"

        self.service.commit_task_rename(self.task, "Fix login bug")

        self.assertEqual(self.subject, "task(rename) Fix login bug → Fix the login bug")

    def test_assign_reads_the_assignee_from_the_task(self):
        """An assignment points at whoever the task now names."""
        self.task.assigned_to = "alice"

        self.service.commit_task_assign(self.task)

        self.assertEqual(self.subject, "task(assign) Fix login bug → alice")

    def test_unassign(self):
        """An unassignment has no assignee to name."""
        self.service.commit_task_unassign(self.task)

        self.assertEqual(self.subject, "task(unassign) Fix login bug")

    def test_tag(self):
        """A tag added is named in the subject."""
        self.service.commit_task_tag(self.task, "bug")

        self.assertEqual(self.subject, "task(tag) Fix login bug → bug")

    def test_untag(self):
        """A tag removed is named in the subject."""
        self.service.commit_task_untag(self.task, "bug")

        self.assertEqual(self.subject, "task(untag) Fix login bug → bug")


class TestTaskMoveCommits(ChangeTrackingTestCase):
    """A move names the columns it spans and both column paths."""

    def setUp(self) -> None:
        super().setUp()
        self.task = self.make_task()

    def test_within_a_board(self):
        """A move on one board names the two columns."""
        moved = self.repository.move_task(self.task, Slug("in-progress"))

        self.service.commit_task_move(moved, Slug("main"), Slug("todo"))

        self.assertEqual(self.subject, "task(move) Fix login bug — To Do → In Progress")
        self.assertEqual(self.trailer("From"), "/main/todo")
        self.assertEqual(self.trailer("To"), "/main/in-progress")

    def test_across_boards_qualifies_the_destination(self):
        """A move to another board spells that board out."""
        self.repository.create_board("Ops", Slug("ops"))
        self.repository.create_column(Slug("ops"), "Backlog", Slug("backlog"))
        moved = self.repository.move_task(self.task, Slug("backlog"), Slug("ops"))

        self.service.commit_task_move(moved, Slug("main"), Slug("todo"))

        self.assertEqual(self.subject, "task(move) Fix login bug — To Do → Ops/Backlog")
        self.assertEqual(self.trailer("To"), "/ops/backlog")

    def test_archiving_commits_as_a_move(self):
        """Archiving is a move into the archive column and reads as one."""
        self.repository.create_column(
            Slug("main"), "Archive", Slug("archive"), role="archive"
        )
        moved = self.repository.move_task(self.task, Slug("archive"))

        self.service.commit_task_move(moved, Slug("main"), Slug("todo"))

        self.assertEqual(self.subject, "task(move) Fix login bug — To Do → Archive")
        self.assertEqual(self.trailer("Action"), "move")


class TestNameResolution(ChangeTrackingTestCase):
    """Names come from the repository, and a missing one falls back to the slug."""

    def test_uses_display_names_not_slugs(self):
        """The message reads in display names even though the task holds slugs."""
        task = self.make_task()

        self.service.commit_task_create(task)

        self.assertEqual(self.trailer("Column"), "To Do")

    def test_falls_back_to_the_slug_for_a_missing_column(self):
        """A column that has gone missing is reported by slug rather than raised."""
        task = self.make_task()
        self.repository.delete_column(Slug("main"), Slug("todo"))

        self.service.commit_task_create(task)

        self.assertEqual(self.trailer("Column"), "todo")

    def test_falls_back_to_the_slug_for_a_missing_board(self):
        """A board that has gone missing is reported by slug rather than raised."""
        task = self.make_task()
        self.repository.delete_board(Slug("main"))

        self.service.commit_task_create(task)

        self.assertEqual(self.trailer("Board"), "main")


class TestChangeTrackingForwarding(ChangeTrackingTestCase):
    """Every other call reaches the injected implementation unchanged."""

    def test_initialize_forwards_worktree_settings(self):
        """`initialize()` hands the root, worktree, and branch straight down."""
        self.service.initialize(Path("/tmp/project"), worktree=".store", branch="tasks")

        self.assertTrue(self.change_tracker.is_initialized)
        self.assertEqual(self.change_tracker.worktree, ".store")
        self.assertEqual(self.change_tracker.branch, "tasks")

    def test_is_initialized_reports_the_implementation(self):
        """The property reads through rather than tracking state of its own."""
        self.assertFalse(self.service.is_initialized)

        self.change_tracker.initialize(Path("/tmp/project"))

        self.assertTrue(self.service.is_initialized)

    def test_add_commit_writes_the_composed_message(self):
        """A commit made through the service carries the message the builder composed."""
        commit = self.service.add_commit(task_data(), Path("main/todo"))

        self.assertEqual(self.change_tracker.commits, [commit])
        self.assertEqual(self.message, self.service.build_message(task_data()).text)

    def test_the_tracker_is_handed_the_message_whole(self):
        """The implementation receives subject and trailers, not rendered text."""
        self.service.commit_board_create(self.board)

        written = self.change_tracker.commit_messages[-1]

        self.assertEqual(written.subject, "board(create) Main")
        self.assertEqual(written.trailers["Entity"], "board")

    def test_add_commit_refuses_unknown_data(self):
        """Data describing no operation is refused before anything is written."""
        with self.assertRaises(TypeError):
            self.service.add_commit(CommitData(id=ID, path="/main"))

        self.assertEqual(self.change_tracker.messages, [])

    def test_operations_commit_the_whole_store(self):
        """A per-operation commit is scoped to the store, never to one path."""
        self.service.commit_board_create(self.board)

        self.assertEqual(self.change_tracker.paths, [None])

    def test_squash_commits_forwards(self):
        """The squash collapses the implementation's history."""
        self.service.commit_board_create(self.board)
        self.service.commit_column_create(self.todo)

        self.service.squash_commits("squash: all")

        self.assertEqual(self.change_tracker.messages, ["squash: all"])

    def test_get_history_forwards_path_and_limit(self):
        """History comes back scoped and limited as the implementation returns it."""
        self.service.add_commit(task_data("create"), Path("main/todo"))
        self.service.add_commit(task_data("delete"), Path("main/done"))

        history = self.service.get_history(Path("main/todo"), limit=5)

        self.assertEqual(len(history), 1)
        self.assertTrue(history[0].message.startswith("task(create)"))

    def test_has_uncommitted_changes_forwards(self):
        """What the implementation holds pending is what the service reports."""
        self.assertFalse(self.service.has_uncommitted_changes())

        self.change_tracker.record_change(Path("main/todo/a-task.md"))

        self.assertTrue(self.service.has_uncommitted_changes(Path("main/todo")))

    def test_sync_forwards(self):
        """A sync runs both halves on the implementation."""
        self.service.sync()

        self.assertEqual(self.change_tracker.pulls, 1)
        self.assertEqual(self.change_tracker.pushes, 1)


class TestChangeTrackingBuilder(ChangeTrackingTestCase):
    """The service composes with a builder it is given or supplies its own."""

    def test_supplies_a_builder_by_default(self):
        """A service constructed without one still composes."""
        self.assertIsInstance(self.service.message_builder, CommitMessageBuilder)

    def test_keeps_an_injected_builder(self):
        """A builder passed in is the one the service composes with."""
        builder = CommitMessageBuilder()
        service = ChangeTrackingService(self.change_tracker, self.repository, builder)

        self.assertIs(service.message_builder, builder)

    def test_build_message_writes_nothing(self):
        """Composing a message on its own leaves the history alone."""
        message = self.service.build_message(task_data())

        self.assertEqual(message.subject, "task(create) Fix login bug")
        self.assertEqual(self.change_tracker.commits, [])


if __name__ == "__main__":
    unittest.main()
