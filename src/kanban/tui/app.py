"""The Textual application: the TUI's entry point."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator

from textual.app import App
from textual.binding import Binding

from ..services.kanban import CONFIG_TUI_THEME, DEFAULT_THEME, KanbanService
from ..services.render_service import RenderService
from .commands import KanbanCommands, ThemeCommands, ThemePalette
from .interaction import DeferredInteraction
from .renderer import TUIRenderer
from .screens.board import BoardScreen
from .screens.config import ConfigScreen
from .screens.help import HelpScreen


class KanbanApp(App[None]):
    """
    The kanban TUI.

    Sits at the same level of the architecture as the CLI and the REPL: it
    consumes the `KanbanService` and nothing below it.  The app itself holds no
    board data — the board screen re-fetches from the service whenever it
    needs to render.
    """

    CSS_PATH = "kanban.tcss"
    TITLE = "kanban"

    # Every palette entry comes from one provider — Textual's system commands
    # included — since that is the only way the list has an order of its own.
    COMMANDS = {KanbanCommands}

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("question_mark", "help", "Help", show=True),
    ]

    def __init__(self, svc: KanbanService) -> None:
        """
        Create the app around an already-configured kanban service.

        The service is handed the app's own way of asking the user a question,
        in place of the terminal prompt it was built with: the terminal belongs
        to the TUI for as long as it runs, and a command that reached it would
        block the loop drawing the screen.  The board is what puts the question
        up instead.
        """
        super().__init__()
        self.svc = svc
        self.command_renderer = TUIRenderer(render_service=RenderService(service=svc))
        self.interaction = DeferredInteraction()
        svc.interaction = self.interaction

    def on_mount(self) -> None:
        """Restore the configured theme, then show the board screen."""
        self.theme = self._configured_theme()
        self.push_screen(BoardScreen(self.svc))

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _configured_theme(self) -> str:
        """
        Return the theme named by `tui.theme`, or the default when it cannot be used.

        Which themes exist is the app's to know, not the service's, so an
        unknown name — a theme removed since it was chosen, or a typo written
        into the config file by hand — falls back here rather than being
        refused when it was stored.
        """
        name: str | None = None
        with self._config_errors("read the theme"):
            name = self.svc.get_config(CONFIG_TUI_THEME)

        if name is not None and name in self.available_themes:
            return name

        if name:
            logging.warning("Configured theme %r is not available; using %s", name, DEFAULT_THEME)
        return DEFAULT_THEME

    def watch_theme(self, theme: str) -> None:
        """
        Remember the theme, whichever way it was changed.

        Watching the reactive rather than the theme palette catches every route
        to a new theme — the palette, a keybinding, anything added later — and
        keeps the writing in one place.  Textual's own `_watch_theme` still runs
        alongside this one and does the applying.
        """
        with self._config_errors("save the theme"):
            self.svc.set_config(CONFIG_TUI_THEME, theme)

    @contextmanager
    def _config_errors(self, action: str) -> Iterator[None]:
        """
        Log a failed config call instead of tearing the app down.

        A theme is a preference: failing to read or write one is worth a line in
        the log, but never worth interrupting the person using the board.
        """
        try:
            yield
        except Exception as exc:
            description = str(exc) or exc.__class__.__name__
            logging.warning("TUI could not %s: %s", action, description)

    def action_help(self) -> None:
        """Open the bindings reference."""
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen())

    def action_configuration(self) -> None:
        """Show the configuration values, and edit one."""
        if not isinstance(self.screen, ConfigScreen):
            self.push_screen(ConfigScreen(self.svc))

    def search_themes(self) -> None:
        """
        Show the theme list, marking the theme in use and opening on it.

        Overrides Textual's own, which lists the themes by name alone, says
        nothing about which one is already active, and starts on the first.
        """
        self.push_screen(
            ThemePalette(providers=[ThemeCommands], placeholder="Search for themes…")
        )

    # The app deliberately does not re-sync on `events.AppFocus`.  Returning to
    # the terminal leaves the board as the user left it; changes made outside
    # the app are picked up by the manual refresh key (`r`) instead.


def run_tui(*, svc: KanbanService) -> None:
    """Run the kanban TUI against `svc` until the user quits."""
    # Temporary measure until the index is persistent, matching the REPL.
    svc.index_service.rebuild()

    try:
        KanbanApp(svc).run()
    except Exception as exc:
        description = str(exc) or exc.__class__.__name__
        logging.error("TUI exited with an error: %s", description)
        raise
