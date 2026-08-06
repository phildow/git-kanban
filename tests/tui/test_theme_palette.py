"""Tests for the theme palette: marking and opening on the theme in use."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.command import Command, CommandInput, CommandList
from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.commands import ACTIVE_MARK, ThemePalette


def _make_app() -> KanbanApp:
    """Return an app over a service holding one board, so the TUI has something to draw."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "todo", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    return KanbanApp(svc)


async def _open_themes(pilot: Pilot[None], theme: str) -> ThemePalette:
    """Set `theme` as the app's, open the theme palette, and return it once populated."""
    await pilot.pause()
    pilot.app.theme = theme
    pilot.app.search_themes()
    # The palette gathers its commands in a worker and batches what it finds,
    # so the list is not there the moment the screen is.
    await pilot.pause(0.5)

    palette = pilot.app.screen
    assert isinstance(palette, ThemePalette)
    return palette


def _highlighted(palette: ThemePalette) -> str | None:
    """Return the theme name of the highlighted row, or None when nothing is."""
    command_list = palette.query_one(CommandList)
    index = command_list.highlighted

    if index is None:
        return None

    option = command_list.get_option_at_index(index)
    return option.hit.text if isinstance(option, Command) else None


def _other_theme(app: KanbanApp) -> str:
    """Return a theme other than the one the app starts on."""
    return next(name for name in app.available_themes if name != app.theme)


class TestThemePaletteOpens(unittest.IsolatedAsyncioTestCase):
    """The palette opens on the theme in use rather than the first one listed."""

    async def test_active_theme_is_highlighted(self) -> None:
        """The highlighted row is the theme the app is using."""
        app = _make_app()
        theme = _other_theme(app)

        async with app.run_test() as pilot:
            palette = await _open_themes(pilot, theme)

            self.assertEqual(_highlighted(palette), theme)

    async def test_active_theme_is_not_the_first_row(self) -> None:
        """The list keeps its order — the active theme is highlighted where it sits."""
        app = _make_app()
        theme = _other_theme(app)

        async with app.run_test() as pilot:
            palette = await _open_themes(pilot, theme)
            first = palette.query_one(CommandList).get_option_at_index(0)

            self.assertIsInstance(first, Command)
            self.assertNotEqual(first.hit.text, theme)  # type: ignore[union-attr]

    async def test_active_theme_is_marked(self) -> None:
        """The row for the active theme carries the mark."""
        app = _make_app()
        theme = _other_theme(app)

        async with app.run_test() as pilot:
            palette = await _open_themes(pilot, theme)
            command_list = palette.query_one(CommandList)
            index = command_list.highlighted
            assert index is not None

            prompt = str(command_list.get_option_at_index(index).prompt)
            self.assertTrue(prompt.startswith(ACTIVE_MARK))


class TestThemePaletteSearch(unittest.IsolatedAsyncioTestCase):
    """Searching hands the list back to the usual best-match ordering."""

    async def test_query_highlights_the_best_match(self) -> None:
        """With a query typed the top match leads, not the active theme."""
        app = _make_app()
        theme = _other_theme(app)

        async with app.run_test() as pilot:
            palette = await _open_themes(pilot, theme)

            palette.query_one(CommandInput).value = "textual-light"
            await pilot.pause(0.5)

            self.assertEqual(_highlighted(palette), "textual-light")
            self.assertEqual(palette.query_one(CommandList).highlighted, 0)


if __name__ == "__main__":
    unittest.main()
