"""Tests for `tui.task-id`: whether the board's cards carry the task's id."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.models.config import CONFIG_TUI_TASK_ID, TASK_ID_HIDE, TASK_ID_SHOW
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import CardWidget, ColumnView


def _make_service(setting: str | None) -> KanbanService:
    """Return a service holding one board of two tasks, with `tui.task-id` set."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "todo", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    for title in ("first", "second"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))

    if setting is not None:
        svc.set_config(CONFIG_TUI_TASK_ID, setting)

    return svc


def _cards(pilot: Pilot[None]) -> list[CardWidget]:
    """Return the cards the todo column has mounted."""
    screen = next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))
    view = next(v for v in screen.query(ColumnView) if v.column.slug == "todo")
    return view.cards


def _rendered(card: CardWidget) -> str:
    """Return the text the card draws."""
    return card.render().plain


class TestBoardTaskIdShown(unittest.IsolatedAsyncioTestCase):
    """Set to show, every card on the board leads with the task's id."""

    async def test_cards_carry_the_id(self) -> None:
        """Each card's text opens with the `#id` sigil of the task it draws."""
        svc = _make_service(TASK_ID_SHOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            for card in _cards(pilot):
                expected = f"#{card.card_task.id.hex[:8]}"
                self.assertTrue(_rendered(card).startswith(expected))

    async def test_a_collapsed_card_leaves_it_off(self) -> None:
        """`x` collapses the cards, and a collapsed card is the title alone."""
        svc = _make_service(TASK_ID_SHOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("x")
            await pilot.pause()

            for card in _cards(pilot):
                self.assertTrue(_rendered(card).startswith(card.card_task.title))


class TestBoardTaskIdHidden(unittest.IsolatedAsyncioTestCase):
    """Set to hide, no card shows an id."""

    async def test_cards_lead_with_the_title(self) -> None:
        """Each card's text opens with the title, as it did before the setting existed."""
        svc = _make_service(TASK_ID_HIDE)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            for card in _cards(pilot):
                self.assertTrue(_rendered(card).startswith(card.card_task.title))

    async def test_an_unset_setting_hides_the_id(self) -> None:
        """With nothing configured the ids stay off, as the default has them."""
        svc = _make_service(None)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            for card in _cards(pilot):
                self.assertTrue(_rendered(card).startswith(card.card_task.title))


class TestBoardTaskIdChanged(unittest.IsolatedAsyncioTestCase):
    """A setting changed mid-session reaches the cards without a reload."""

    async def test_showing_the_id_redraws_the_cards(self) -> None:
        """A `config set` from the command bar puts the ids on the cards it drew without."""
        svc = _make_service(TASK_ID_HIDE)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            self.assertFalse(any(card.show_id for card in _cards(pilot)))

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press(*f"config set {CONFIG_TUI_TASK_ID} {TASK_ID_SHOW}")
            await pilot.press("enter")
            await pilot.pause()

            self.assertTrue(all(card.show_id for card in _cards(pilot)))

    async def test_hiding_the_id_redraws_the_cards(self) -> None:
        """The same command takes the ids off again."""
        svc = _make_service(TASK_ID_SHOW)
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            self.assertTrue(all(card.show_id for card in _cards(pilot)))

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press(*f"config set {CONFIG_TUI_TASK_ID} {TASK_ID_HIDE}")
            await pilot.press("enter")
            await pilot.pause()

            self.assertFalse(any(card.show_id for card in _cards(pilot)))


if __name__ == "__main__":
    unittest.main()
