"""Tests for the `Task` model: its path, and its markdown body sections."""

from __future__ import annotations

import unittest

from pathlib import Path
from uuid import uuid4

from kanban.models import Slug, Task
from kanban.models.task import comments_of, description_of


def make_task(body: str = "") -> Task:
    """Return a task carrying `body`."""
    return Task(
        id=uuid4(),
        title="Fix login bug",
        slug=Slug("fix-login-bug"),
        board=Slug("main"),
        column=Slug("todo"),
        body=body,
    )


class TestTaskAPath(unittest.TestCase):
    """Verifies the `path` property of `Task`."""

    def test_path_is_absolute_and_includes_board_and_column_and_filename(self):
        """`path` is an absolute path containing the board's slug, the column's slug, and the task's filename."""
        task = Task(
            id=uuid4(),
            title="Fix login bug",
            slug="fix-login-bug",
            board="my-project",
            column="todo",
        )
        self.assertEqual(task.path, Path("/my-project/todo/fix-login-bug"))
        self.assertTrue(task.path.is_absolute())


class TestSetDescription(unittest.TestCase):
    """Task.set_description writes the section between Description and Comments."""

    def test_empty_body_and_empty_description_produces_heading(self) -> None:
        """An empty body and empty description yields just the `# Description` heading."""
        task = make_task()
        task.set_description("")
        self.assertEqual(task.body, "# Description\n\n")

    def test_empty_body_and_content_description_produces_heading_and_body(self) -> None:
        """An empty body with content becomes a heading followed by the description."""
        task = make_task()
        task.set_description("hello world")
        self.assertEqual(task.body, "# Description\n\nhello world\n")

    def test_replaces_existing_description_content(self) -> None:
        """Existing content under `# Description` is replaced by the new description."""
        task = make_task("# Description\n\nold content")
        task.set_description("new content")
        self.assertEqual(task.body, "# Description\n\nnew content\n")

    def test_preserves_comments_section(self) -> None:
        """A `# Comments` section following the description is preserved unchanged."""
        task = make_task("# Description\n\nold\n\n# Comments\n\nA remark")
        task.set_description("new")
        self.assertEqual(task.body, "# Description\n\nnew\n\n# Comments\n\nA remark\n")

    def test_inserts_description_heading_when_missing(self) -> None:
        """A body without a `# Description` heading gets one inserted at the top."""
        task = make_task("# Comments\n\nA remark")
        task.set_description("new")
        self.assertEqual(task.body, "# Description\n\nnew\n\n# Comments\n\nA remark\n")

    def test_empty_description_leaves_only_heading(self) -> None:
        """An empty description clears the description body, leaving the heading."""
        task = make_task("# Description\n\nold content\n\n# Comments\n\nremark")
        task.set_description("")
        self.assertEqual(task.body, "# Description\n\n\n# Comments\n\nremark\n")

    def test_mutates_in_place(self) -> None:
        """The task itself is changed; nothing is returned to assign back."""
        task = make_task()
        self.assertIsNone(task.set_description("hello"))
        self.assertIn("hello", task.body)


class TestDescriptionOf(unittest.TestCase):
    """description_of returns the text under the Description heading."""

    def test_reads_the_description(self) -> None:
        """The text below the heading is the description."""
        self.assertEqual(description_of("# Description\n\nhello world\n"), "hello world")

    def test_stops_at_the_comments_heading(self) -> None:
        """Comments are a separate section and are not part of the description."""
        body = "# Description\n\nhello\n\n# Comments\n\na note\n"
        self.assertEqual(description_of(body), "hello")

    def test_keeps_internal_blank_lines(self) -> None:
        """Paragraphs within the description survive."""
        self.assertEqual(description_of("# Description\n\nfirst\n\nsecond\n"), "first\n\nsecond")

    def test_empty_description_section(self) -> None:
        """A heading with nothing under it is an empty description."""
        self.assertEqual(description_of("# Description\n\n"), "")

    def test_body_without_a_heading(self) -> None:
        """A body with no Description heading has no description."""
        self.assertEqual(description_of("just some text"), "")

    def test_empty_body(self) -> None:
        """An empty body has no description."""
        self.assertEqual(description_of(""), "")


