"""Tests for the commit message builder."""

from __future__ import annotations

import unittest
from uuid import UUID

from kanban.tracking import (
    BoardCommitData,
    ColumnCommitData,
    ColumnReorderCommitData,
    CommitData,
    CommitMessage,
    CommitMessageBuilder,
    TaskAssignCommitData,
    TaskCommitData,
    TaskMoveCommitData,
    TaskRenameCommitData,
    TaskTagCommitData,
)

ID = UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")


class TestCommitMessage(unittest.TestCase):
    """A message renders as a subject, a blank line, then the trailers."""

    def setUp(self) -> None:
        self.message = CommitMessage(
            subject="task(create) Fix login bug",
            trailers={"Entity": "task", "Action": "create"},
        )

    def test_text_renders_subject_and_trailers(self):
        """`text` joins the two halves with a blank line between them."""
        self.assertEqual(
            self.message.text,
            "task(create) Fix login bug\n\nEntity: task\nAction: create",
        )

    def test_str_renders_the_message(self):
        """A message stringifies to what a tracker is given."""
        self.assertEqual(str(self.message), self.message.text)


class TestBoardMessages(unittest.TestCase):
    """Board subjects and trailers."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def test_create(self):
        """A created board is named on its own."""
        data = BoardCommitData(id=ID, path="/my-project", action="create", name="My Project")

        self.assertEqual(self.builder.build(data).subject, "board(create) My Project")

    def test_rename_names_both_sides(self):
        """A renamed board shows the old name and the new."""
        data = BoardCommitData(
            id=ID,
            path="/main-project",
            action="rename",
            name="Main Project",
            old_name="My Project",
        )

        self.assertEqual(
            self.builder.build(data).subject, "board(rename) My Project → Main Project"
        )

    def test_delete(self):
        """A deleted board is named on its own."""
        data = BoardCommitData(id=ID, path="/my-project", action="delete", name="My Project")

        self.assertEqual(self.builder.build(data).subject, "board(delete) My Project")

    def test_trailers(self):
        """A board carries the four common trailers and nothing more."""
        data = BoardCommitData(id=ID, path="/my-project", action="create", name="My Project")

        self.assertEqual(
            self.builder.build(data).trailers,
            {
                "Entity": "board",
                "Action": "create",
                "Id":     str(ID),
                "Path":   "/my-project",
            },
        )


class TestColumnMessages(unittest.TestCase):
    """Column subjects and trailers."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def test_create(self):
        """A created column is named on its own."""
        data = ColumnCommitData(
            id=ID, path="/main/backlog", action="create", board="Main", name="Backlog"
        )

        self.assertEqual(self.builder.build(data).subject, "column(create) Backlog")

    def test_rename_names_both_sides(self):
        """A renamed column shows the old name and the new."""
        data = ColumnCommitData(
            id=ID,
            path="/main/todo",
            action="rename",
            board="Main",
            name="Todo",
            old_name="To Do",
        )

        self.assertEqual(self.builder.build(data).subject, "column(rename) To Do → Todo")

    def test_reorder_names_the_position(self):
        """A reordered column shows where it landed."""
        data = ColumnReorderCommitData(
            id=ID, path="/main/in-review", board="Main", name="In Review", position=2
        )

        self.assertEqual(
            self.builder.build(data).subject, "column(reorder) In Review → position 2"
        )

    def test_trailers_carry_the_board(self):
        """A column adds the board it belongs to."""
        data = ColumnCommitData(
            id=ID, path="/main/backlog", action="delete", board="Main", name="Backlog"
        )

        self.assertEqual(
            self.builder.build(data).trailers,
            {
                "Entity": "column",
                "Action": "delete",
                "Id":     str(ID),
                "Path":   "/main/backlog",
                "Board":  "Main",
            },
        )

    def test_reorder_trailers_report_the_column_action(self):
        """A reorder is a column commit with its own action."""
        data = ColumnReorderCommitData(
            id=ID, path="/main/in-review", board="Main", name="In Review", position=2
        )

        trailers = self.builder.build(data).trailers

        self.assertEqual(trailers["Entity"], "column")
        self.assertEqual(trailers["Action"], "reorder")


