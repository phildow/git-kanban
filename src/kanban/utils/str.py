
import unicodedata
import re

from ..models.slug import Slug

def slug_it(s: str) -> Slug:
    """
    Convert free-form title text into a slug.
    Encapsulates the _kebab_case function and returns a Slug type.
    """
    return Slug(_kebab_case(s))

def parse_destination(destination: str, require_absolute: bool = False) -> tuple[Slug, Slug | None]:
    """
    Split a move destination into the column it names and the board, if any.

    A bare `<column>` names a column of the task's own board and carries no
    board.  A `/board/column` path names a column of another board, which is
    how a task crosses boards.  Returned as (column, board) so the board is
    the part a caller may ignore.

    The CLI implies an absolute path and so leaves `require_absolute` alone: a
    two-component destination names a board there whether or not a slash leads
    it.  The REPL passes True, where a path without a leading slash is always
    relative to the active board and so can only be a column of it.

    Raises ValueError for a destination with more components than a board and
    a column, and for a relative one naming a board when `require_absolute`.
    """
    parts = [part for part in destination.split("/") if part]

    if len(parts) == 1:
        return Slug(parts[0]), None
    if len(parts) == 2:
        if require_absolute and not destination.startswith("/"):
            raise ValueError(f"Invalid destination '{destination}': a column of another board must be named absolutely, as /{destination}")
        return Slug(parts[1]), Slug(parts[0])

    raise ValueError(f"Invalid destination '{destination}': expected <column> or /board/column")

def _kebab_case(s: str) -> str:
    """Convert free-form title text into a kebab-case filename slug."""
    # strip leading and trailing whitespace
    s = s.strip()
    # normalize unicode characters to their closest ASCII equivalent
    s = unicodedata.normalize("NFC", s).encode("ascii", "ignore").decode("ascii")
    # convert to lowercase
    s = s.lower()
    # remove any characters that are not alphanumeric, spaces, underscores, or hyphens
    s = re.sub(r"[^a-zA-Z0-9\s_\-]", "", s)
    # replace spaces, underscores, and hyphens with a single space
    s = re.sub(r"[\s_\-]+", " ", s)
    # replace spaces with a single hyphen
    s = s.replace(" ", "-")
    # remove any characters that are not alphanumeric or hyphens
    # s = re.sub(r"[^a-zA-Z0-9\-]", "", s)
    # strip leading/trailing hyphens
    s = s.lower().strip("-")
    
    if not s:
        raise ValueError("Title must contain at least one alphanumeric character")
    return s