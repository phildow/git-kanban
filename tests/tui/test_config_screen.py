"""Tests for the configuration screen: listing values, staging edits, and saving them."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Button, Static

from kanban.models import Slug
from kanban.models.config import CONFIG_TUI_NOTIFICATIONS, CONFIG_VALUES
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
from kanban.tui.formatting import (
    FREE_TEXT_VALUES,
    STAGED_MARKER,
    UNSET_VALUE,
    config_value_column,
    config_values_hint,
)
from kanban.tui.screens.config import ConfigScreen
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


def _values(keypath: str) -> list[str]:
    """Return the values `keypath` permits, in the order the screen cycles them."""
    return sorted(CONFIG_VALUES[keypath])


def _value_column() -> int:
    """Return how far into a row its value starts, the names being padded to a width."""
    return config_value_column(max(len(_name_of(key)) for key in CONFIG_KEYS))


def _row_index(screen: ConfigScreen, key: str) -> int:
    """Return the row `key` is listed at, headings included in the count."""
    row = screen.row_for(key)
    assert row is not None, f"{key} is not listed"
    return row


def _prompts(screen: ConfigScreen) -> list[str]:
    """Return every row of the list as plain text."""
    rows = _rows(screen)
    return [str(rows.get_option_at_index(i).prompt) for i in range(rows.option_count)]


def _section_of(keypath: str) -> str:
    """Return the section a keypath belongs to."""
    return keypath.partition(".")[0]


def _name_of(keypath: str) -> str:
    """Return a keypath's name within its section."""
    return keypath.partition(".")[2]


