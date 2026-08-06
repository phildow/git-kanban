"""Tests for a command from the bar that needs the user, asked on screen instead."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from textual.pilot import Pilot

from kanban.models import Slug, Task
from kanban.protocols.interaction import ConfirmationRequired, EditRequired
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.interaction import DeferredInteraction
from kanban.tui.screens.confirm import ConfirmScreen
from kanban.tui.screens.task_form import TaskFormScreen
from kanban.tui.widgets import CommandBar

from .helpers import make_task


def _make_service() -> KanbanService:
    """Return a service holding one board of two columns, the first with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    svc.create_task("/alpha/todo", TaskCreateParams(title="first task"))

    return svc


async def _run(pilot: Pilot[None], line: str) -> None:
    """Open the command bar if needed, type `line`, and submit it."""
    bar = pilot.app.screen.query_one(CommandBar)
    if not bar.has_class("-visible"):
        await pilot.press("slash")
        await pilot.pause()

    bar.value = line
    await pilot.press("enter")
    await pilot.pause()
    await pilot.pause()


def _tasks(svc: KanbanService, column: str) -> list[Task]:
    """Return the tasks stored in the named column of the test board."""
    return svc.repository.get_tasks(Slug("alpha"), Slug(column))


class TestDeferredInteraction(unittest.TestCase):
    """The TUI's interaction answers a granted question and defers every other."""

    def setUp(self) -> None:
        """Give each test an interaction with nothing granted."""
        self.interaction = DeferredInteraction()

    def test_a_confirmation_is_deferred(self) -> None:
        """The question is raised rather than put to a terminal nobody is at."""
        with self.assertRaises(ConfirmationRequired) as raised:
            self.interaction.confirm("Delete it?")

        self.assertEqual(raised.exception.message, "Delete it?")

    def test_a_granted_confirmation_is_answered(self) -> None:
        """The answer the user already gave stands for the run that needs it."""
        self.interaction.granted = "Delete it?"

        self.assertTrue(self.interaction.confirm("Delete it?"))

    def test_a_different_question_is_still_deferred(self) -> None:
        """A grant answers the question it was given for, and no other."""
        self.interaction.granted = "Delete it?"

        with self.assertRaises(ConfirmationRequired):
            self.interaction.confirm("Delete the whole board?")

    def test_an_edit_is_deferred_with_its_task(self) -> None:
        """The task comes with the refusal, for the consumer to open."""
        task = make_task()

        with self.assertRaises(EditRequired) as raised:
            self.interaction.edit("body", task)

        self.assertIs(raised.exception.task, task)


class TestConfirmationFromTheBar(unittest.IsolatedAsyncioTestCase):
    """A command that asks for confirmation is confirmed in a modal, then run."""

    async def test_the_app_installs_its_own_interaction(self) -> None:
        """The service asks the app, not the terminal, for the length of the session."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()

            self.assertIs(service.interaction, pilot.app.interaction)

    async def test_delete_asks_before_it_deletes(self) -> None:
        """The modal is up and the task is still there while it is unanswered."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "delete first-task")

            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertEqual(len(_tasks(service, "todo")), 1)

    async def test_confirming_runs_the_command(self) -> None:
        """The answer goes back into a second run, which does the deleting."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "delete first-task")

            await pilot.press("y")
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(_tasks(service, "todo"), [])

    async def test_the_board_redraws_the_column_it_deleted_from(self) -> None:
        """The re-run is a command like any other, and is scoped like one."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "delete first-task")
            await pilot.press("y")
            await pilot.pause()
            await pilot.pause()

            view = next(
                v
                for v in pilot.app.screen.query("ColumnView")
                if v.column.slug == Slug("todo")
            )
            self.assertEqual(view.cards, [])

    async def test_cancelling_leaves_the_task_alone(self) -> None:
        """A refused confirmation is a command that never ran a second time."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "delete first-task")

            await pilot.press("escape")
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(len(_tasks(service, "todo")), 1)
            self.assertNotIsInstance(pilot.app.screen, ConfirmScreen)

    async def test_the_grant_does_not_outlive_the_run_it_was_given_for(self) -> None:
        """A second delete asks again rather than inheriting the first answer."""
        service = _make_service()
        service.create_task("/alpha/todo", TaskCreateParams(title="second task"))

        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "delete first-task")
            await pilot.press("y")
            await pilot.pause()
            await pilot.pause()

            await _run(pilot, "delete second-task")

            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertEqual(len(_tasks(service, "todo")), 1)

    async def test_force_skips_the_question(self) -> None:
        """`--force` answers it before it is asked, as it does in the REPL."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "delete first-task --force")

            self.assertNotIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertEqual(_tasks(service, "todo"), [])


class TestEditFromTheBar(unittest.IsolatedAsyncioTestCase):
    """A command that wants an editor gets the TUI's own task form."""

    async def test_edit_opens_the_task_form(self) -> None:
        """`edit` is no longer refused: it opens the form on the task it names."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "edit first-task")

            self.assertIsInstance(pilot.app.screen, TaskFormScreen)

    async def test_create_with_edit_creates_the_task_and_opens_the_form(self) -> None:
        """The create stands — only the editing was deferred — and the card is drawn."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "create todo second --edit")

            self.assertIsInstance(pilot.app.screen, TaskFormScreen)
            self.assertEqual(len(_tasks(service, "todo")), 2)

            await pilot.press("escape")
            await pilot.pause()

            view = next(
                v
                for v in pilot.app.screen.query("ColumnView")
                if v.column.slug == Slug("todo")
            )
            self.assertEqual(len(view.cards), 2)

    async def test_comment_with_edit_opens_the_form(self) -> None:
        """`--edit` reaches the editor through `comment` too, and is caught there too."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "comment first-task --edit")

            self.assertIsInstance(pilot.app.screen, TaskFormScreen)
