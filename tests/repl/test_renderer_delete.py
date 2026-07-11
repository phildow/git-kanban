"""Tests that the REPL renderers' delete methods include the deleted object's name."""

from __future__ import annotations

import io
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Board, Column, Task
from kanban.repl.renderer import Renderer
from kanban.repl.rich_renderer import RichRenderer


def _capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class _DeleteRenderingMixin:
    """Shared assertions for both REPL renderers' delete methods."""

    renderer_cls = None

    def setUp(self) -> None:
        self.renderer = self.renderer_cls(render_helper=MagicMock())
        self.args = Namespace(quiet=False)

    def test_render_board_delete_includes_name_and_slug(self) -> None:
        board = Board(id=uuid4(), name="My Project", slug="my-project")
        out = _capture(self.renderer.render_board_delete, self.args, board)
        self.assertIn("My Project", out)
        self.assertIn("my-project", out)

    def test_render_column_delete_includes_name_and_slug(self) -> None:
        column = Column(id=uuid4(), name="To Do", slug="todo", board="my-project", position=0)
        out = _capture(self.renderer.render_column_delete, self.args, column)
        self.assertIn("To Do", out)
        self.assertIn("todo", out)

    def test_render_task_delete_includes_title_and_slug(self) -> None:
        task = Task(id=uuid4(), title="Fix login bug", slug="fix-login-bug", board="my-project", column="todo")
        out = _capture(self.renderer.render_task_delete, self.args, task)
        self.assertIn("Fix login bug", out)
        self.assertIn("fix-login-bug", out)


class TestRendererDelete(_DeleteRenderingMixin, unittest.TestCase):
    renderer_cls = Renderer


class TestRichRendererDelete(_DeleteRenderingMixin, unittest.TestCase):
    renderer_cls = RichRenderer


if __name__ == "__main__":
    unittest.main()
