"""The task form modal, pushed on create and edit."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ...models import Column, Priority, Task
from ..widgets import AutoCompleteInput


@dataclass
class TaskFormResult:
    """
    The values entered in the form.

    The screen validates and normalises input before dismissing, so the board
    screen can map these fields straight onto `TaskCreateParams` or
    `TaskUpdateParams` without further parsing.  `None` means "cleared"; the
    board screen turns cleared fields into `TaskUnsetParams` on edit.
    """

    title:       str
    assigned_to: str | None = None
    priority:    Priority | None = None
    due_date:    datetime | None = None
    tags:        list[str] = field(default_factory=list)


class TaskFormScreen(ModalScreen[TaskFormResult | None]):
    """
    Create or edit a task.

    Pass a `Task` to edit it, or a `Column` to create a task in that column.
    Dismisses with a `TaskFormResult`, or None when cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "save", "Save", show=True),
    ]

    def __init__(
        self,
        *,
        task: Task | None = None,
        column: Column | None = None,
        assignees: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Create the form in edit mode when `task` is given, otherwise create mode.

        `assignees` and `tags` are the values offered by those fields'
        dropdowns.  They are passed in rather than looked up so the screen keeps
        its distance from the kanban service.
        """
        super().__init__()
        if task is None and column is None:
            raise ValueError("TaskFormScreen requires either a task or a column")

        # Named `form_task` because Textual's MessagePump owns `task`.
        self.form_task = task
        self.column = column
        self.assignees = assignees or []
        self.tags = tags or []

    @property
    def is_edit(self) -> bool:
        """Return True when the form is editing an existing task."""
        return self.form_task is not None

    def compose(self) -> ComposeResult:
        """Lay out the labelled fields above the button row."""
        task = self.form_task
        heading = (
            f"Edit {task.slug}" if task is not None
            else f"New task in {self.column.name if self.column else ''}"
        )

        with Vertical(id="dialog"):
            yield Static(heading, id="form-heading")
            with VerticalScroll(id="form-fields"):
                yield Label("Title")
                yield Input(
                    value=task.title if task else "",
                    placeholder="task title",
                    id="field-title",
                )
                yield Label("Assigned to")
                yield AutoCompleteInput(
                    self.assignees,
                    value=(task.assigned_to or "") if task else "",
                    placeholder="name",
                    id="field-assigned-to",
                )
                yield Label("Priority")
                yield Select(
                    [(priority.value, priority) for priority in Priority],
                    value=task.priority if task and task.priority else Select.NULL,
                    prompt="none",
                    id="field-priority",
                )
                yield Label("Due date")
                yield Input(
                    value=_date_value(task),
                    placeholder="YYYY-MM-DD",
                    id="field-due-date",
                )
                yield Label("Tags")
                yield AutoCompleteInput(
                    self.tags,
                    value=", ".join(task.tags) if task else "",
                    placeholder="comma separated",
                    delimiter=",",
                    id="field-tags",
                )
                yield Static("", id="form-error")
            with Horizontal(id="dialog-buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Put the cursor in the title field."""
        self.query_one("#field-title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or cancel depending on which button was pressed."""
        if event.button.id == "save":
            self.action_save()
        else:
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Treat Enter in any field as a save."""
        _ = event
        self.action_save()

    def action_save(self) -> None:
        """Validate the fields and dismiss with the result, or show an error."""
        title = self.query_one("#field-title", Input).value.strip()
        if not title:
            self._show_error("A title is required")
            return

        raw_date = self.query_one("#field-due-date", Input).value.strip()
        due_date: datetime | None = None
        if raw_date:
            try:
                due_date = datetime.fromisoformat(raw_date)
            except ValueError:
                self._show_error(f"Could not read '{raw_date}' as a date (YYYY-MM-DD)")
                return

        priority_value = self.query_one("#field-priority", Select).value
        priority = priority_value if isinstance(priority_value, Priority) else None

        raw_tags = self.query_one("#field-tags", AutoCompleteInput).value
        tags = [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

        assigned_to = (
            self.query_one("#field-assigned-to", AutoCompleteInput).value.strip() or None
        )

        self.dismiss(
            TaskFormResult(
                title=title,
                assigned_to=assigned_to,
                priority=priority,
                due_date=due_date,
                tags=tags,
            )
        )

    def action_cancel(self) -> None:
        """Dismiss without saving."""
        self.dismiss(None)

    def _show_error(self, message: str) -> None:
        """Display a validation message beneath the fields."""
        self.query_one("#form-error", Static).update(message)


def _date_value(task: Task | None) -> str:
    """Return a task's due date formatted for the date input, or an empty string."""
    if task is None or task.due_date is None:
        return ""
    return task.due_date.date().isoformat()
