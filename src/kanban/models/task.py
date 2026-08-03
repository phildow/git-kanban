"""The task entity, and the markdown body conventions that belong to it."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from ..models.priority import Priority
from ..models.slug import Slug
from ..protocols.sluggable import Sluggable

@dataclass
class Task(Sluggable):
    """
    Canonical task entity used by repository and service layers.

    `board` and `column` describe the task's current location and are not saved 
    or restored from the repository.  They are only used for rendering and filtering 
    in the CLI. Other fields capture metadata rendered in the CLI and used for filtering/sorting.
    """

    id:             UUID
    title:          str
    slug:           Slug
    board:          Slug
    column:         Slug
    
    created_by:     str | None = None
    assigned_to:    str | None = None
    priority:       Priority | None = None
    due_date:       datetime | None = None
    tags:           list[str] = field(default_factory=list)
    created_at:     datetime | None = None
    updated_at:     datetime | None = None
    body:           str = ""

    @property
    def path(self) -> Path:
        return Path(f"/{self.board}/{self.column}/{self.slug}")

    @property
    def description(self) -> str:
        """Return the task's Description section, without its heading."""
        return description_of(self.body)

    @property
    def comments(self) -> str:
        """Return the task's Comments section, without its heading."""
        return comments_of(self.body)

    def set_description(self, description: str) -> None:
        """
        Replace the task's Description section.  Mutates `body` in place.

        The section runs from the `# Description` heading to the `# Comments`
        heading, or to the end of the body when there is none; any Comments
        section is left untouched.  A body with no Description heading gains
        one, ahead of the Comments section.  An empty `description` leaves the
        heading with nothing under it.
        """
        body = self.body or ""
        heading = DESCRIPTION_HEADING_RE.search(body)
        comments = COMMENTS_HEADING_RE.search(body)

        description = description.strip("\n")
        block = (
            f"# Description\n\n{description}\n" if description else "# Description\n\n"
        )

        preamble = ""
        if heading:
            before = body[: heading.start()].rstrip()
            if before:
                preamble = f"{before}\n\n"

        if comments:
            kept = body[comments.start() :].rstrip() + "\n"
            self.body = f"{preamble}{block}\n{kept}"
            return

        self.body = f"{preamble}{block}"

    def append_comment(
        self,
        comment: str,
        *,
        author: str | None = None,
        when: datetime | None = None,
    ) -> None:
        """
        Add `comment` under the task's `# Comments` heading.  Mutates `body` in place.

        Each comment is filed under a `## YYYY-MM-DD @author` heading of its
        own, naming the day it was made and, when it is known, who made it, so
        the section reads as a dated thread rather than as one run of text.
        `when` defaults to now; an unknown `author` leaves the heading as just
        the date.

        Comments are only ever appended, never rewritten.  Trailing whitespace
        is trimmed from the body first, and the `# Comments` heading is added if
        the body does not already carry one.
        """
        body = (self.body or "").rstrip()
        entry = f"{comment_heading(author=author, when=when)}\n\n{comment.strip()}"

        if COMMENTS_HEADING_RE.search(body):
            self.body = f"{body}\n\n{entry}" if body else entry
        elif body:
            self.body = f"{body}\n\n# Comments\n\n{entry}"
        else:
            self.body = f"# Comments\n\n{entry}"


# ── Markdown body sections ────────────────────────────────────────────────────

COMMENTS_HEADING_RE = re.compile(r"^# Comments\s*$", re.MULTILINE)
DESCRIPTION_HEADING_RE = re.compile(r"^# Description\s*$", re.MULTILINE)

# How the date reads in a comment's own heading.
COMMENT_DATE_FORMAT = "%Y-%m-%d"

def comment_heading(author: str | None = None, when: datetime | None = None) -> str:
    """
    Return the heading a single comment is filed under: `## YYYY-MM-DD @author`.

    `when` defaults to now, in UTC, as the rest of the task's timestamps are.
    An author is named with a leading `@`, written only once however the name
    was configured; without one the heading is the date alone.
    """
    stamp = (when or datetime.now(timezone.utc)).strftime(COMMENT_DATE_FORMAT)
    name = (author or "").strip().lstrip("@").strip()

    return f"## {stamp} @{name}" if name else f"## {stamp}"

def description_of(body: str) -> str:
    """
    Return the text under a body's `# Description` heading.

    The section runs to the `# Comments` heading, or to the end of the body
    when there is none.  A body with no Description heading has no description.
    """
    body = body or ""
    heading = DESCRIPTION_HEADING_RE.search(body)
    if heading is None:
        return ""

    rest = body[heading.end():]
    comments = COMMENTS_HEADING_RE.search(rest)
    if comments is not None:
        rest = rest[:comments.start()]

    return rest.strip("\n").rstrip()

def comments_of(body: str) -> str:
    """
    Return the text under a body's `# Comments` heading.

    The section runs to the end of the body — comments are the last thing in a
    task file.  A body with no Comments heading has no comments.
    """
    body = body or ""
    heading = COMMENTS_HEADING_RE.search(body)
    if heading is None:
        return ""

    return body[heading.end() :].strip("\n").rstrip()
