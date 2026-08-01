"""The Textual application: the TUI's entry point."""

from __future__ import annotations

import logging

from textual.app import App
from textual.binding import Binding

from ..services.kanban import KanbanService
from ..services.render_service import RenderService
from .commands import KanbanCommands, ThemeCommands, ThemePalette
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
        """Create the app around an already-configured kanban service."""
        super().__init__()
        self.svc = svc
        self.command_renderer = TUIRenderer(render_service=RenderService(service=svc))

    def on_mount(self) -> None:
        """Show the board screen."""
        self.push_screen(BoardScreen(self.svc))

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
