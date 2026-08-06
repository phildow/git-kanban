"""The collapsible sidebar: repository status and git log for the current scope."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from ...services.kanban import KanbanService


class StatusView(Static):
    """Renders `KanbanService.status()`: context, counts, index freshness, git state."""

    def __init__(self, svc: KanbanService) -> None:
        """Create a status view backed by `svc`."""
        super().__init__(id="status-view")
        self.svc = svc
        self.border_title = " status "

    def on_mount(self) -> None:
        """Populate the view once it is attached to the screen."""
        self.reload()

    def reload(self) -> None:
        """Re-query the service and redraw.  The filesystem is the source of truth."""
        self.update(self._status_text())

    def _status_text(self) -> Text:
        """Return the rendered status block, or a placeholder when unavailable."""
        try:
            status = self.svc.status()
        except NotImplementedError:
            return Text("status is not implemented yet", style="dim italic")
        except Exception as exc:
            return Text(str(exc) or exc.__class__.__name__, style="red")

        text = Text()
        rows = [
            ("board", str(status.user_context.path)),
            ("boards", str(status.board_count)),
            ("columns", str(status.column_count)),
            ("tasks", str(status.task_count)),
            ("index", "fresh" if status.index_fresh else "stale"),
            ("git", "dirty" if status.uncommitted_changes else "clean"),
        ]
        width = max(len(label) for label, _ in rows)
        for label, value in rows:
            text.append(f"{label.rjust(width)}  ", style="dim")
            text.append(f"{value}\n")
        return text


class LogView(Static):
    """Renders `KanbanService.log()`, scoped to the focused task or to the board."""

    def __init__(self, svc: KanbanService) -> None:
        """Create a log view backed by `svc`."""
        super().__init__(id="log-view")
        self.svc = svc
        self.scope: Path = Path("/")
        self.border_title = " log "

    def on_mount(self) -> None:
        """Populate the view once it is attached to the screen."""
        self.reload()

    def set_scope(self, scope: Path) -> None:
        """Point the log at a board, column, or task path and redraw."""
        self.scope = scope
        self.reload()

    def reload(self) -> None:
        """Re-query the service and redraw."""
        self.border_title = f" log {self.scope} "
        self.update(self._log_text())

    def _log_text(self) -> Text:
        """Return the rendered commit list, or a placeholder when unavailable."""
        try:
            commits = self.svc.log(self.scope, limit=20)
        except NotImplementedError:
            return Text("log is not implemented yet", style="dim italic")
        except Exception as exc:
            return Text(str(exc) or exc.__class__.__name__, style="red")

        if not commits:
            return Text("no commits", style="dim italic")

        text = Text()
        for commit in commits:
            text.append(f"{commit.sha[:8]}\n", style="yellow")
        return text


class SidebarPanel(VerticalScroll):
    """
    The right-hand panel, collapsible with `s`.

    Owns the status and log views and forwards reload requests to them; the
    board screen decides when a reload is needed.
    """

    def __init__(
        self, svc: KanbanService, *, collapsed: bool = False, id: str | None = None
    ) -> None:
        """Create a sidebar backed by `svc`, collapsed from the start when asked."""
        super().__init__(id=id, classes="-collapsed" if collapsed else None)
        self.svc = svc

    def compose(self) -> ComposeResult:
        """Lay out the status view above the log view."""
        yield StatusView(self.svc)
        yield LogView(self.svc)

    def reload(self) -> None:
        """Re-query both child views."""
        for view in (self.query(StatusView), self.query(LogView)):
            for widget in view:
                widget.reload()

    def set_scope(self, scope: Path) -> None:
        """Scope the log view to a board, column, or task path."""
        for widget in self.query(LogView):
            widget.set_scope(scope)

    def toggle(self) -> bool:
        """Collapse or expand the panel.  Returns True when the panel is now visible."""
        self.toggle_class("-collapsed")
        return not self.has_class("-collapsed")