class TestTaskDescriptionProperty(unittest.TestCase):
    """Task.description reads the task's own body."""

    def test_reads_from_the_body(self) -> None:
        """The property reports what the body holds."""
        self.assertEqual(make_task("# Description\n\nhello world\n").description, "hello world")

    def test_task_with_no_body(self) -> None:
        """A task with an empty body has no description."""
        self.assertEqual(make_task().description, "")

    def test_reads_back_what_was_written(self) -> None:
        """A description survives being written and read."""
        task = make_task()
        task.set_description("hello world")
        self.assertEqual(task.description, "hello world")


class TestAppendComment(unittest.TestCase):
    """Task.append_comment produces the correct body layout."""

    def test_empty_body_produces_heading_and_comment(self) -> None:
        """An empty body becomes a `# Comments` heading followed by the comment."""
        task = make_task()
        task.append_comment("hi")
        self.assertEqual(task.body, "# Comments\n\nhi")

    def test_body_without_heading_adds_heading(self) -> None:
        """A non-empty body without the heading gets the heading before the comment."""
        task = make_task("# Description\n\nSome text.")
        task.append_comment("hi")
        self.assertEqual(task.body, "# Description\n\nSome text.\n\n# Comments\n\nhi")

    def test_body_with_heading_appends_only_comment(self) -> None:
        """A body already containing the heading only receives the new comment."""
        task = make_task("# Comments\n\nfirst")
        task.append_comment("second")
        self.assertEqual(task.body, "# Comments\n\nfirst\n\nsecond")

    def test_trailing_whitespace_is_stripped_from_body(self) -> None:
        """Trailing whitespace in the original body is trimmed before appending."""
        task = make_task("# Description\n\nSome text.\n\n\n")
        task.append_comment("hi")
        self.assertEqual(task.body, "# Description\n\nSome text.\n\n# Comments\n\nhi")

    def test_mutates_in_place(self) -> None:
        """The task itself is changed; nothing is returned to assign back."""
        task = make_task()
        self.assertIsNone(task.append_comment("hi"))
        self.assertIn("hi", task.body)


class TestCommentsOf(unittest.TestCase):
    """comments_of returns the text under the Comments heading."""

    def test_reads_a_comment(self) -> None:
        """The text below the heading is the comments."""
        self.assertEqual(comments_of("# Comments\n\na note\n"), "a note")

    def test_reads_several_comments(self) -> None:
        """Comments are returned as written, blank lines and all."""
        body = "# Comments\n\nfirst\n\nsecond\n"
        self.assertEqual(comments_of(body), "first\n\nsecond")

    def test_starts_after_the_description(self) -> None:
        """The description above is not part of the comments."""
        body = "# Description\n\nhello\n\n# Comments\n\na note\n"
        self.assertEqual(comments_of(body), "a note")

    def test_body_without_a_heading(self) -> None:
        """A body with no Comments heading has no comments."""
        self.assertEqual(comments_of("# Description\n\nhello\n"), "")

    def test_empty_body(self) -> None:
        """An empty body has no comments."""
        self.assertEqual(comments_of(""), "")


class TestTaskCommentsProperty(unittest.TestCase):
    """Task.comments reads the task's own body."""

    def test_reads_from_the_body(self) -> None:
        """The property reports what the body holds."""
        self.assertEqual(make_task("# Comments\n\na note\n").comments, "a note")

    def test_task_with_no_comments(self) -> None:
        """A task with no Comments section reports none."""
        self.assertEqual(make_task().comments, "")

    def test_reads_back_what_was_appended(self) -> None:
        """Comments survive being appended and read."""
        task = make_task()
        task.append_comment("first")
        task.append_comment("second")
        self.assertEqual(task.comments, "first\n\nsecond")


class TestCommentsAlongsideDescription(unittest.TestCase):
    """The two sections do not disturb each other."""

    def test_comment_leaves_the_description_readable(self) -> None:
        """Adding a comment leaves the description where it was."""
        task = make_task()
        task.set_description("hello")
        task.append_comment("a note")

        self.assertEqual(task.description, "hello")

    def test_rewriting_the_description_keeps_comments(self) -> None:
        """Replacing the description does not disturb the comments."""
        task = make_task()
        task.set_description("first")
        task.append_comment("a note")
        task.set_description("second")

        self.assertEqual(task.description, "second")
        self.assertIn("a note", task.body)

    def test_comments_accumulate(self) -> None:
        """Each comment is added to the ones already there."""
        task = make_task()
        task.append_comment("first")
        task.append_comment("second")

        self.assertEqual(task.body.count("# Comments"), 1)
        self.assertIn("first", task.body)
        self.assertIn("second", task.body)


if __name__ == "__main__":
    unittest.main()
