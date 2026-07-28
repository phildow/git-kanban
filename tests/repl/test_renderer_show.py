"""Tests that RichRenderer.render_task_show respects the --plain flag for the body."""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Board, Column, Slug, Task
from kanban.repl.rich_renderer import RichRenderer


def _capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class TestRichRendererTaskShowPlainFlag(unittest.TestCase):
    """render_task_show renders the body as Markdown by default, Text with --plain."""

    def setUp(self) -> None:
        self.board = Board(id=uuid4(), name="Alpha", slug=Slug("alpha"))
        self.column = Column(
            id=uuid4(),
            name="To Do",
            slug=Slug("todo"),
            board=Slug("alpha"),
            position=0,
        )
        render_service = MagicMock()
        render_service.board_for_slug.return_value = self.board
        render_service.column_for_slug.return_value = self.column
        self.renderer = RichRenderer(render_service=render_service)
        self.task = Task(
            id=uuid4(),
            title="Fix login bug",
            slug="fix-login-bug",
            board="alpha",
            column="todo",
            body="# Heading\n\nSome **bold** text.",
        )

    def test_default_renders_body_as_markdown(self) -> None:
        """Without --plain, markdown syntax is interpreted rather than shown literally."""
        args = Namespace(plain=False)
        out = _capture(self.renderer.render_task_show, args, self.task)
        self.assertNotIn("**bold**", out)
        self.assertNotIn("# Heading", out)
        self.assertIn("bold", out)
        self.assertIn("Heading", out)

    def test_plain_flag_renders_body_as_literal_text(self) -> None:
        """With --plain, markdown syntax is shown literally, not interpreted."""
        args = Namespace(plain=True)
        out = _capture(self.renderer.render_task_show, args, self.task)
        self.assertIn("**bold**", out)
        self.assertIn("# Heading", out)

    def test_false_plain_attribute_defaults_to_markdown(self) -> None:
        """Namespaces without a plain attribute (e.g. other callers) default to Markdown."""
        args = Namespace(plain=False)
        out = _capture(self.renderer.render_task_show, args, self.task)
        self.assertNotIn("**bold**", out)

    def test_empty_body_renders_nothing_in_either_mode(self) -> None:
        """A task with no body produces no crash and no stray markdown/text artifacts."""
        empty_task = Task(id=uuid4(), title="No body", slug="no-body", board="alpha", column="todo")
        out_markdown = _capture(self.renderer.render_task_show, Namespace(plain=False), empty_task)
        out_plain = _capture(self.renderer.render_task_show, Namespace(plain=True), empty_task)
        self.assertNotIn("None", out_markdown)
        self.assertNotIn("None", out_plain)


if __name__ == "__main__":
    unittest.main()
