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


# ── Markdown body sections ────────────────────────────────────────────────────

COMMENTS_HEADING_RE = re.compile(r"^# Comments\s*$", re.MULTILINE)
def append_comment(body: str, comment: str) -> str:
    """
    Return `body` with `comment` appended under a `# Comments` heading.

    Trailing whitespace is stripped from the body before appending. If the body
    does not already contain a `# Comments` heading, one is inserted before the
    comment. An empty body results in a body that starts with the heading.
    """
    body = (body or "").rstrip()
    if COMMENTS_HEADING_RE.search(body):
        return f"{body}\n\n{comment}" if body else comment
    if body:
        return f"{body}\n\n# Comments\n\n{comment}"
    return f"# Comments\n\n{comment}"


DESCRIPTION_HEADING_RE = re.compile(r"^# Description\s*$", re.MULTILINE)
def set_description(body: str, description: str) -> str:
    """
    Return `body` with the Description section content replaced by `description`.

    The description section is the portion of the markdown body between the
    `# Description` heading and either the `# Comments` heading (if any) or the
    end of the document. Any Comments section is preserved unchanged. If the
    body does not already contain a `# Description` heading, one is inserted
    ahead of the Comments section (or at the start if no Comments section
    exists). An empty description leaves only the `# Description` heading.
    """
    body = body or ""
    desc_match = DESCRIPTION_HEADING_RE.search(body)
    comments_match = COMMENTS_HEADING_RE.search(body)

    description = description.strip("\n")
    if description:
        description_block = f"# Description\n\n{description}\n"
    else:
        description_block = "# Description\n\n"

    preamble = ""
    if desc_match:
        preamble_text = body[:desc_match.start()].rstrip()
        if preamble_text:
            preamble = f"{preamble_text}\n\n"

    if comments_match:
        comments_block = body[comments_match.start():].rstrip() + "\n"
        return f"{preamble}{description_block}\n{comments_block}"
    return f"{preamble}{description_block}"


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
