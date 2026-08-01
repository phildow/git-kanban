"""Command palette providers for the TUI."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from textual.app import SystemCommand
from textual.command import (
    Command,
    CommandInput,
    CommandList,
    CommandPalette,
    DiscoveryHit,
    Hit,
    Hits,
)
from textual.content import Content
from textual.system_commands import SystemCommandsProvider
from textual.theme import ThemeProvider

if TYPE_CHECKING:
    from .app import KanbanApp

# The marker sits in front of every row so the names line up either way.
ACTIVE_MARK = "● "
INACTIVE_MARK = "  "


class KanbanCommands(SystemCommandsProvider):
    """
    Every palette entry: Textual's system commands, the app's own, then Quit.

    The app's entries name app-level actions — ones that belong to the
    application rather than to the board in front of the user, and so have
    nowhere to live among the board's keys.

    This stands in for Textual's own provider rather than sitting beside it.
    The palette gathers each provider's hits off a queue as they arrive, so no
    provider can say where another's entries land; supplying the whole list
    from one place is what makes its order ours to decide.  Quit goes at the
    bottom, out of the way of the entries reached by running an eye down the
    list.
    """

    def _kanban_commands(self) -> list[SystemCommand]:
        """Return the app's own entries: a name, what it does, and the action."""
        app = cast("KanbanApp", self.app)
        return [
            SystemCommand(
                "Configuration",
                "Show the configuration values, and edit one",
                app.action_configuration,
            ),
        ]

    def _ordered_commands(self) -> list[SystemCommand]:
        """
        Return every entry in the order the palette lists them.

        Textual's own lead, in the name order its provider puts them in, then
        the app's, then Quit.
        """
        system = sorted(
            self.app.get_system_commands(self.screen), key=lambda command: command.title
        )
        quit_command = [command for command in system if self._is_quit(command)]
        rest = [command for command in system if not self._is_quit(command)]

        return [*rest, *self._kanban_commands(), *quit_command]

    def _is_quit(self, command: SystemCommand) -> bool:
        """
        Return True for the command that quits the app.

        Matched on the action rather than the name so that renaming the command
        upstream moves nothing: at worst it sorts by name as it always did.
        """
        return command.callback == self.app.action_quit

    async def discover(self) -> Hits:
        """Offer every entry when the palette is opened with nothing typed."""
        for command in self._ordered_commands():
            if command.discover:
                yield DiscoveryHit(
                    command.title, command.callback, text=command.title, help=command.help
                )

    async def search(self, query: str) -> Hits:
        """Offer the entries matching `query`, ranked by how well they match."""
        matcher = self.matcher(query)

        for command in self._ordered_commands():
            if (match := matcher.match(command.title)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(command.title),
                    command.callback,
                    text=command.title,
                    help=command.help,
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
