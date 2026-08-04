"""
The configuration keys the application supports, their permitted values, and
the values a new configuration file is written with.

Config is structured application settings, not a scratchpad: only the keys
named here may be read or written, and a key whose values are drawn from a
fixed set only accepts one of them.  Arbitrary values belong in userdata.

These definitions sit below both the service and the repository because both
need them — the service to validate what it is asked to store, the repository
to seed a new config file with the defaults.
"""

from __future__ import annotations

# ── Keys ──────────────────────────────────────────────────────────────────────

"""The current user's name, used as the author of tasks and comments."""
CONFIG_USER_NAME = "user.name"

"""Where in its column a newly created task is inserted."""
CONFIG_NEW_TASK_INSERT = "new-task.insert"

"""Insert a new task at the top of its column."""
INSERT_TOP = "top"
"""Insert a new task at the bottom of its column."""
INSERT_BOTTOM = "bottom"
"""TUI only, falls back to `top` if no selection"""
INSERT_ABOVE = "above"
"""TUI only, falls back to `bottom` if no selection"""
INSERT_BELOW = "below"

"""The theme the TUI opens in, by name."""
CONFIG_TUI_THEME = "tui.theme"
"""The default theme the TUI opens in, by name."""
DEFAULT_THEME = "textual-dark"

CONFIG_KEYS: frozenset[str] = frozenset({
    CONFIG_USER_NAME,
    CONFIG_NEW_TASK_INSERT,
    CONFIG_TUI_THEME,
})

# Keys whose value is drawn from a fixed set.  A key with no entry here takes
# free text, as a name does — and as a theme name does: which themes exist is
# the TUI's to know, so it is the TUI that falls back to the default when it is
# asked for one it cannot find.
CONFIG_VALUES: dict[str, frozenset[str]] = {
    CONFIG_NEW_TASK_INSERT: frozenset({
        INSERT_TOP, INSERT_BOTTOM, INSERT_ABOVE, INSERT_BELOW
    }),
}

# What a new configuration file is written with.  A key with no default here is
# left unset until the user sets it: there is no sensible stand-in for a name.
CONFIG_DEFAULTS: dict[str, str] = {
    CONFIG_NEW_TASK_INSERT: INSERT_BOTTOM,
    CONFIG_TUI_THEME: DEFAULT_THEME,
}


# ── Errors ────────────────────────────────────────────────────────────────────

class InvalidConfigKey(ValueError):
    """Raised when a config keypath is not one of the supported CONFIG_KEYS."""
    def __init__(self, keypath: str):
        supported = ", ".join(sorted(CONFIG_KEYS))
        super().__init__(f"Invalid config key: {keypath}. Supported keys: {supported}")
        self.keypath = keypath


class InvalidConfigValue(ValueError):
    """Raised when a value is not one of those its config key permits."""
    def __init__(self, keypath: str, value: str):
        permitted = ", ".join(sorted(CONFIG_VALUES.get(keypath, frozenset())))
        super().__init__(
            f"Invalid value for {keypath}: {value}. Permitted values: {permitted}"
        )
        self.keypath = keypath
        self.value = value