class TestConfigScreenRows(unittest.IsolatedAsyncioTestCase):
    """The rows pair every supported key with its value."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_lists_every_supported_key(self) -> None:
        """Every supported keypath has a row of its own."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            for keypath in CONFIG_KEYS:
                self.assertIsNotNone(screen.row_for(keypath))

    async def test_typing_matches_the_name_within_the_section(self) -> None:
        """The section is carried by the heading, so typing matches the rest."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            keys = [key for key in _rows(screen).keys if key is not None]

            self.assertEqual(keys, [_name_of(k) for k in sorted(CONFIG_KEYS)])

    async def test_unset_key_says_so(self) -> None:
        """A key with no value shows that it is unset rather than an empty column."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            self.assertIn(UNSET_VALUE, _prompts(screen)[_row_index(screen, CONFIG_USER_NAME)])

    async def test_row_shows_the_stored_value(self) -> None:
        """A key that has been set shows its value alongside its name."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            row = _prompts(screen)[_row_index(screen, CONFIG_USER_NAME)]

            self.assertIn(_name_of(CONFIG_USER_NAME), row)
            self.assertIn("philip", row)


class TestConfigScreenGroups(unittest.IsolatedAsyncioTestCase):
    """The keys are grouped by section, each group under a heading."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_every_section_has_a_heading(self) -> None:
        """Each section named by a keypath heads a group."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            headings = [
                prompt.strip()
                for prompt, key in zip(_prompts(screen), _rows(screen).keys)
                if key is None
            ]

            self.assertEqual(headings, sorted({_section_of(k) for k in CONFIG_KEYS}))

    async def test_keys_follow_their_own_heading(self) -> None:
        """A key is listed below the heading for its section, not another's."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            keys = _rows(screen).keys
            prompts = _prompts(screen)

            for keypath in CONFIG_KEYS:
                row = _row_index(screen, keypath)
                heading = next(i for i in range(row, -1, -1) if keys[i] is None)
                self.assertEqual(prompts[heading].strip(), _section_of(keypath))

    async def test_headings_cannot_be_chosen(self) -> None:
        """A heading is not a setting, so it is not selectable."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            rows = _rows(screen)

            for index, key in enumerate(rows.keys):
                if key is None:
                    self.assertTrue(rows.get_option_at_index(index).disabled)

    async def test_opens_on_the_first_setting(self) -> None:
        """The list starts on a setting rather than on the heading above it."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            rows = _rows(screen)

            self.assertIsNotNone(rows.highlighted)
            self.assertIsNotNone(rows.keys[rows.highlighted])

    async def test_arrow_keys_step_over_headings(self) -> None:
        """Moving down lands on the next setting, not on the heading between them."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            rows = _rows(screen)
            await pilot.press("down")
            await pilot.pause()

            self.assertIsNotNone(rows.keys[rows.highlighted])


class TestConfigScreenCycling(unittest.IsolatedAsyncioTestCase):
    """Enter steps a key drawn from a fixed set to its next value."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def _open_on(self, pilot: Pilot[None], key: str) -> ConfigScreen:
        """Open the screen with `key` highlighted."""
        screen = await _open_config(pilot)
        _rows(screen).highlighted = _row_index(screen, key)
        await pilot.pause()
        return screen

    async def test_enter_stages_the_first_value(self) -> None:
        """An unset key starts at the first value it permits."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), _values(CONFIG_NEW_TASK_INSERT)[0])

    async def test_enter_again_steps_on(self) -> None:
        """Each press moves to the value after the one held."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), _values(CONFIG_NEW_TASK_INSERT)[1])

    async def test_cycling_wraps_round(self) -> None:
        """The value after the last is the first again."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            values = _values(CONFIG_NEW_TASK_INSERT)

            # The first press lands on the first value; a press per value takes
            # it once round the set and back to where it started.
            await pilot.press("enter")
            for _ in values:
                await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), values[0])

    async def test_cycling_starts_from_the_stored_value(self) -> None:
        """A key that has a value steps to the one after it, not to the first."""
        values = _values(CONFIG_NEW_TASK_INSERT)
        self.svc.set_config(CONFIG_NEW_TASK_INSERT, values[1])

        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), values[2])

    async def test_cycling_follows_the_values_line(self) -> None:
        """The values are stepped through in the order the line under the list gives."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_TUI_NOTIFICATIONS)
            line = str(screen.query_one("#config-hint", Static).render())

            seen: list[str | None] = []
            for _ in _values(CONFIG_TUI_NOTIFICATIONS):
                await pilot.press("enter")
                await pilot.pause()
                seen.append(screen.value_of(CONFIG_TUI_NOTIFICATIONS))

            self.assertEqual(line, config_values_hint(CONFIG_VALUES[CONFIG_TUI_NOTIFICATIONS]))
            self.assertEqual(seen, _values(CONFIG_TUI_NOTIFICATIONS))

    async def test_cycling_stages_rather_than_writes(self) -> None:
        """A cycled value is pending like any other until the screen is saved."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertIsNone(self.svc.get_config(CONFIG_NEW_TASK_INSERT))
            row = _prompts(screen)[_row_index(screen, CONFIG_NEW_TASK_INSERT)]
            self.assertTrue(row.startswith(STAGED_MARKER))

            screen.action_save()
            await pilot.pause()

            self.assertEqual(
                self.svc.get_config(CONFIG_NEW_TASK_INSERT), _values(CONFIG_NEW_TASK_INSERT)[0]
            )

    async def test_cycling_opens_no_dialog(self) -> None:
        """There is nothing to type, so nothing is pushed over the list."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertIs(pilot.app.screen, screen)
            self.assertFalse(screen.field.is_open)

    async def test_e_cycles_as_enter_does(self) -> None:
        """`e` reaches the same value, the two being one behaviour."""
        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("e")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), _values(CONFIG_NEW_TASK_INSERT)[0])

    async def test_a_value_outside_the_set_starts_over(self) -> None:
        """A stored value the key no longer permits cycles to the first, not nowhere."""
        self.svc.repository.set_config(CONFIG_NEW_TASK_INSERT, "sideways")

        async with self.app.run_test() as pilot:
            screen = await self._open_on(pilot, CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), _values(CONFIG_NEW_TASK_INSERT)[0])

    async def test_every_fixed_value_key_cycles(self) -> None:
        """No key with a fixed set opens a field instead."""
        async with self.app.run_test() as pilot:
            for keypath in CONFIG_VALUES:
                screen = await self._open_on(pilot, keypath)
                await pilot.press("enter")
                await pilot.pause()

                self.assertFalse(screen.field.is_open)
                self.assertEqual(screen.value_of(keypath), _values(keypath)[0])


