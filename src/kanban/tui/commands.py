"""Command palette providers for the TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from textual.command import (
    Command,
    CommandInput,
    CommandList,
    CommandPalette,
    DiscoveryHit,
    Hit,
    Hits,
    Provider,
)
from textual.content import Content
from textual.theme import ThemeProvider

if TYPE_CHECKING:
    from .app import KanbanApp

# The marker sits in front of every row so the names line up either way.
ACTIVE_MARK = "● "
INACTIVE_MARK = "  "


class KanbanCommands(Provider):
    """
    The app's own palette entries, alongside Textual's system ones.

    Each entry names an app-level action — one that belongs to the application
    rather than to the board in front of the user, and so has nowhere to live
    among the board's keys.
    """

    @property
    def _commands(self) -> list[tuple[str, str, Callable[[], None]]]:
        """Return the entries to offer: a name, what it does, and the action."""
        app = cast("KanbanApp", self.app)
        return [
            (
                "Configuration",
                "Show the configuration values, and edit one",
                app.action_configuration,
            ),
        ]

    async def discover(self) -> Hits:
        """Offer every entry when the palette is opened with nothing typed."""
        for name, description, callback in self._commands:
            yield DiscoveryHit(name, callback, text=name, help=description)

    async def search(self, query: str) -> Hits:
        """Offer the entries matching `query`."""
        matcher = self.matcher(query)

        for name, description, callback in self._commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(name),
                    callback,
                    text=name,
                    help=description,
                )


class ThemeCommands(ThemeProvider):
    """
    The theme list, with the theme already in use marked.

    Textual's own provider lists every theme by name alone, which leaves the
    user to guess which one they are looking at.  This one puts a mark against
    the active theme.
    """

    def _is_active(self, name: str) -> bool:
        """Return True when `name` is the theme the app is currently using."""
        return name == self.app.theme

    def _display(self, name: str, label: Content | None = None) -> Content:
        """
        Return the palette row for a theme.

        `label` carries the search highlighting when there is a query; without
        one the plain name is used.
        """
        mark = (
            Content.from_markup(f"[$accent]{ACTIVE_MARK}[/]")
            if self._is_active(name)
            else Content(INACTIVE_MARK)
        )
        return mark + (Content(name) if label is None else label)

    async def discover(self) -> Hits:
        """Offer every theme, with the active one marked."""
        for name, callback in self.commands:
            yield DiscoveryHit(self._display(name), callback, text=name)

    async def search(self, query: str) -> Hits:
        """Offer the themes matching `query`, with the active one marked."""
        matcher = self.matcher(query)

        for name, callback in self.commands:
            if (match := matcher.match(name)) > 0:
                yield Hit(
                    match,
                    self._display(name, matcher.highlight(name)),
                    callback,
                    text=name,
                )


class ThemePalette(CommandPalette):
    """
    The palette the themes are shown in, opening on the theme in use.

    Textual highlights the first row every time the list is rebuilt, which for
    a list of themes means starting on one the user is not using.  Only the
    unsearched list is repositioned: once a query narrows it the best match
    leads, as it does in every other palette.
    """

    def _refresh_command_list(
        self, command_list: CommandList, commands: list[Command], clear_current: bool
    ) -> None:
        """Rebuild the list, then highlight the active theme while unsearched."""
        super()._refresh_command_list(command_list, commands, clear_current)

        if self.query_one(CommandInput).value.strip():
            return

        index = self._index_of(command_list, self.app.theme)
        if index is not None:
            command_list.highlighted = index

    @staticmethod
    def _index_of(command_list: CommandList, name: str) -> int | None:
        """Return the row `name` was listed at, or None when it is not listed."""
        for index in range(command_list.option_count):
            option = command_list.get_option_at_index(index)
            if isinstance(option, Command) and option.hit.text == name:
                return index
        return None
