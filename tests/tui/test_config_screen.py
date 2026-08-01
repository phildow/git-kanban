"""Tests for the configuration screen: listing values and editing one."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Input

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import (
    CONFIG_KEYS,
    CONFIG_NEW_TASK_INSERT,
    CONFIG_USER_NAME,
    INSERT_TOP,
    KanbanService,
)
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.formatting import UNSET_VALUE
from kanban.tui.screens.config import ConfigScreen
from kanban.tui.screens.config_value import ConfigValueScreen
from kanban.tui.widgets import PrefixList


def _make_service() -> KanbanService:
    """Return a service over one board, so the board screen has something to draw."""
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

    return svc


async def _open_config(pilot: Pilot[None]) -> ConfigScreen:
    """Open the configuration screen through the app action, and return it."""
    await pilot.pause()
    pilot.app.action_configuration()
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, ConfigScreen))


def _rows(screen: ConfigScreen) -> PrefixList:
    """Return the screen's list of configuration keys."""
    return screen.query_one("#config-list", PrefixList)


def _row_index(key: str) -> int:
    """Return the row `key` is listed at: the screen lists the keys in sorted order."""
    return sorted(CONFIG_KEYS).index(key)


def _prompts(screen: ConfigScreen) -> list[str]:
    """Return every row of the list as plain text."""
    rows = _rows(screen)
    return [str(rows.get_option_at_index(i).prompt) for i in range(rows.option_count)]


class TestConfigScreenRows(unittest.IsolatedAsyncioTestCase):
    """The rows pair every supported key with its value."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_lists_every_supported_key(self) -> None:
        """Typing is matched against the supported keypaths, in sorted order."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            self.assertEqual(_rows(screen).keys, sorted(CONFIG_KEYS))

    async def test_unset_key_says_so(self) -> None:
        """A key with no value shows that it is unset rather than an empty column."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            self.assertIn(UNSET_VALUE, _prompts(screen)[0])

    async def test_row_shows_the_stored_value(self) -> None:
        """A key that has been set shows its value alongside the keypath."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            row = _prompts(screen)[sorted(CONFIG_KEYS).index(CONFIG_USER_NAME)]

            self.assertTrue(row.startswith(CONFIG_USER_NAME))
            self.assertIn("philip", row)


class TestConfigScreenEditing(unittest.IsolatedAsyncioTestCase):
    """Enter on a row edits that key's value."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def _edit(
        self, pilot: Pilot[None], value: str, key: str = CONFIG_USER_NAME
    ) -> ConfigScreen:
        """Open the screen, start editing `key`, and type `value` into the prompt."""
        screen = await _open_config(pilot)
        _rows(screen).highlighted = _row_index(key)
        await pilot.press("enter")
        await pilot.pause()

        prompt = next(s for s in pilot.app.screen_stack if isinstance(s, ConfigValueScreen))
        prompt.query_one("#field-config-value", Input).value = value
        return screen

    async def test_enter_opens_the_value_prompt(self) -> None:
        """The prompt is headed by the key it is setting."""
        async with self.app.run_test() as pilot:
            await _open_config(pilot)
            await pilot.press("enter")
            await pilot.pause()

            prompt = pilot.app.screen
            self.assertIsInstance(prompt, ConfigValueScreen)
            self.assertEqual(prompt.key, sorted(CONFIG_KEYS)[0])  # type: ignore[union-attr]

    async def test_prompt_is_prefilled_with_the_current_value(self) -> None:
        """Editing a key that has a value starts from that value."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(CONFIG_USER_NAME)
            await pilot.press("enter")
            await pilot.pause()

            prompt = pilot.app.screen
            assert isinstance(prompt, ConfigValueScreen)
            self.assertEqual(prompt.query_one("#field-config-value", Input).value, "philip")

    async def test_saving_writes_the_value(self) -> None:
        """The value typed into the prompt is stored by the service."""
        async with self.app.run_test() as pilot:
            await self._edit(pilot, "philip")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_USER_NAME), "philip")

    async def test_saving_redraws_the_row(self) -> None:
        """The list shows the new value without being reopened."""
        async with self.app.run_test() as pilot:
            screen = await self._edit(pilot, "philip")
            await pilot.press("enter")
            await pilot.pause()

            self.assertIn("philip", _prompts(screen)[_row_index(CONFIG_USER_NAME)])

    async def test_value_outside_the_permitted_set_is_refused(self) -> None:
        """A key with fixed values keeps its own when told something else."""
        async with self.app.run_test() as pilot:
            await self._edit(pilot, "sideways", key=CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertIsNone(self.svc.get_config(CONFIG_NEW_TASK_INSERT))

    async def test_permitted_value_is_stored(self) -> None:
        """A key with fixed values takes one of them."""
        async with self.app.run_test() as pilot:
            await self._edit(pilot, INSERT_TOP, key=CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_NEW_TASK_INSERT), INSERT_TOP)

    async def test_cancelling_leaves_the_value_alone(self) -> None:
        """Escaping the prompt writes nothing."""
        async with self.app.run_test() as pilot:
            await self._edit(pilot, "philip")
            await pilot.press("escape")
            await pilot.pause()

            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))

    async def test_empty_value_is_refused(self) -> None:
        """A blank value is reported rather than stored."""
        async with self.app.run_test() as pilot:
            await self._edit(pilot, "   ")
            await pilot.press("enter")
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, ConfigValueScreen)
            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))

    async def test_escape_closes_the_screen(self) -> None:
        """Escape on the list closes the configuration screen."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            await pilot.press("escape")
            await pilot.pause()

            self.assertNotIn(screen, pilot.app.screen_stack)


if __name__ == "__main__":
    unittest.main()
