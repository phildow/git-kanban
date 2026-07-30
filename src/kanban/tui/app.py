"""The Textual application: the TUI's entry point."""

from __future__ import annotations

import logging

from textual import events
from textual.app import App
from textual.binding import Binding

from ..services.kanban import KanbanService
from ..services.render_service import RenderService
from .renderer import TuiRenderer
from .screens.board import BoardScreen
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

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
        Binding("question_mark", "help", "Help", show=True),
    ]

    def __init__(self, svc: KanbanService) -> None:
        """Create the app around an already-configured kanban service."""
        super().__init__()
        self.svc = svc
        self.command_renderer = TuiRenderer(render_service=RenderService(service=svc))

    def on_mount(self) -> None:
        """Show the board screen."""
        self.push_screen(BoardScreen(self.svc))

    def action_help(self) -> None:
        """Open the bindings reference."""
        if not isinstance(self.screen, HelpScreen):
            self.push_screen(HelpScreen())

    def on_app_focus(self, event: events.AppFocus) -> None:
        """
        Re-sync from the filesystem when the terminal regains focus.

        This catches the common case of switching away to run `git pull` or to
        edit a task file, then switching back.  Terminals that do not report
        focus fall back to the manual refresh key.
        """
        _ = event
        screen = self.screen
        if isinstance(screen, BoardScreen):
            self.run_worker(screen.reload(), exclusive=False)


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
