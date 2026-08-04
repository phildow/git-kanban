"""
Parsing for the board's inline filter bar.

The bar takes the same flags as the REPL's `search` and `tasks` commands, so
`--tag bug -p high` means the same thing here as it does there.  Bare words are
matched against the task's title, slug, assignee, and tags.

Filtering happens against tasks the board has already fetched — the bar narrows
what is on screen rather than re-querying — so the parsed query carries its own
predicate.  That predicate matches values by prefix, unlike the service's, which
matches in full: the bar filters as the user types, and a half-typed tag should
narrow rather than empty the board.
"""

from __future__ import annotations

import argparse
import shlex
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from io import StringIO

from ..models import Task, TaskFilter
from ..repl.command_helpers import build_task_filter
from ..repl.parser import add_task_filter_args


@dataclass
class FilterQuery:
    """
    A parsed filter: free text to match, plus the flags to filter by.

    An empty query matches everything, which is what an empty filter bar means.
    """

    terms:  list[str] = field(default_factory=list)
    filter: TaskFilter = field(default_factory=TaskFilter)

    @property
    def is_empty(self) -> bool:
        """Return True when the query narrows nothing."""
        return not self.terms and self.filter == TaskFilter()

    def matches(self, task: Task) -> bool:
        """Return True when `task` satisfies every flag and every bare word."""
        return self._matches_flags(task) and all(
            _matches_term(task, term) for term in self.terms
        )

    def _matches_flags(self, task: Task) -> bool:
        """
        Return True when `task` satisfies the flags that are set.

        Values are matched by prefix rather than in full, because the bar
        filters as the user types: `-t b` should already be narrowing to the
        `bug` tag rather than showing an empty board until the word is finished.
        Priorities and dates are matched exactly, having no useful prefix.
        """
        criteria = self.filter

        if not _has_prefix(task.assigned_to, criteria.assigned_to):
            return False
        if not _has_prefix(task.created_by, criteria.created_by):
            return False
        if criteria.priority is not None and task.priority != criteria.priority:
            return False
        if criteria.tags and not any(
            _has_prefix(tag, prefix) for prefix in criteria.tags for tag in task.tags
        ):
            return False
        if any(_has_prefix(task.column, prefix) for prefix in criteria.exclude_columns):
            return False
        if criteria.due_before is not None and (
            task.due_date is None or task.due_date >= criteria.due_before
        ):
            return False
        if criteria.due_after is not None and (
            task.due_date is None or task.due_date <= criteria.due_after
        ):
            return False
        return True


def build_filter_parser() -> argparse.ArgumentParser:
    """
    Return the parser for the filter bar.

    The flags come from the REPL's own definition, so the two cannot drift.
    """
    parser = argparse.ArgumentParser(prog="filter", add_help=False, exit_on_error=False)
    parser.add_argument("query", metavar="TEXT", nargs="*")
    parser.add_argument(
        "-x",
        "--exclude",
        metavar="COLUMN",
        action="append",
        dest="exclude_columns",
        help="Hide tasks in this column (repeatable)",
    )
    add_task_filter_args(parser)
    # The bar narrows the cards already on the board, and `A` is what puts the
    # archive among them, so this is not a flag the bar offers — only a value
    # `build_task_filter` needs to find.
    parser.set_defaults(include_archived=False)
    return parser


def parse_filter(text: str) -> FilterQuery | None:
    """
    Parse the filter bar's contents.

    Returns None when the text does not parse — half-typed flags, an unclosed
    quote, an unknown option.  The caller keeps the last query that did parse,
    so the board stops narrowing further rather than emptying out mid-keystroke.
    """
    if not text.strip():
        return FilterQuery()

    try:
        tokens = shlex.split(text)
    except ValueError:
        return None

    buffer = StringIO()
    try:
        # argparse reports usage errors by exiting and printing; neither is any
        # use to a live filter.  `build_task_filter` raises instead — on a date
        # it cannot read, which is every prefix of one the user is still typing.
        with redirect_stdout(buffer), redirect_stderr(buffer):
            args = build_filter_parser().parse_args(tokens)
        task_filter = build_task_filter(args)
    except (SystemExit, argparse.ArgumentError, ValueError):
        return None

    return FilterQuery(terms=list(args.query), filter=task_filter)


def _has_prefix(value: str | None, prefix: str | None) -> bool:
    """
    Return True when `value` starts with `prefix`, ignoring case.

    An unset `prefix` is no criterion at all and passes; an unset `value`
    cannot satisfy one.
    """
    if prefix is None:
        return True
    if value is None:
        return False
    return value.lower().startswith(prefix.lower())


def _matches_term(task: Task, term: str) -> bool:
    """Return True when `term` appears in a task's title, slug, assignee, or tags."""
    needle = term.lower()

    haystack = [task.title.lower(), task.slug.lower()]
    if task.assigned_to:
        haystack.append(task.assigned_to.lower())
    haystack.extend(tag.lower() for tag in task.tags)

    return any(needle in value for value in haystack)
