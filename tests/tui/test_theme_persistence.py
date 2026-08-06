"""Tests for remembering the TUI's theme: restoring it, and saving a change."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.command import CommandInput
from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import CONFIG_TUI_THEME, DEFAULT_THEME, KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.commands import ThemePalette

# A theme Textual ships that is not the default, so a restore is visible.
OTHER_THEME = "nord"
UNKNOWN_THEME = "no-such-theme"


def _make_service(theme: str | None = None) -> KanbanService:
    """Return a service over one board, with `theme` configured when given."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "To Do", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    if theme is not None:
        svc.set_config(CONFIG_TUI_THEME, theme)

    return svc


class TestThemeRestored(unittest.IsolatedAsyncioTestCase):
    """The app opens in the theme `tui.theme` names."""

    async def test_configured_theme_is_applied(self) -> None:
        """A configured theme is the one the app starts in."""
        app = KanbanApp(_make_service(OTHER_THEME))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertEqual(app.theme, OTHER_THEME)

    async def test_unset_theme_falls_back_to_the_default(self) -> None:
        """With nothing configured the app opens in the default theme."""
        app = KanbanApp(_make_service())

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertEqual(app.theme, DEFAULT_THEME)

    async def test_unknown_theme_falls_back_to_the_default(self) -> None:
        """A theme that is not registered is not applied."""
        app = KanbanApp(_make_service(UNKNOWN_THEME))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertEqual(app.theme, DEFAULT_THEME)

    async def test_unknown_theme_is_left_in_the_config(self) -> None:
        """Falling back does not overwrite what the user configured."""
        svc = _make_service(UNKNOWN_THEME)

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            self.assertEqual(svc.get_config(CONFIG_TUI_THEME), UNKNOWN_THEME)

    async def test_a_failed_read_still_starts_the_app(self) -> None:
        """A config read that raises is logged, not fatal."""
        svc = _make_service()
        svc.get_config = MagicMock(side_effect=OSError("no config"))  # type: ignore[method-assign]

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            self.assertEqual(pilot.app.theme, DEFAULT_THEME)


class TestThemeSaved(unittest.IsolatedAsyncioTestCase):
    """A change of theme is written back to the config."""

    async def test_changing_the_theme_saves_it(self) -> None:
        """Setting the theme stores the new name."""
        svc = _make_service()

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            pilot.app.theme = OTHER_THEME
            await pilot.pause()

            self.assertEqual(svc.get_config(CONFIG_TUI_THEME), OTHER_THEME)

    async def test_the_saved_theme_is_restored_next_time(self) -> None:
        """A theme chosen in one session is the one the next session opens in."""
        svc = _make_service()

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            pilot.app.theme = OTHER_THEME
            await pilot.pause()

        app = KanbanApp(svc)
        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertEqual(app.theme, OTHER_THEME)

    async def test_a_failed_write_still_applies_the_theme(self) -> None:
        """A config write that raises is logged, and the theme still changes."""
        svc = _make_service()
        svc.set_config = MagicMock(side_effect=OSError("read-only"))  # type: ignore[method-assign]

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            pilot.app.theme = OTHER_THEME
            await pilot.pause()

            self.assertEqual(pilot.app.theme, OTHER_THEME)


class TestThemeSavedFromThePalette(unittest.IsolatedAsyncioTestCase):
    """Choosing a theme in the palette is what a user actually does."""

    async def _choose_in_palette(self, pilot: Pilot[None], theme: str) -> None:
        """Open the theme palette, search for `theme`, and pick the first hit."""
        pilot.app.search_themes()
        # The palette gathers its commands in a worker and batches what it
        # finds, so the list is not there the moment the screen is.
        await pilot.pause(0.5)

        palette = pilot.app.screen
        assert isinstance(palette, ThemePalette)
        palette.query_one(CommandInput).value = theme
        await pilot.pause(0.5)

        await pilot.press("enter")
        await pilot.pause(0.5)

    async def test_theme_chosen_in_the_palette_is_saved(self) -> None:
        """The palette's own route to a new theme is written back too."""
        svc = _make_service()

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await self._choose_in_palette(pilot, OTHER_THEME)

            self.assertEqual(pilot.app.theme, OTHER_THEME)
            self.assertEqual(svc.get_config(CONFIG_TUI_THEME), OTHER_THEME)


if __name__ == "__main__":
    unittest.main()
