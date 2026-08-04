"""Tests for redrawing only what a command run from the command bar changed."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from textual.pilot import Pilot

from kanban.models import Priority, Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.widgets import CardWidget, ColumnPanel, ColumnView, CommandBar


def _make_service() -> KanbanService:
    """Return a service holding one board of three columns, each with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done"), ("Later", "later")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    svc.create_task("/alpha/todo", TaskCreateParams(title="first task"))
    svc.create_task("/alpha/todo", TaskCreateParams(title="second task"))
    svc.create_task("/alpha/done", TaskCreateParams(title="done task"))
    svc.create_task("/alpha/later", TaskCreateParams(title="later task"))

    return svc


def _view(pilot: Pilot[None], column: str) -> ColumnView:
    """Return the mounted view of the named column."""
    view = next(
        v
        for v in pilot.app.screen.query(ColumnView)
        if v.column.slug == Slug(column)
    )
    return view


def _cards(pilot: Pilot[None], column: str) -> list[CardWidget]:
    """Return the card widgets currently drawn in the named column."""
    return _view(pilot, column).cards


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


class TestReadOnlyCommands(unittest.IsolatedAsyncioTestCase):
    """A command that only reads leaves every card on the board where it is."""

    async def test_a_listing_redraws_nothing(self) -> None:
        """The cards are the same widgets afterwards, not rebuilt copies."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            before = _cards(pilot, "todo")

            await _run(pilot, "tasks")

            self.assertEqual(before, _cards(pilot, "todo"))

    async def test_a_search_redraws_nothing(self) -> None:
        """Searching leaves the board standing, however wide the search."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            panels = list(pilot.app.screen.query(ColumnPanel))

            await _run(pilot, "search task")

            self.assertEqual(panels, list(pilot.app.screen.query(ColumnPanel)))


class TestTaskCommands(unittest.IsolatedAsyncioTestCase):
    """A command that writes a task redraws its columns, and no others."""

    async def test_create_redraws_only_the_column_created_in(self) -> None:
        """The new card appears; the other columns keep the widgets they had."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            done = _cards(pilot, "done")
            later = _cards(pilot, "later")

            await _run(pilot, "create todo third")

            self.assertEqual(len(_cards(pilot, "todo")), 3)
            self.assertEqual(done, _cards(pilot, "done"))
            self.assertEqual(later, _cards(pilot, "later"))

    async def test_update_redraws_only_the_column_holding_the_task(self) -> None:
        """The card shows the new value, and the rest of the board is untouched."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            done = _cards(pilot, "done")

            await _run(pilot, "update first-task --priority high")

            card = next(
                card
                for card in _cards(pilot, "todo")
                if card.card_task.slug == Slug("first-task")
            )
            self.assertEqual(card.card_task.priority, Priority.HIGH)
            self.assertEqual(done, _cards(pilot, "done"))

    async def test_move_redraws_the_columns_it_left_and_joined(self) -> None:
        """Both ends of the move are redrawn; a column at neither end is not."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            later = _cards(pilot, "later")

            await _run(pilot, "move first-task done")

            self.assertEqual(len(_cards(pilot, "todo")), 1)
            self.assertEqual(len(_cards(pilot, "done")), 2)
            self.assertEqual(later, _cards(pilot, "later"))

    async def test_delete_redraws_only_the_column_deleted_from(self) -> None:
        """The card goes, and the other columns are left alone."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            done = _cards(pilot, "done")

            await _run(pilot, "delete first-task --force")

            self.assertEqual(len(_cards(pilot, "todo")), 1)
            self.assertEqual(done, _cards(pilot, "done"))

    async def test_a_task_written_to_another_board_redraws_nothing(self) -> None:
        """A command naming a board that is not on screen changes nothing drawn."""
        service = _make_service()
        service.repository.create_board("beta", slug=Slug("beta"))
        service.repository.create_column(Slug("beta"), "To Do", slug=Slug("todo"))

        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            panels = list(pilot.app.screen.query(ColumnPanel))
            todo = _cards(pilot, "todo")

            await _run(pilot, "create /beta/todo elsewhere")

            self.assertEqual(panels, list(pilot.app.screen.query(ColumnPanel)))
            self.assertEqual(todo, _cards(pilot, "todo"))
            written = service.repository.get_tasks(Slug("beta"), Slug("todo"))
            self.assertEqual(len(written), 1)


class TestStructuralCommands(unittest.IsolatedAsyncioTestCase):
    """A board or column changing rebuilds the board, since nothing else can."""

    async def test_creating_a_column_rebuilds_the_board(self) -> None:
        """The new column is drawn, which only a rebuild can do."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, 'create --column "In Review"')

            slugs = [panel.column.slug for panel in pilot.app.screen.query(ColumnPanel)]
            self.assertIn(Slug("in-review"), slugs)

    async def test_renaming_a_column_rebuilds_the_board(self) -> None:
        """A column's name is drawn in its header, which a card redraw misses."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, 'rename -c todo "Backlog"')

            names = [panel.column.name for panel in pilot.app.screen.query(ColumnPanel)]
            self.assertIn("Backlog", names)


class TestSelectionAfterRefresh(unittest.IsolatedAsyncioTestCase):
    """A redrawn column comes back with the card the user was on still highlighted."""

    async def test_the_selected_card_keeps_the_highlight(self) -> None:
        """A command against another card does not move the selection off this one."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            selected = _view(pilot, "todo").selected_task
            self.assertIsNotNone(selected)
            self.assertEqual(selected.slug, Slug("second-task"))

            await _run(pilot, "update first-task --priority high")

            self.assertEqual(
                _view(pilot, "todo").selected_task.slug, Slug("second-task")
            )

    async def test_a_renamed_card_keeps_the_highlight_under_its_new_slug(self) -> None:
        """Renaming the selected task leaves the highlight on the card it renamed."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, 'rename first-task "Third Thoughts"')

            self.assertEqual(
                _view(pilot, "todo").selected_task.slug, Slug("third-thoughts")
            )

    async def test_a_created_card_takes_the_highlight_when_nothing_is_selected(
        self,
    ) -> None:
        """With no selection standing, the card the command wrote is highlighted."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            service.clear_selection()

            await _run(pilot, "create todo third")

            self.assertEqual(_view(pilot, "todo").selected_task.slug, Slug("third"))
