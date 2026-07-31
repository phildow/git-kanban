"""Tests for the app's own command palette entries."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.command import Command, CommandInput, CommandList, CommandPalette, Hit

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.commands import KanbanCommands
from kanban.tui.screens.config import ConfigScreen

CONFIGURATION = "Configuration"


def _make_app() -> KanbanApp:
    """Return an app over a service holding one board, so the TUI has something to draw."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "todo", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    return KanbanApp(svc)


class TestKanbanCommandsRegistered(unittest.IsolatedAsyncioTestCase):
    """The provider is part of the app's palette."""

    async def test_provider_is_registered(self) -> None:
        """The app offers its own commands alongside Textual's system ones."""
        self.assertIn(KanbanCommands, KanbanApp.COMMANDS)


class TestConfigurationCommand(unittest.IsolatedAsyncioTestCase):
    """The palette offers Configuration, and running it opens the screen."""

    async def _hits(self, app: KanbanApp, query: str) -> list[Hit]:
        """Return the provider's hits for `query`."""
        provider = KanbanCommands(app.screen)
        return [hit async for hit in provider.search(query)]

    async def test_discovered_without_a_query(self) -> None:
        """Configuration is one of the entries offered before anything is typed."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            provider = KanbanCommands(pilot.app.screen)
            names = [hit.text async for hit in provider.discover()]

            self.assertIn(CONFIGURATION, names)

    async def test_found_by_search(self) -> None:
        """Typing part of the name matches the entry."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            hits = await self._hits(app, "config")

            self.assertEqual([hit.text for hit in hits], [CONFIGURATION])

    async def test_running_it_opens_the_config_screen(self) -> None:
        """The entry's callback pushes the configuration screen."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            hits = await self._hits(app, "config")
            hits[0].command()
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, ConfigScreen)

    async def test_palette_lists_it(self) -> None:
        """Opening the palette and searching for it shows the entry in the list."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()

            palette = pilot.app.screen
            assert isinstance(palette, CommandPalette)

            palette.query_one(CommandInput).value = "configuration"
            # The palette gathers its commands in a worker and batches what it
            # finds, so the list is not there the moment the query is.
            await pilot.pause(0.5)

            command_list = palette.query_one(CommandList)
            names = [
                option.hit.text
                for index in range(command_list.option_count)
                if isinstance(option := command_list.get_option_at_index(index), Command)
            ]
            self.assertIn(CONFIGURATION, names)


if __name__ == "__main__":
    unittest.main()
