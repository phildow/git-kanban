"""Tests that render_search delegates to render_task_list in the REPL renderers."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch
from uuid import UUID

from kanban.models import Slug, Task
from kanban.protocols.command_renderer import ObjectField
from kanban.repl.rich_renderer import RichRenderer


class TestRichRendererSearchDelegatesToTaskList(unittest.TestCase):
    """RichRenderer.render_search renders results the same way render_task_list does."""

    def setUp(self) -> None:
        self.renderer = RichRenderer(render_service=MagicMock())

    def test_render_search_calls_render_task_list_with_same_args_and_result(self) -> None:
        args = Namespace(slugs=False)
        result = [object(), object()]

        with patch.object(self.renderer, "render_task_list") as mock_render_task_list:
            self.renderer.render_search(args, result)

        mock_render_task_list.assert_called_once_with(args, result)

    def test_render_search_respects_slugs_flag_like_task_list(self) -> None:
        args = Namespace(slugs=True)
        result = [object()]

        with patch.object(self.renderer, "render_task_list_slug_only") as slug_only, \
             patch.object(self.renderer, "render_task_list_rich") as rich:
            self.renderer.render_search(args, result)

        slug_only.assert_called_once_with(args, result)
        rich.assert_not_called()


class TestRichRendererFields(unittest.TestCase):
    """RichRenderer.render_fields reports each field asked for on a line of its own."""

    def setUp(self) -> None:
        self.renderer = RichRenderer(render_service=MagicMock())
        self.task = Task(
            id=UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d"),
            title="Fix login",
            slug=Slug("fix-login"),
            board=Slug("main"),
            column=Slug("todo"),
        )

    def _rendered(self, *fields: ObjectField) -> list[str]:
        """Return the lines the named fields were printed on."""
        args = Namespace()
        with patch.object(self.renderer, "_emit") as emit:
            self.renderer.render_fields(args, self.task, fields)
        return [call[0][1] for call in emit.call_args_list]

    def test_path_field_emits_the_full_path(self) -> None:
        """The path is the object's own, board and column included."""
        self.assertEqual(self._rendered(ObjectField.PATH), ["/main/todo/fix-login"])

    def test_id_field_emits_the_uuid(self) -> None:
        """The id is emitted as a plain string, nothing else alongside it."""
        self.assertEqual(self._rendered(ObjectField.ID), ["a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d"])

    def test_both_fields_take_a_line_each(self) -> None:
        """Two fields are two lines, in the order they were given."""
        self.assertEqual(
            self._rendered(ObjectField.PATH, ObjectField.ID),
            ["/main/todo/fix-login", "a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d"],
        )

    def test_a_list_reports_every_object(self) -> None:
        """A list of objects reports each one's fields in turn."""
        args = Namespace()
        with patch.object(self.renderer, "_emit") as emit:
            self.renderer.render_fields_list(args, [self.task, self.task], (ObjectField.PATH,))
        self.assertEqual(
            [call[0][1] for call in emit.call_args_list],
            ["/main/todo/fix-login", "/main/todo/fix-login"],
        )

    def test_silenced_drops_the_output(self) -> None:
        """A silenced renderer prints nothing, whatever it is asked to render."""
        args = Namespace()
        with patch.object(self.renderer.console, "print") as console_print:
            with self.renderer.silenced():
                self.renderer.render_fields(args, self.task, (ObjectField.PATH,))
            self.renderer.render_fields(args, self.task, (ObjectField.PATH,))
        console_print.assert_called_once_with("/main/todo/fix-login")


if __name__ == "__main__":
    unittest.main()
