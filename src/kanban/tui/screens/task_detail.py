"""The task detail modal, pushed on Enter."""

from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, Static

from ...models import Task
from ..formatting import metadata_text
from ..widgets import TaskHeading

TaskNavigator = Callable[[int, int], Task | None]
"""
Moves the board's selection by (columns, cards) and returns the task now selected.

Returns None when the selection did not move — the end of the board, or a
column with no card to show.
"""


class DetailBody(VerticalScroll):
    """
    The scrollable rendering of the task's body.

    The arrows belong to the board while the detail screen is open, so its own
    scrolling bindings for them are released and the keys reach the screen.
    The shifted arrows scroll it in their place, as do paging, Home, End, and
    the mouse.
    """

    # Bindings released to the screen: a disabled binding is not matched, so the
    # key bubbles past the body.
    _RELEASED = frozenset(
        {"scroll_up", "scroll_down", "scroll_left", "scroll_right"}
    )

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable the arrow-key scrolling the detail screen navigates with."""
        _ = parameters
        return action not in self._RELEASED


class TaskDetailScreen(ModalScreen[Task | None]):
    """
    Renders a single task: metadata block followed by the markdown body.

    The body is the task's file content below the frontmatter, so the
    Description and Comments sections render as written on disk.

    The arrows and `h/j/k/l` keep moving the board's selection underneath, and
    the screen redraws on whichever task they land on: `navigate` is what moves
    it, since the board is covered and cannot see the keys itself.

    Dismisses with the task the user asked to edit, so the board screen can open
    the form on it — editing belongs to the board, which is the screen that
    talks to the kanban service.  Dismisses with None when it is only closed.
    """

    BINDINGS = [
        Binding("escape,q,enter", "dismiss_screen", "Close", show=True),
        Binding("e", "edit", "Edit", show=True),
        # The board's own navigation keys, in the board's own arrangement:
        # left/right for the columns, up/down for the cards within one.  The
        # first binding of each pair names both keys; the second is hidden.
        Binding("left,h", "navigate(-1, 0)", "Column", show=True, key_display="←/→ h/l"),
        Binding("right,l", "navigate(1, 0)", "Column", show=False, system=True),
        Binding("up,k", "navigate(0, -1)", "Card", show=True, key_display="↑/↓ j/k"),
        Binding("down,j", "navigate(0, 1)", "Card", show=False, system=True),
        # The unshifted keys move the selection, so scrolling the body the
        # selection lands on is the shifted form of the same keys.  As on the
        # board, the shifted arrows are named and the shifted letters capitals.
        Binding("shift+up,K", "scroll_body(0, -1)", "Scroll", show=True, key_display="⇧↑/↓"),
        Binding("shift+down,J", "scroll_body(0, 1)", "Scroll", show=False, system=True),
        Binding("shift+left,H", "scroll_body(-1, 0)", "Scroll", show=False, system=True),
        Binding("shift+right,L", "scroll_body(1, 0)", "Scroll", show=False, system=True),
    ]

    def __init__(self, task: Task, *, navigate: TaskNavigator | None = None) -> None:
        """
        Create a detail screen for `task`.

        `navigate` moves the selection on the board below; without one the
        screen stands on the task it was opened with.
        """
        super().__init__()
        # Named `detail_task` because Textual's MessagePump owns `task`.
        self.detail_task = task
        self._navigate = navigate

    def compose(self) -> ComposeResult:
        """Lay out the metadata block above a scrollable rendering of the body."""
        with Vertical(id="dialog"):
            yield TaskHeading(self.detail_task)
            yield Static(metadata_text(self.detail_task), classes="-task-meta")
            with DetailBody(id="task-detail-body"):
                yield Markdown(self._body(self.detail_task))

    def action_dismiss_screen(self) -> None:
        """Close the modal."""
        self.dismiss(None)

    def action_edit(self) -> None:
        """Close the modal and ask the board to open the shown task for editing."""
        self.dismiss(self.detail_task)

    def action_navigate(self, columns: int, cards: int) -> None:
        """Move the board's selection and draw whichever task it lands on."""
        if self._navigate is None:
            return

        task = self._navigate(columns, cards)
        if task is None or task == self.detail_task:
            return

        self.show_task(task)

    def action_scroll_body(self, columns: int, lines: int) -> None:
        """Scroll the body by `columns` cells and `lines` lines, leaving the selection alone."""
        self.query_one(DetailBody).scroll_relative(
            x=columns, y=lines, animate=False
        )

    def show_task(self, task: Task) -> None:
        """Draw `task` in place of the one on screen."""
        self.detail_task = task

        self.query_one(TaskHeading).set_task(task)
        self.query_one(".-task-meta", Static).update(metadata_text(task))
        self.query_one(Markdown).update(self._body(task))
        # A new task is read from its start, wherever the last one was scrolled to.
        self.query_one(DetailBody).scroll_home(animate=False)

    def _body(self, task: Task) -> str:
        """Return what to render for `task`, standing in for an empty body."""
        return task.body or "*(no description)*"
