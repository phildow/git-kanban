"""Tests for remembering whether the sidebar is on screen: restore and save."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import (
    SIDEBAR_HIDDEN,
    SIDEBAR_VISIBLE,
    USERDATA_TUI_SIDEBAR,
    BoardScreen,
)
from kanban.tui.widgets import SidebarPanel

COLLAPSED = "-collapsed"


def _make_service(sidebar: str | None = None) -> KanbanService:
    """Return a service over one board, with `tui.sidebar` stored when given."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "To Do", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    if sidebar is not None:
        svc.set_userdata(USERDATA_TUI_SIDEBAR, sidebar)

    return svc


def _sidebar(app: KanbanApp) -> SidebarPanel:
    """Return the board screen's sidebar."""
    screen = app.screen
    assert isinstance(screen, BoardScreen)
    return screen.query_one(SidebarPanel)


class TestSidebarRestored(unittest.IsolatedAsyncioTestCase):
    """The board opens with the sidebar as `tui.sidebar` left it."""

    async def test_unset_sidebar_starts_hidden(self) -> None:
        """With nothing stored the sidebar is off screen."""
        app = KanbanApp(_make_service())

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertTrue(_sidebar(app).has_class(COLLAPSED))

    async def test_visible_sidebar_starts_shown(self) -> None:
        """A stored `visible` puts the sidebar on screen."""
        app = KanbanApp(_make_service(SIDEBAR_VISIBLE))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertFalse(_sidebar(app).has_class(COLLAPSED))

    async def test_hidden_sidebar_starts_hidden(self) -> None:
        """A stored `hidden` leaves the sidebar off screen."""
        app = KanbanApp(_make_service(SIDEBAR_HIDDEN))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertTrue(_sidebar(app).has_class(COLLAPSED))

    async def test_unrecognised_sidebar_starts_hidden(self) -> None:
        """A value that is neither state falls back to hidden."""
        app = KanbanApp(_make_service("sideways"))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertTrue(_sidebar(app).has_class(COLLAPSED))

    async def test_a_failed_read_still_starts_the_app(self) -> None:
        """A userdata read that raises is logged, not fatal, and hides the sidebar."""
        svc = _make_service(SIDEBAR_VISIBLE)
        svc.get_userdata = MagicMock(side_effect=OSError("no userdata"))  # type: ignore[method-assign]

        app = KanbanApp(svc)
        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertTrue(_sidebar(app).has_class(COLLAPSED))


class TestSidebarSaved(unittest.IsolatedAsyncioTestCase):
    """Toggling the sidebar writes where it stands to userdata."""

    async def test_showing_the_sidebar_is_saved(self) -> None:
        """`s` from hidden stores `visible`."""
        svc = _make_service()

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()

            self.assertEqual(svc.get_userdata(USERDATA_TUI_SIDEBAR), SIDEBAR_VISIBLE)

    async def test_hiding_the_sidebar_is_saved(self) -> None:
        """`s` from visible stores `hidden`."""
        svc = _make_service(SIDEBAR_VISIBLE)

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()

            self.assertEqual(svc.get_userdata(USERDATA_TUI_SIDEBAR), SIDEBAR_HIDDEN)

    async def test_the_saved_state_is_restored_next_time(self) -> None:
        """A sidebar shown in one session is on screen in the next."""
        svc = _make_service()

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()

        app = KanbanApp(svc)
        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertFalse(_sidebar(app).has_class(COLLAPSED))

    async def test_a_failed_write_still_toggles_the_sidebar(self) -> None:
        """A userdata write that raises is logged, and the sidebar still opens."""
        svc = _make_service()
        svc.set_userdata = MagicMock(side_effect=OSError("read-only"))  # type: ignore[method-assign]

        app = KanbanApp(svc)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()

            self.assertFalse(_sidebar(app).has_class(COLLAPSED))


if __name__ == "__main__":
    unittest.main()