class TestConfigScreenRowField(unittest.IsolatedAsyncioTestCase):
    """A key that takes free text is typed on its own row."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def _open_field(
        self, pilot: Pilot[None], key: str = CONFIG_USER_NAME
    ) -> ConfigScreen:
        """Open the screen and start editing `key` on its row."""
        screen = await _open_config(pilot)
        _rows(screen).highlighted = _row_index(screen, key)
        await pilot.press("enter")
        await pilot.pause()
        return screen

    async def test_enter_opens_the_field_on_the_row(self) -> None:
        """The field is opened over the list rather than a dialog over the screen."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)

            self.assertIs(pilot.app.screen, screen)
            self.assertTrue(screen.field.is_open)
            self.assertIs(pilot.app.focused, screen.field)

    async def test_e_opens_the_field_too(self) -> None:
        """`e` edits the highlighted setting, as it does on the board."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(screen, CONFIG_USER_NAME)
            await pilot.press("e")
            await pilot.pause()

            self.assertTrue(screen.field.is_open)

    async def test_the_field_holds_the_current_value(self) -> None:
        """Editing a key that has a value starts from that value."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)

            self.assertEqual(screen.field.value, "philip")

    async def test_the_field_starts_at_the_value(self) -> None:
        """It covers the value alone, so the name it belongs to stays legible."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            await pilot.pause()

            rows = _rows(screen).scrollable_content_region
            self.assertEqual(screen.field.region.x, rows.x + _value_column())
            self.assertEqual(screen.field.region.width, rows.width - _value_column())

    async def test_the_field_covers_the_row_it_edits(self) -> None:
        """It is laid on the highlighted row, not on the one above or below."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            await pilot.pause()

            rows = _rows(screen)
            row = _row_index(screen, CONFIG_USER_NAME)
            self.assertEqual(
                screen.field.region.y, rows.scrollable_content_region.y + row
            )
            self.assertEqual(screen.field.region.height, 1)

    async def test_typing_stages_the_value(self) -> None:
        """Enter takes what was typed and closes the field."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            await pilot.press("p", "h", "i", "l")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_USER_NAME), "phil")
            self.assertFalse(screen.field.is_open)
            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))

    async def test_the_row_shows_what_was_typed(self) -> None:
        """The list picks the value up, marked pending."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            screen.field.value = "philip"
            await pilot.press("enter")
            await pilot.pause()

            row = _prompts(screen)[_row_index(screen, CONFIG_USER_NAME)]
            self.assertIn("philip", row)
            self.assertTrue(row.startswith(STAGED_MARKER))

    async def test_closing_hands_the_focus_back(self) -> None:
        """The list has the keys again once the field is done with."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            screen.field.value = "philip"
            await pilot.press("enter")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _rows(screen))

    async def test_escape_closes_the_field_alone(self) -> None:
        """The first Escape leaves the field, not the screen."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            screen.field.value = "philip"
            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(screen.field.is_open)
            self.assertIn(screen, pilot.app.screen_stack)
            self.assertIsNone(screen.value_of(CONFIG_USER_NAME))

    async def test_escape_twice_closes_the_screen(self) -> None:
        """The second Escape closes the modal, the field being gone."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_an_empty_field_stages_nothing(self) -> None:
        """A value cleared away leaves the setting as it was: there is no unset."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            screen.field.value = "   "
            await pilot.press("enter")
            await pilot.pause()

            self.assertFalse(screen.field.is_open)
            self.assertEqual(screen.value_of(CONFIG_USER_NAME), "philip")

    async def test_saving_takes_the_open_field(self) -> None:
        """Shift+Enter in the field saves what is in it."""
        async with self.app.run_test() as pilot:
            screen = await self._open_field(pilot)
            screen.field.value = "philip"
            await pilot.press("shift+enter")
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_USER_NAME), "philip")
            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_every_free_text_key_opens_the_field(self) -> None:
        """No key without a fixed set cycles instead."""
        async with self.app.run_test() as pilot:
            for keypath in sorted(CONFIG_KEYS - set(CONFIG_VALUES)):
                screen = await self._open_field(pilot, keypath)

                self.assertTrue(screen.field.is_open)
                await pilot.press("escape")
                await pilot.pause()

    async def test_other_letters_still_jump(self) -> None:
        """Reserving `e` leaves the rest of the alphabet to the type-ahead."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            await pilot.press("t")
            await pilot.pause()

            self.assertEqual(_rows(screen).selected_key, "theme")
            self.assertFalse(screen.field.is_open)

    async def test_escape_closes_the_screen(self) -> None:
        """Escape on the list, with no field open, closes the configuration screen."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            await pilot.press("escape")
            await pilot.pause()

            self.assertNotIn(screen, pilot.app.screen_stack)


