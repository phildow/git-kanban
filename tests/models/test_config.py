"""Tests for the configuration definitions: keys, permitted values, defaults."""

from __future__ import annotations

import unittest

from kanban.models.config import (
    CONFIG_DEFAULTS,
    CONFIG_KEYS,
    CONFIG_NEW_TASK_INSERT,
    CONFIG_TUI_THEME,
    CONFIG_USER_NAME,
    CONFIG_VALUES,
    DEFAULT_THEME,
    INSERT_ABOVE,
    INSERT_BELOW,
    INSERT_BOTTOM,
    INSERT_TOP,
    InvalidConfigKey,
    InvalidConfigValue,
)


class TestConfigKeys(unittest.TestCase):
    """The supported keys, and the shape of the definitions around them."""

    def test_user_name_is_supported(self) -> None:
        """user.name is a supported key."""
        self.assertIn(CONFIG_USER_NAME, CONFIG_KEYS)

    def test_new_task_insert_is_supported(self) -> None:
        """new-task.insert is a supported key."""
        self.assertIn(CONFIG_NEW_TASK_INSERT, CONFIG_KEYS)

    def test_tui_theme_is_supported(self) -> None:
        """tui.theme is a supported key."""
        self.assertIn(CONFIG_TUI_THEME, CONFIG_KEYS)

    def test_constrained_keys_are_supported_keys(self) -> None:
        """Every key with a fixed value set is a key the application accepts."""
        self.assertTrue(set(CONFIG_VALUES) <= CONFIG_KEYS)

    def test_defaulted_keys_are_supported_keys(self) -> None:
        """Every key with a default is a key the application accepts."""
        self.assertTrue(set(CONFIG_DEFAULTS) <= CONFIG_KEYS)


class TestConfigValues(unittest.TestCase):
    """The values new-task.insert draws from, and the defaults' agreement with them."""

    def test_new_task_insert_permits_top_and_bottom(self) -> None:
        """new-task.insert is one end of the column or the other."""
        self.assertLessEqual({INSERT_TOP, INSERT_BOTTOM}, CONFIG_VALUES[CONFIG_NEW_TASK_INSERT])

    def test_new_task_insert_permits_above_and_below(self) -> None:
        """new-task.insert is also either side of the selected task."""
        self.assertLessEqual({INSERT_ABOVE, INSERT_BELOW}, CONFIG_VALUES[CONFIG_NEW_TASK_INSERT])

    def test_new_task_insert_permits_nothing_else(self) -> None:
        """The four positions are all new-task.insert takes."""
        self.assertEqual(
            CONFIG_VALUES[CONFIG_NEW_TASK_INSERT],
            {INSERT_TOP, INSERT_BOTTOM, INSERT_ABOVE, INSERT_BELOW},
        )

    def test_new_task_insert_defaults_to_bottom(self) -> None:
        """A new task goes to the bottom of its column unless told otherwise."""
        self.assertEqual(CONFIG_DEFAULTS[CONFIG_NEW_TASK_INSERT], INSERT_BOTTOM)

    def test_every_default_is_permitted(self) -> None:
        """No default falls outside the values its own key allows."""
        for keypath, value in CONFIG_DEFAULTS.items():
            permitted = CONFIG_VALUES.get(keypath)
            if permitted is not None:
                self.assertIn(value, permitted)

    def test_user_name_is_free_text(self) -> None:
        """A name is not drawn from a fixed set."""
        self.assertNotIn(CONFIG_USER_NAME, CONFIG_VALUES)

    def test_tui_theme_defaults_to_the_default_theme(self) -> None:
        """The TUI opens in the default theme unless told otherwise."""
        self.assertEqual(CONFIG_DEFAULTS[CONFIG_TUI_THEME], DEFAULT_THEME)

    def test_tui_theme_is_free_text(self) -> None:
        """Which themes exist is the TUI's to know, so the value is unconstrained."""
        self.assertNotIn(CONFIG_TUI_THEME, CONFIG_VALUES)


class TestConfigErrors(unittest.TestCase):
    """The errors name what was refused and what would have been accepted."""

    def test_invalid_key_names_the_key(self) -> None:
        """InvalidConfigKey carries the keypath it refused."""
        error = InvalidConfigKey("user.nickname")

        self.assertEqual(error.keypath, "user.nickname")
        self.assertIn("user.nickname", str(error))

    def test_invalid_key_lists_the_supported_keys(self) -> None:
        """InvalidConfigKey says which keys would have been accepted."""
        error = InvalidConfigKey("user.nickname")

        for keypath in CONFIG_KEYS:
            self.assertIn(keypath, str(error))

    def test_invalid_value_names_the_value(self) -> None:
        """InvalidConfigValue carries the key and value it refused."""
        error = InvalidConfigValue(CONFIG_NEW_TASK_INSERT, "sideways")

        self.assertEqual(error.keypath, CONFIG_NEW_TASK_INSERT)
        self.assertEqual(error.value, "sideways")

    def test_invalid_value_lists_the_permitted_values(self) -> None:
        """InvalidConfigValue says which values would have been accepted."""
        error = InvalidConfigValue(CONFIG_NEW_TASK_INSERT, "sideways")

        self.assertIn(INSERT_TOP, str(error))
        self.assertIn(INSERT_BOTTOM, str(error))


if __name__ == "__main__":
    unittest.main()
