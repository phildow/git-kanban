"""Tests for where the board screen places a task it creates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.models.config import (
    CONFIG_NEW_TASK_INSERT,
    INSERT_ABOVE,
    INSERT_BELOW,
    INSERT_TOP,
)
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import ColumnView


def _make_service(insert: str) -> KanbanService:
    """Return a service holding one board of three tasks, with new-task.insert set."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "todo", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    for title in ("first", "second", "third"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))

    svc.set_config(CONFIG_NEW_TASK_INSERT, insert)
    return svc


def _stored(svc: KanbanService) -> list[str]:
    """Return the slugs the todo column holds, in the order it holds them."""
    return [task.slug for task in svc.get_tasks(Path("/alpha/todo"))]


def _shown(pilot: Pilot[None]) -> list[str]:
    """Return the slugs the todo column has cards mounted for."""
    screen = next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))
    view = next(v for v in screen.query(ColumnView) if v.column.slug == "todo")
    return [card.card_task.slug for card in view.cards]


async def _create(pilot: Pilot[None], title: str, *, select: int = 0) -> None:
    """Select the card at `select`, then create a task titled `title` through the form."""
    await pilot.pause()
    for _ in range(select):
        await pilot.press("down")
    await pilot.press("n")
    await pilot.pause()
    await pilot.press(*title)
    await pilot.press("ctrl+s")
    await pilot.pause()


class TestBoardNewTaskInsert(unittest.IsolatedAsyncioTestCase):
    """A task created on the board is placed against the card that was selected."""

    async def test_below_places_the_task_under_the_selected_card(self) -> None:
        """Set to below, the new card follows the one the selection was on."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await _create(pilot, "fourth", select=1)

            self.assertEqual(_stored(svc), ["first", "second", "fourth", "third"])
            self.assertEqual(_shown(pilot), ["first", "second", "fourth", "third"])

    async def test_above_places_the_task_over_the_selected_card(self) -> None:
        """Set to above, the new card takes the place of the one selected."""
        svc = _make_service(INSERT_ABOVE)
        async with KanbanApp(svc).run_test() as pilot:
            await _create(pilot, "fourth", select=1)

            self.assertEqual(_stored(svc), ["first", "fourth", "second", "third"])
            self.assertEqual(_shown(pilot), ["first", "fourth", "second", "third"])

    async def test_top_ignores_the_selection(self) -> None:
        """Set to top, the new card goes to the head of the column regardless."""
        svc = _make_service(INSERT_TOP)
        async with KanbanApp(svc).run_test() as pilot:
            await _create(pilot, "fourth", select=1)

            self.assertEqual(_stored(svc), ["fourth", "first", "second", "third"])


class TestBoardSelection(unittest.IsolatedAsyncioTestCase):
    """The board tells the service what it has selected, for commands to act on."""

    async def test_selection_follows_the_highlighted_card(self) -> None:
        """Moving down the column moves the selection with it."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            self.assertEqual(svc.selection.board, "alpha")
            self.assertEqual(svc.selection.column, "todo")
            self.assertEqual(svc.selection.task, "second")

    async def test_opening_the_command_bar_leaves_the_selection_standing(self) -> None:
        """The bar takes the focus, not the selection: a command still has one."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("slash")
            await pilot.pause()

            self.assertEqual(svc.selection.task, "second")

    async def test_arrows_in_the_command_bar_do_not_move_the_selection(self) -> None:
        """↑/↓ belong to the open bar: the cards behind it hold still."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # select "second"
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("down", "down", "up")
            await pilot.pause()

            self.assertEqual(svc.selection.task, "second")

    async def test_paging_in_the_command_bar_does_not_move_the_selection(self) -> None:
        """The rest of the navigation family is refused while the bar has focus."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # select "second"
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("pagedown", "alt+down", "alt+up")
            await pilot.pause()

            self.assertEqual(svc.selection.task, "second")

    async def test_arrows_in_the_filter_bar_do_not_move_the_selection(self) -> None:
        """The filter bar takes them too — it is typed into just the same."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # select "second"
            await pilot.press("colon")
            await pilot.pause()
            await pilot.press("down", "pagedown")
            await pilot.pause()

            self.assertEqual(svc.selection.task, "second")


class TestCommandBarNewTaskInsert(unittest.IsolatedAsyncioTestCase):
    """A task created from the command bar is placed against the selected card."""

    async def test_below_places_the_task_under_the_selected_card(self) -> None:
        """`create todo <title>` typed into the bar reads the board's selection."""
        svc = _make_service(INSERT_BELOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # select "second"
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press(*"create todo fourth")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_stored(svc), ["first", "second", "fourth", "third"])

    async def test_above_places_the_task_over_the_selected_card(self) -> None:
        """Set to above, the task typed into the bar takes the selected card's place."""
        svc = _make_service(INSERT_ABOVE)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # select "second"
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press(*"create todo fourth")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_stored(svc), ["first", "fourth", "second", "third"])


if __name__ == "__main__":
    unittest.main()