class TestConfigScreenValuesLine(unittest.IsolatedAsyncioTestCase):
    """The line under the list says what the setting in focus will take."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    def _line(self, screen: ConfigScreen) -> str:
        """Return the values line as plain text."""
        return str(screen.query_one("#config-hint", Static).render())

    async def test_opens_on_the_first_setting_values(self) -> None:
        """The line is filled in before the user moves anywhere."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            first = sorted(CONFIG_KEYS)[0]

            permitted = CONFIG_VALUES.get(first)
            expected = config_values_hint(permitted) if permitted else FREE_TEXT_VALUES
            self.assertIn(expected, self._line(screen))

    async def test_fixed_value_key_lists_its_values(self) -> None:
        """A key drawn from a fixed set names every value in it."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(screen, CONFIG_NEW_TASK_INSERT)
            await pilot.pause()

            for value in CONFIG_VALUES[CONFIG_NEW_TASK_INSERT]:
                self.assertIn(value, self._line(screen))

    async def test_free_text_key_says_so(self) -> None:
        """A key with no fixed set says it takes free text rather than nothing."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(screen, CONFIG_USER_NAME)
            await pilot.pause()

            self.assertIn(FREE_TEXT_VALUES, self._line(screen))

    async def test_the_line_follows_the_highlight(self) -> None:
        """Moving to another setting replaces what the line says."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(screen, CONFIG_USER_NAME)
            await pilot.pause()
            before = self._line(screen)

            _rows(screen).highlighted = _row_index(screen, CONFIG_TUI_NOTIFICATIONS)
            await pilot.pause()

            self.assertNotEqual(before, self._line(screen))
            self.assertIn(
                config_values_hint(CONFIG_VALUES[CONFIG_TUI_NOTIFICATIONS]),
                self._line(screen),
            )

    async def test_every_key_says_what_it_takes(self) -> None:
        """No supported setting leaves the line empty."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            for keypath in CONFIG_KEYS:
                _rows(screen).highlighted = _row_index(screen, keypath)
                await pilot.pause()

                permitted = CONFIG_VALUES.get(keypath)
                expected = config_values_hint(permitted) if permitted else FREE_TEXT_VALUES
                self.assertIn(expected, self._line(screen))

    async def test_the_line_is_the_whole_of_what_a_key_takes(self) -> None:
        """There is no prompt behind it saying anything more: the line is it."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)
            _rows(screen).highlighted = _row_index(screen, CONFIG_NEW_TASK_INSERT)
            await pilot.pause()

            self.assertEqual(
                self._line(screen), config_values_hint(CONFIG_VALUES[CONFIG_NEW_TASK_INSERT])
            )

    async def test_key_bindings_are_not_listed(self) -> None:
        """The line carries values, not the keys the screen answers to."""
        async with self.app.run_test() as pilot:
            screen = await _open_config(pilot)

            self.assertNotIn("Save", self._line(screen))
            self.assertNotIn("Cancel", self._line(screen))


class TestConfigScreenStaging(unittest.IsolatedAsyncioTestCase):
    """An edit is held on the screen until the user saves it."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def _stage(
        self, pilot: Pilot[None], value: str, key: str = CONFIG_USER_NAME
    ) -> ConfigScreen:
        """Type `value` into the row for `key`, leaving the change staged."""
        screen = next(
            (s for s in pilot.app.screen_stack if isinstance(s, ConfigScreen)),
            None,
        ) or await _open_config(pilot)

        _rows(screen).highlighted = _row_index(screen, key)

        # A key drawn from a fixed set has no field to type into: it is stepped
        # round to the value wanted instead.
        if key in CONFIG_VALUES:
            for _ in CONFIG_VALUES[key]:
                if screen.value_of(key) == value:
                    break
                await pilot.press("enter")
                await pilot.pause()
            return screen

        await pilot.press("enter")
        await pilot.pause()

        screen.field.value = value
        await pilot.press("enter")
        await pilot.pause()

        return screen

    async def test_edited_value_is_not_written(self) -> None:
        """Closing the field stages the value; the service still has none."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")

            self.assertEqual(screen.value_of(CONFIG_USER_NAME), "philip")
            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))

    async def test_staged_row_is_marked(self) -> None:
        """A pending change is visible in the gutter the other rows leave empty."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            rows = _prompts(screen)

            self.assertTrue(rows[_row_index(screen, CONFIG_USER_NAME)].startswith(STAGED_MARKER))
            self.assertFalse(
                rows[_row_index(screen, CONFIG_TUI_NOTIFICATIONS)].startswith(STAGED_MARKER)
            )

    async def test_editing_starts_from_the_staged_value(self) -> None:
        """Reopening a staged key shows what is pending, not what is stored."""
        self.svc.set_config(CONFIG_USER_NAME, "stored")

        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            _rows(screen).highlighted = _row_index(screen, CONFIG_USER_NAME)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.field.value, "philip")

    async def test_cycling_starts_from_the_staged_value(self) -> None:
        """A staged value is where the next step round begins."""
        async with self.app.run_test() as pilot:
            values = _values(CONFIG_NEW_TASK_INSERT)
            screen = await self._stage(pilot, values[0], key=CONFIG_NEW_TASK_INSERT)
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(screen.value_of(CONFIG_NEW_TASK_INSERT), values[1])

    async def test_editing_back_to_the_stored_value_is_not_a_change(self) -> None:
        """A value typed back to what is stored stops being pending."""
        self.svc.set_config(CONFIG_USER_NAME, "philip")

        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "alice")
            await self._stage(pilot, "philip")

            row = _prompts(screen)[_row_index(screen, CONFIG_USER_NAME)]
            self.assertFalse(row.startswith(STAGED_MARKER))

    async def test_shift_enter_saves(self) -> None:
        """Shift+Enter writes what is staged and closes the screen."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            await pilot.press("shift+enter")
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_USER_NAME), "philip")
            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_save_button_saves(self) -> None:
        """The Save button does what Shift+Enter does."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            screen.query_one("#save", Button).press()
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_USER_NAME), "philip")
            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_save_writes_every_staged_key(self) -> None:
        """Saving is not limited to the setting edited last."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            await self._stage(pilot, INSERT_TOP, key=CONFIG_NEW_TASK_INSERT)
            screen.action_save()
            await pilot.pause()

            self.assertEqual(self.svc.get_config(CONFIG_USER_NAME), "philip")
            self.assertEqual(self.svc.get_config(CONFIG_NEW_TASK_INSERT), INSERT_TOP)

    async def test_escape_discards_staged_changes(self) -> None:
        """Escape closes the screen without writing what was staged."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            await pilot.press("escape")
            await pilot.pause()

            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))
            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_cancel_button_discards_staged_changes(self) -> None:
        """The Cancel button does what Escape does."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            screen.query_one("#cancel", Button).press()
            await pilot.pause()

            self.assertIsNone(self.svc.get_config(CONFIG_USER_NAME))
            self.assertNotIn(screen, pilot.app.screen_stack)

    async def test_reopening_shows_the_stored_values_again(self) -> None:
        """Nothing staged survives the screen it was staged on."""
        async with self.app.run_test() as pilot:
            await self._stage(pilot, "philip")
            await pilot.press("escape")
            await pilot.pause()

            screen = await _open_config(pilot)
            self.assertIsNone(screen.value_of(CONFIG_USER_NAME))

    async def test_a_failed_write_leaves_the_screen_up(self) -> None:
        """A write the service refuses keeps the change staged to be corrected."""
        async with self.app.run_test() as pilot:
            screen = await self._stage(pilot, "philip")
            self.svc.set_config = MagicMock(side_effect=RuntimeError("no"))  # type: ignore[method-assign]
            screen.action_save()
            await pilot.pause()

            self.assertIn(screen, pilot.app.screen_stack)
            self.assertEqual(screen.value_of(CONFIG_USER_NAME), "philip")


if __name__ == "__main__":
    unittest.main()