class TestTaskMessages(unittest.TestCase):
    """Task subjects for the operations that name no destination."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def _task(self, action: str) -> TaskCommitData:
        """Return task data for action, on the same task throughout."""
        return TaskCommitData(
            id=ID,
            path="/main/todo/fix-login-bug",
            action=action,
            board="Main",
            column="To Do",
            title="Fix login bug",
        )

    def test_create(self):
        """A created task is named on its own."""
        self.assertEqual(
            self.builder.build(self._task("create")).subject, "task(create) Fix login bug"
        )

    def test_update(self):
        """An updated task is named on its own."""
        self.assertEqual(
            self.builder.build(self._task("update")).subject, "task(update) Fix login bug"
        )

    def test_unset(self):
        """An unset field names the task alone."""
        self.assertEqual(
            self.builder.build(self._task("unset")).subject, "task(unset) Fix login bug"
        )

    def test_comment(self):
        """A comment names the task alone."""
        self.assertEqual(
            self.builder.build(self._task("comment")).subject, "task(comment) Fix login bug"
        )

    def test_delete(self):
        """A deleted task is named on its own."""
        self.assertEqual(
            self.builder.build(self._task("delete")).subject, "task(delete) Fix login bug"
        )

    def test_trailers_carry_board_and_column(self):
        """A task adds the board and the column that holds it."""
        self.assertEqual(
            self.builder.build(self._task("create")).trailers,
            {
                "Entity": "task",
                "Action": "create",
                "Id":     str(ID),
                "Path":   "/main/todo/fix-login-bug",
                "Board":  "Main",
                "Column": "To Do",
            },
        )


class TestTaskRenameMessages(unittest.TestCase):
    """A renamed task names both titles."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()
        self.data = TaskRenameCommitData(
            id=ID,
            path="/main/todo/fix-the-login-bug",
            board="Main",
            column="To Do",
            old_title="Fix login bug",
            new_title="Fix the login bug",
        )

    def test_subject(self):
        """The subject shows the old title and the new."""
        self.assertEqual(
            self.builder.build(self.data).subject,
            "task(rename) Fix login bug → Fix the login bug",
        )

    def test_trailers(self):
        """The trailers report the rename and the post-rename path."""
        trailers = self.builder.build(self.data).trailers

        self.assertEqual(trailers["Action"], "rename")
        self.assertEqual(trailers["Path"], "/main/todo/fix-the-login-bug")
        self.assertEqual(trailers["Column"], "To Do")


class TestTaskAssignMessages(unittest.TestCase):
    """Assignment names the assignee; unassignment has none to name."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def test_assign_names_the_assignee(self):
        """An assigned task points at who took it."""
        data = TaskAssignCommitData(
            id=ID,
            path="/main/todo/fix-login-bug",
            action="assign",
            board="Main",
            column="To Do",
            title="Fix login bug",
            assignee="alice",
        )

        self.assertEqual(self.builder.build(data).subject, "task(assign) Fix login bug → alice")

    def test_unassign_names_the_task_alone(self):
        """An unassigned task has no assignee to name."""
        data = TaskAssignCommitData(
            id=ID,
            path="/main/todo/fix-login-bug",
            action="unassign",
            board="Main",
            column="To Do",
            title="Fix login bug",
        )

        self.assertEqual(self.builder.build(data).subject, "task(unassign) Fix login bug")

    def test_trailers_report_the_action(self):
        """The trailer action follows the subject verb."""
        data = TaskAssignCommitData(
            id=ID,
            path="/main/todo/fix-login-bug",
            action="unassign",
            board="Main",
            column="To Do",
            title="Fix login bug",
        )

        self.assertEqual(self.builder.build(data).trailers["Action"], "unassign")


class TestTaskTagMessages(unittest.TestCase):
    """Tagging and untagging both name the tag."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def _tag(self, action: str) -> TaskTagCommitData:
        """Return tag data for action, on the same task and tag throughout."""
        return TaskTagCommitData(
            id=ID,
            path="/main/todo/fix-login-bug",
            action=action,
            board="Main",
            column="To Do",
            title="Fix login bug",
            tag="bug",
        )

    def test_tag(self):
        """A tagged task points at the tag added."""
        self.assertEqual(self.builder.build(self._tag("tag")).subject, "task(tag) Fix login bug → bug")

    def test_untag(self):
        """An untagged task points at the tag removed."""
        self.assertEqual(
            self.builder.build(self._tag("untag")).subject, "task(untag) Fix login bug → bug"
        )

    def test_trailers_report_the_action(self):
        """The trailer action follows the subject verb."""
        self.assertEqual(self.builder.build(self._tag("untag")).trailers["Action"], "untag")


