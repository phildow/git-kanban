"""
Helpers that read values off a parsed argparse Namespace.

Shared by the CLI and REPL command handlers, which parse the same arguments
with different parsers, and by the TUI's filter bar, which parses a subset of
them with a parser of its own.
"""

import argparse
from datetime import datetime, timezone

from ..models import Priority, Slug, TaskFilter


def parse_priority(args: argparse.Namespace) -> Priority | None:
    """Return the --priority argument as a Priority, or None if not provided."""
    priority = args.priority
    return Priority(priority) if priority else None


def build_task_filter(args: argparse.Namespace) -> TaskFilter:
    """
    Build a TaskFilter from parsed filter arguments.

    Every parser that offers the filter flags names them the same way, so the
    same reader serves all three consumers.  A date that cannot be read raises,
    which is what the TUI's filter bar catches while one is still being typed.
    """
    def _parse_date(s: str | None) -> datetime | None:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

    return TaskFilter(
        assigned_to=args.assigned_to,
        priority=parse_priority(args),
        tags=args.tags or [],
        due_before=_parse_date(args.due_before),
        due_after=_parse_date(args.due_after),
        created_by=args.created_by,
        exclude_columns=[Slug(column) for column in args.exclude_columns or []],
        include_archived=args.include_archived,
    )
