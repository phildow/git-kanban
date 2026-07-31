"""The task entity, and the markdown body conventions that belong to it."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
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

    def append_comment(self, comment: str) -> None:
        """
        Add `comment` under the task's `# Comments` heading.  Mutates `body` in place.

        Comments are only ever appended, never rewritten.  Trailing whitespace
        is trimmed from the body first, and the heading is added if the body
        does not already carry one.
        """
        body = (self.body or "").rstrip()

        if COMMENTS_HEADING_RE.search(body):
            self.body = f"{body}\n\n{comment}" if body else comment
        elif body:
            self.body = f"{body}\n\n# Comments\n\n{comment}"
        else:
            self.body = f"# Comments\n\n{comment}"


# ── Markdown body sections ────────────────────────────────────────────────────

COMMENTS_HEADING_RE = re.compile(r"^# Comments\s*$", re.MULTILINE)
DESCRIPTION_HEADING_RE = re.compile(r"^# Description\s*$", re.MULTILINE)


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