class TestTaskMoveMessages(unittest.TestCase):
    """A move names where the task came from and where it went."""

    def setUp(self) -> None:
        self.builder = CommitMessageBuilder()

    def test_within_a_board_names_columns(self):
        """A move that stays on its board names the two columns."""
        data = TaskMoveCommitData(
            id=ID,
            path="/main/in-progress/fix-login-bug",
            action="move",
            title="Fix login bug",
            from_board="Main",
            from_column="Todo",
            from_path="/main/todo",
            to_board="Main",
            to_column="In Progress",
            to_path="/main/in-progress",
        )

        self.assertEqual(
            self.builder.build(data).subject,
            "task(move) Fix login bug — Todo → In Progress",
        )

    def test_across_boards_qualifies_the_destination(self):
        """A move to another board spells that board out on the destination."""
        data = TaskMoveCommitData(
            id=ID,
            path="/ops/in-progress/fix-login-bug",
            action="move",
            title="Fix login bug",
            from_board="Main",
            from_column="Todo",
            from_path="/main/todo",
            to_board="Ops",
            to_column="In Progress",
            to_path="/ops/in-progress",
        )

        self.assertEqual(
            self.builder.build(data).subject,
            "task(move) Fix login bug — Todo → Ops/In Progress",
        )

    def test_archiving_is_a_move(self):
        """Archiving carries no message of its own — it is a move to the archive."""
        data = TaskMoveCommitData(
            id=ID,
            path="/main/archive/fix-login-bug",
            action="move",
            title="Fix login bug",
            from_board="Main",
            from_column="Todo",
            from_path="/main/todo",
            to_board="Main",
            to_column="Archive",
            to_path="/main/archive",
        )

        self.assertEqual(
            self.builder.build(data).subject, "task(move) Fix login bug — Todo → Archive"
        )

    def test_trailers_carry_from_and_to(self):
        """A move reports the two column paths instead of a board and column."""
        data = TaskMoveCommitData(
            id=ID,
            path="/main/in-progress/fix-login-bug",
            action="move",
            title="Fix login bug",
            from_board="Main",
            from_column="Todo",
            from_path="/main/todo",
            to_board="Main",
            to_column="In Progress",
            to_path="/main/in-progress",
        )

        self.assertEqual(
            self.builder.build(data).trailers,
            {
                "Entity": "task",
                "Action": "move",
                "Id":     str(ID),
                "Path":   "/main/in-progress/fix-login-bug",
                "From":   "/main/todo",
                "To":     "/main/in-progress",
            },
        )


class TestUnsupportedCommitData(unittest.TestCase):
    """Data the builder does not know is refused rather than half-formatted."""

    def test_raises_type_error(self):
        """A bare `CommitData` describes no operation."""
        with self.assertRaises(TypeError):
            CommitMessageBuilder().build(CommitData(id=ID, path="/main"))


if __name__ == "__main__":
    unittest.main()
