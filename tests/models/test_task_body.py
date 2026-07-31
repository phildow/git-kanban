"""Tests for reading a task's markdown body sections."""

from __future__ import annotations

import unittest
from uuid import uuid4

from kanban.models import Slug, Task
from kanban.models.task import append_comment, description_of, set_description


def make_task(body: str) -> Task:
    """Return a task carrying `body`."""
    return Task(
        id=uuid4(),
        title="Fix login bug",
        slug=Slug("fix-login-bug"),
        board=Slug("main"),
        column=Slug("todo"),
        body=body,
    )


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
        body = "# Description\n\nfirst\n\nsecond\n"
        self.assertEqual(description_of(body), "first\n\nsecond")

    def test_empty_description_section(self) -> None:
        """A heading with nothing under it is an empty description."""
        self.assertEqual(description_of("# Description\n\n"), "")

    def test_body_without_a_heading(self) -> None:
        """A body with no Description heading has no description."""
        self.assertEqual(description_of("just some text"), "")

    def test_empty_body(self) -> None:
        """An empty body has no description."""
        self.assertEqual(description_of(""), "")


class TestTaskDescription(unittest.TestCase):
    """Task.description reads the task's own body."""

    def test_reads_from_the_body(self) -> None:
        """The property reports what the body holds."""
        task = make_task("# Description\n\nhello world\n")
        self.assertEqual(task.description, "hello world")

    def test_task_with_no_body(self) -> None:
        """A task with an empty body has no description."""
        self.assertEqual(make_task("").description, "")


class TestRoundTrip(unittest.TestCase):
    """What set_description writes, description_of reads back."""

    def test_round_trips(self) -> None:
        """A description survives being written and read."""
        body = set_description("", "hello world")
        self.assertEqual(description_of(body), "hello world")

    def test_round_trips_alongside_comments(self) -> None:
        """Adding a comment leaves the description readable."""
        body = append_comment(set_description("", "hello"), "a note")
        self.assertEqual(description_of(body), "hello")

    def test_rewriting_keeps_comments(self) -> None:
        """Replacing the description does not disturb the comments."""
        body = append_comment(set_description("", "first"), "a note")
        body = set_description(body, "second")

        self.assertEqual(description_of(body), "second")
        self.assertIn("a note", body)
