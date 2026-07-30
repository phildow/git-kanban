"""
Render helpers for the TUI.

These functions turn domain dataclasses into Rich renderables.  They are the
TUI's equivalent of the CLI's render helpers: they never call the kanban
service, never touch storage, and never mutate the objects they are given.

Cards use compact sigils so they stay readable without consuming vertical
space: `!HIGH` for priority, `@name` for the assignee, `#id` for the task, and
`#tag` for tags.
"""

from __future__ import annotations

from datetime import datetime

from rich.text import Text

from ..models import Board, Column, Priority, Task

# Colour carries semantic meaning: red for high, yellow for medium, dim for low.
PRIORITY_STYLES: dict[Priority, str] = {
    Priority.HIGH: "bold red",
    Priority.MEDIUM: "yellow",
    Priority.LOW: "dim cyan",
}

# The spec's card sigils abbreviate medium so every priority fits the same width.
PRIORITY_LABELS: dict[Priority, str] = {
    Priority.HIGH: "HIGH",
    Priority.MEDIUM: "MED",
    Priority.LOW: "LOW",
}


def short_id(task: Task) -> str:
    """Return the compact `#id` sigil for a task: the first eight hex digits of its UUID."""
    return f"#{task.id.hex[:8]}"


def priority_sigil(priority: Priority | None) -> str:
    """Return the `!PRIORITY` sigil for a priority, or an empty string when unset."""
    if priority is None:
        return ""
    return f"!{PRIORITY_LABELS[priority]}"


def priority_style(priority: Priority | None) -> str:
    """Return the Rich style used to render a priority sigil."""
    if priority is None:
        return "dim"
    return PRIORITY_STYLES[priority]


def format_date(value: datetime | None) -> str:
    """Return a short `Jun 15` style date, or an empty string when the date is unset."""
    if value is None:
        return ""
    return value.strftime("%b %d")


def format_timestamp(value: datetime | None) -> str:
    """Return an ISO-ish `2026-06-15 10:00` timestamp, or an em dash when unset."""
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


def column_title(column: Column, task_count: int) -> str:
    """Return the column's border title, e.g. `BACKLOG (4)`."""
    return f" {column.name.upper()} ({task_count}) "


def board_subtitle(board: Board | None, column_count: int, task_count: int) -> str:
    """
    Return the header subtitle describing the active board.

    The counts are passed in rather than read off the board so the header
    always agrees with what is actually on screen.
    """
    if board is None:
        return "no board"
    return f"/{board.slug} — {column_count} columns, {task_count} tasks"


def board_label(
    board: Board,
    name_width: int = 0,
    path_width: int = 0,
    count_width: int = 0,
) -> Text:
    """
    Return a board's row in the switcher: its name, then its path and task count.

    The widths pad each field so the rows read as three columns; the count is
    right-aligned within `count_width` so the numbers line up too.  Callers
    take the widths from the widest entry in the list.
    """
    text = Text()
    text.append(board.name.ljust(name_width))
    text.append("  ")
    text.append(f"/{board.slug}".ljust(path_width), style="dim")
    text.append("  ")
    text.append(f"{board.task_count:>{count_width}} tasks", style="dim")
    return text


def card_text(task: Task, *, dense: bool = False) -> Text:
    """
    Return the renderable body of a card.

    In dense mode the card collapses to a single summary line; otherwise
    metadata is spread over as many lines as the task has fields set.
    """
    if dense:
        return _dense_card_text(task)
    return _full_card_text(task)


def _dense_card_text(task: Task) -> Text:
    """Return a single-line summary of a task for dense mode."""
    text = Text(no_wrap=True, overflow="ellipsis")
    # text.append(short_id(task), style="dim")
    # text.append(" ")
    text.append(task.title)

    if task.priority is not None:
        text.append(" ")
        text.append(priority_sigil(task.priority), style=priority_style(task.priority))
    if task.assigned_to:
        text.append(f" @{task.assigned_to}", style="cyan")

    return text


def _full_card_text(task: Task) -> Text:
    """Return the multi-line body of a task card: title, sigils, due date, and tags."""
    text = Text()
    # text.append(short_id(task), style="dim")
    # text.append(" ")
    text.append(task.title, style="bold")

    sigils = Text()
    if task.priority is not None:
        sigils.append(priority_sigil(task.priority), style=priority_style(task.priority))
    if task.assigned_to:
        if sigils:
            sigils.append("  ")
        sigils.append(f"@{task.assigned_to}", style="cyan")
    if sigils:
        text.append("\n")
        text.append_text(sigils)

    if task.due_date is not None:
        text.append("\n")
        text.append(f"due {format_date(task.due_date)}", style="magenta")

    if task.tags:
        text.append("\n")
        text.append(" ".join(f"#{tag}" for tag in task.tags), style="dim green")

    return text


def detail_text(task: Task) -> Text:
    """Return the metadata block shown at the top of the task detail screen."""
    text = Text()
    text.append(f"{task.title}\n", style="bold")
    text.append(f"{task.path}\n\n", style="dim")

    rows: list[tuple[str, str, str]] = [
        ("priority", priority_sigil(task.priority) or "—", priority_style(task.priority)),
        ("assigned", f"@{task.assigned_to}" if task.assigned_to else "—", "cyan"),
        ("created by", task.created_by or "—", ""),
        ("due", format_date(task.due_date) or "—", "magenta"),
        ("tags", " ".join(f"#{tag}" for tag in task.tags) or "—", "green"),
        ("created", format_timestamp(task.created_at), "dim"),
        ("updated", format_timestamp(task.updated_at), "dim"),
    ]

    width = max(len(label) for label, _, _ in rows)
    for label, value, style in rows:
        text.append(f"{label.rjust(width)}  ", style="dim")
        text.append(f"{value}\n", style=style)

    return text
