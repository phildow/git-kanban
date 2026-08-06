"""Tests for the record a command leaves of what it changed."""

from __future__ import annotations

import shlex
import unittest
from unittest.mock import MagicMock

from kanban.models import Slug
from kanban.protocols.command_renderer import CommandRenderer
from kanban.repl.parser import build_parser
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.services.render_service import RenderService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.renderer import READ_ONLY_RENDERERS, CommandEffect, TUIRenderer


def _make_service() -> KanbanService:
    """Return a service holding one board of two columns, the first with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    svc.create_task("/alpha/todo", TaskCreateParams(title="first task"))

    return svc


def _run(svc: KanbanService, renderer: TUIRenderer, line: str) -> CommandEffect:
    """Run `line` through the REPL parser and return what it changed."""
    args = build_parser().parse_args(shlex.split(line))
    args.func(args, svc, renderer)
    renderer.take_output()
    return renderer.take_effect()


class TestReadOnlyCommands(unittest.TestCase):
    """A command that only reads records no change for the board to draw."""

    def setUp(self) -> None:
        """Give each test a service and a renderer of its own."""
        self.svc = _make_service()
        self.renderer = TUIRenderer(render_service=RenderService(service=self.svc))

    def test_a_listing_changes_nothing(self) -> None:
        """Listing tasks leaves the board as it was."""
        self.assertTrue(_run(self.svc, self.renderer, "tasks").is_empty)

    def test_a_search_changes_nothing(self) -> None:
        """Searching leaves the board as it was."""
        self.assertTrue(_run(self.svc, self.renderer, "search first").is_empty)

    def test_a_lookup_changes_nothing(self) -> None:
        """Viewing a task leaves the board as it was."""
        self.assertTrue(_run(self.svc, self.renderer, "info first-task").is_empty)

    def test_setting_a_config_value_changes_nothing_drawn(self) -> None:
        """Config is read the next time a command needs it, not drawn on the board."""
        effect = _run(self.svc, self.renderer, "config set user.name alice")
        self.assertTrue(effect.is_empty)


class TestTaskCommands(unittest.TestCase):
    """A command that writes a task records it, in the column it ended up in."""

    def setUp(self) -> None:
        """Give each test a service and a renderer of its own."""
        self.svc = _make_service()
        self.renderer = TUIRenderer(render_service=RenderService(service=self.svc))

    def test_create_records_the_new_task(self) -> None:
        """The created task names the column it was created in."""
        effect = _run(self.svc, self.renderer, "create todo second")

        self.assertFalse(effect.structural)
        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].slug, Slug("second"))
        self.assertEqual(effect.tasks[0].column, Slug("todo"))

    def test_move_records_the_task_in_its_new_column(self) -> None:
        """A moved task is recorded where it landed, not where it came from."""
        effect = _run(self.svc, self.renderer, "move first-task done")

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].column, Slug("done"))

    def test_update_records_the_updated_task(self) -> None:
        """An update records the task as it now stands."""
        effect = _run(self.svc, self.renderer, "update first-task --priority high")

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].slug, Slug("first-task"))

    def test_reorder_records_the_task(self) -> None:
        """A task moved within its column is recorded like any other write."""
        effect = _run(self.svc, self.renderer, "move first-task --top")

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].column, Slug("todo"))

    def test_rename_records_the_task_under_its_new_slug(self) -> None:
        """A rename changes the slug, and the record carries the new one."""
        effect = _run(self.svc, self.renderer, 'rename first-task "Second Thoughts"')

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].slug, Slug("second-thoughts"))

    def test_delete_records_the_task_it_removed(self) -> None:
        """A deleted task names the column it was deleted from."""
        effect = _run(self.svc, self.renderer, "delete first-task --force")

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].column, Slug("todo"))

    def test_assign_records_the_task(self) -> None:
        """Assigning records the task, which changes what its card reads."""
        effect = _run(self.svc, self.renderer, "assign first-task alice")

        self.assertEqual(len(effect.tasks), 1)
        self.assertEqual(effect.tasks[0].assigned_to, "alice")

    def test_tag_records_the_task(self) -> None:
        """Tagging records the task, which changes what its card reads."""
        effect = _run(self.svc, self.renderer, "tag first-task urgent")

        self.assertEqual(len(effect.tasks), 1)
        self.assertIn("urgent", effect.tasks[0].tags)

    def test_comment_records_the_task(self) -> None:
        """Commenting records the task, whose body has changed."""
        effect = _run(self.svc, self.renderer, 'comment first-task "on it"')

        self.assertEqual(len(effect.tasks), 1)
        self.assertFalse(effect.structural)


class TestStructuralCommands(unittest.TestCase):
    """A board or column changing is a change the board cannot scope to columns."""

    def setUp(self) -> None:
        """Give each test a service and a renderer of its own."""
        self.svc = _make_service()
        self.renderer = TUIRenderer(render_service=RenderService(service=self.svc))

    def test_creating_a_column_is_structural(self) -> None:
        """A column arriving is not confined to the columns already drawn."""
        effect = _run(self.svc, self.renderer, 'create --column "In Review"')

        self.assertTrue(effect.structural)
        self.assertEqual(effect.tasks, ())

    def test_renaming_a_column_is_structural(self) -> None:
        """A column's name is drawn in its header, which a redraw of cards misses."""
        self.assertTrue(_run(self.svc, self.renderer, 'rename -c todo "Backlog"').structural)

    def test_deleting_a_column_is_structural(self) -> None:
        """A column leaving takes its panel with it."""
        self.assertTrue(_run(self.svc, self.renderer, "delete -c done --force").structural)

    def test_reordering_columns_is_structural(self) -> None:
        """Where the columns sit is the board's own layout."""
        self.assertTrue(_run(self.svc, self.renderer, "reorder column done 0").structural)

    def test_creating_a_board_is_structural(self) -> None:
        """A new board changes the list the switcher and the header read from."""
        self.assertTrue(_run(self.svc, self.renderer, 'create --board "Beta"').structural)

    def test_switching_board_is_structural(self) -> None:
        """The working board is the whole of what the screen draws."""
        _run(self.svc, self.renderer, 'create --board "Beta"')
        self.assertTrue(_run(self.svc, self.renderer, "board beta").structural)

    def test_renaming_the_board_is_structural(self) -> None:
        """The board's name is drawn in the header."""
        self.assertTrue(_run(self.svc, self.renderer, 'rename -b "Alpha Project"').structural)


class TestEffectRecord(unittest.TestCase):
    """The record is drained by the reader and covers every command there is."""

    def test_taking_the_effect_resets_it(self) -> None:
        """What one command changed is not reported again for the next."""
        svc = _make_service()
        renderer = TUIRenderer(render_service=RenderService(service=svc))

        _run(svc, renderer, "create todo second")

        self.assertTrue(renderer.take_effect().is_empty)

    def test_every_render_call_is_classified(self) -> None:
        """
        Every call the interface defines either records a change or is named read-only.

        A command added to the renderer without being classified would leave the
        board drawing what the store no longer holds, and a call named in both
        places would be recording a change it also claims not to make.
        """
        recording = {name for name in vars(TUIRenderer) if name.startswith("render_")}
        defined = set(CommandRenderer.__abstractmethods__)

        self.assertEqual(defined, READ_ONLY_RENDERERS | recording)
        self.assertEqual(set(), READ_ONLY_RENDERERS & recording)
