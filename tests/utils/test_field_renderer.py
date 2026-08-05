"""Tests for the renderer that reports an object's fields in place of the object."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock
from uuid import UUID

from kanban.models import Slug, Task
from kanban.protocols.command_renderer import CommandRenderer, ObjectField
from kanban.utils.field_renderer import FieldRenderer, fields_from_args, for_fields
from kanban.tui.renderer import TUIRenderer


def _task() -> Task:
    """Return a task with a known path and id."""
    return Task(
        id=UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d"),
        title="Fix login",
        slug=Slug("fix-login"),
        board=Slug("main"),
        column=Slug("todo"),
    )


class TestFieldsFromArgs(unittest.TestCase):
    """The flags a command was given become the fields it reports."""

    def test_neither_flag_asks_for_no_fields(self) -> None:
        """A command run without the flags reports the object as usual."""
        self.assertEqual(fields_from_args(Namespace(show_path=False, show_id=False)), ())

    def test_a_command_without_the_flags_asks_for_no_fields(self) -> None:
        """Commands that return no object never carry the flags at all."""
        self.assertEqual(fields_from_args(Namespace()), ())

    def test_path_flag_asks_for_the_path(self) -> None:
        """--path alone asks for the path alone."""
        self.assertEqual(
            fields_from_args(Namespace(show_path=True, show_id=False)),
            (ObjectField.PATH,),
        )

    def test_id_flag_asks_for_the_id(self) -> None:
        """--id alone asks for the id alone."""
        self.assertEqual(
            fields_from_args(Namespace(show_path=False, show_id=True)),
            (ObjectField.ID,),
        )

    def test_both_flags_put_the_path_first(self) -> None:
        """Asking for both reports the path ahead of the id."""
        self.assertEqual(
            fields_from_args(Namespace(show_path=True, show_id=True)),
            (ObjectField.PATH, ObjectField.ID),
        )


class TestForFields(unittest.TestCase):
    """`for_fields` puts a FieldRenderer in front of a renderer only when asked."""

    def setUp(self) -> None:
        self.base = MagicMock(spec=CommandRenderer)

    def test_without_the_flags_the_renderer_stands_as_it_is(self) -> None:
        """A command with neither flag renders through the renderer it was given."""
        args = Namespace(show_path=False, show_id=False)
        self.assertIs(for_fields(args, self.base), self.base)

    def test_with_a_flag_the_renderer_is_wrapped(self) -> None:
        """A command with a flag renders through a FieldRenderer instead."""
        args = Namespace(show_path=True, show_id=False)
        renderer = for_fields(args, self.base)
        self.assertIsInstance(renderer, FieldRenderer)
        self.assertEqual(renderer.fields, (ObjectField.PATH,))


class TestFieldRendererDelegation(unittest.TestCase):
    """Every object a command returns is reported by field, through the base renderer."""

    def setUp(self) -> None:
        self.base = MagicMock(spec=CommandRenderer)
        self.fields = (ObjectField.PATH, ObjectField.ID)
        self.renderer = FieldRenderer(base=self.base, fields=self.fields)
        self.args = Namespace()
        self.task = _task()

    def test_an_object_is_reported_by_field(self) -> None:
        """A command returning one object reports that object's fields."""
        self.renderer.render_task_move(self.args, self.task)
        self.base.render_fields.assert_called_once_with(self.args, self.task, self.fields)

    def test_a_list_is_reported_by_field(self) -> None:
        """A command returning a list reports the fields of every object in it."""
        tasks = [self.task, self.task]
        self.renderer.render_task_list(self.args, tasks)
        self.base.render_fields_list.assert_called_once_with(self.args, tasks, self.fields)

    def test_a_reordered_task_is_reported_by_field(self) -> None:
        """A reorder reports the task it returned alongside the operation."""
        self.renderer.render_task_reorder(self.args, (self.task, "up"))
        self.base.render_fields.assert_called_once_with(self.args, self.task, self.fields)

    def test_the_wrapped_renderer_is_still_run(self) -> None:
        """The renderer behind is run for whatever it records of the command."""
        self.renderer.render_task_move(self.args, self.task)
        self.base.render_task_move.assert_called_once_with(self.args, self.task)
        self.base.silenced.assert_called_once()

    def test_a_command_returning_no_object_passes_through(self) -> None:
        """A status has no path or id, so it is rendered as it always is."""
        status = MagicMock()
        self.renderer.render_status(self.args, status)
        self.base.render_status.assert_called_once_with(self.args, status)
        self.base.render_fields.assert_not_called()


class TestFieldRendererOverTUIRenderer(unittest.TestCase):
    """
    The TUI's record of what a command changed survives the fields standing in.

    The board redraws the columns a command touched from what the renderer
    recorded, so a command run with --path from the command bar has to leave
    that record behind exactly as it would without it.
    """

    def setUp(self) -> None:
        self.tui = TUIRenderer(render_service=MagicMock())
        self.renderer = FieldRenderer(base=self.tui, fields=(ObjectField.PATH,))
        self.task = _task()

    def test_the_output_is_the_field_alone(self) -> None:
        """Only the path reaches the output panel, in the TUI's own buffer."""
        self.renderer.render_task_move(Namespace(), self.task)
        self.assertEqual(self.tui.take_output().strip(), "/main/todo/fix-login")

    def test_the_task_is_still_recorded(self) -> None:
        """The moved task is recorded, so the board still redraws its columns."""
        self.renderer.render_task_move(Namespace(), self.task)
        self.assertEqual(self.tui.take_effect().tasks, (self.task,))

    def test_a_structural_change_is_still_recorded(self) -> None:
        """A created column is still structural, whatever was printed for it."""
        column = MagicMock()
        self.renderer.render_column_create(Namespace(), column)
        self.assertTrue(self.tui.take_effect().structural)

    def test_the_renderer_is_not_left_silent(self) -> None:
        """Silence lasts for the one call; the next command prints as usual."""
        self.renderer.render_task_move(Namespace(), self.task)
        self.tui.take_output()
        self.tui.render_fields(Namespace(), self.task, (ObjectField.ID,))
        self.assertEqual(self.tui.take_output().strip(), "a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")


if __name__ == "__main__":
    unittest.main()
