"""
Abstract base class for the change tracking layer.

The kanban store is a worktree of the project repository, and every write to
it is followed by a commit composed by the coordinating facade.  That work
sits behind this interface so the facade never speaks to git directly and a
test can swap the implementation out, exactly as it does for the repository
and the index.

Conventions
-----------
- A `path` argument is always relative to the worktree root — a board
  directory, a column directory, or a task file.  None means the whole store.
- A commit is asked for with a `CommitMessage` — a subject line and the
  trailers that describe the operation — not with text.  How that becomes a
  commit is the implementation's business: the git tracker writes the rendered
  message, and a tracker backed by something other than git is free to keep
  the trailers as fields.
- Methods return `Commit`.  Composing the message belongs to the layer above;
  an implementation records the message it is given.
- Implementations raise `ChangeTrackingError` or a subclass.  Errors from the
  underlying tool (a subprocess failure, a pygit2 exception) are wrapped, never
  surfaced.

Concrete implementations:

    GitChangeTracker      — git worktree, for production use
    InMemoryChangeTracker — list-backed, for unit tests
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from warnings import deprecated

from .message import CommitMessage


# ---------------------------------------------------------------------------
# Change tracking exceptions
# ---------------------------------------------------------------------------

class ChangeTrackingError(Exception):
    """Base class for all change tracking exceptions."""


class ChangeTrackingNotInitialized(ChangeTrackingError):
    """Raised when an operation runs against a store that has no worktree yet."""
    def __init__(self, path: Path):
        super().__init__(f"Change tracking not initialized at {path}")
        self.path = path


class NothingToCommit(ChangeTrackingError):
    """Raised when a commit is asked for and no change is staged or pending."""
    def __init__(self, path: Path | None = None):
        scope = f" under {path}" if path is not None else ""
        super().__init__(f"Nothing to commit{scope}")
        self.path = path


# ---------------------------------------------------------------------------
# Commit record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Commit:
    """
    A single commit in the kanban store's history.

    `sha` is the only field an implementation must supply.  The rest carry what
    a `kanban log` line shows, and are None when the implementation has nothing
    to report for them.
    """

    sha:     str
    message: str | None = None
    author:  str | None = None
    date:    datetime | None = None


# ---------------------------------------------------------------------------
# ChangeTracker
# ---------------------------------------------------------------------------

class ChangeTracker(ABC):
    """Commit, log, and sync the kanban store."""

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @abstractmethod
    def initialize(
        self,
        root:     Path,
        worktree: str = ".kanban-store",
        branch:   str = "kanban",
    ) -> None:
        """
        Prepare change tracking for the store and leave it ready to commit.

        Called by `KanbanService.initialize_kanban` after the store and local
        data are on disk — git last, so there is something to commit.  It is
        also the path a teammate takes on a fresh clone, where the branch
        already exists on the remote and only the worktree is missing, so an
        implementation is responsible for telling those two cases apart.

        Args:
            root:     The project root, the directory holding the worktree.
            worktree: The store directory, relative to root.
            branch:   The branch the worktree has checked out.
        """

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Return True if the store has a worktree that can be committed to."""

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    @abstractmethod
    def add_commit(self, message: CommitMessage, path: Path | None = None) -> Commit:
        """
        Stage what has changed and commit it, returning the new commit.

        Args:
            message: The subject line and trailers describing the operation.
                     An implementation renders them however its backend wants
                     them — `message.text` is the rendered form the git
                     tracker writes, and `message.trailers` is the same
                     information as fields.
            path:    Restrict the commit to this path within the store, or None
                     to commit everything outstanding.

        Raises:
            NothingToCommit: No change is outstanding within path.
        """

    @abstractmethod
    @deprecated("Squashing is out of scope; nothing calls squash_commits().")
    def squash_commits(self, message: str, path: Path | None = None) -> Commit:
        """
        Collapse the commits since the last squash into a single commit.

        Deprecated: squashing is out of scope for now.  The method stays on the
        interface so the shape is not lost, but nothing calls it and no work is
        planned on it.  `GitChangeTracker` will not implement it.

        Args:
            message: The message the squashed commit carries.
            path:    Restrict the squash to commits touching this path, or None
                     for the whole store.

        Raises:
            NothingToCommit: There is nothing to squash.
        """

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    @abstractmethod
    def get_history(self, path: Path | None = None, limit: int = 20) -> list[Commit]:
        """
        Return commits touching path, most recent first.

        History follows a file through renames, which is what makes it usable
        for a task whose title — and so filename — has changed.

        Args:
            path:  Restrict to commits touching this path, or None for the
                   whole store.
            limit: Maximum number of commits to return.
        """

    @abstractmethod
    def has_uncommitted_changes(self, path: Path | None = None) -> bool:
        """
        Return True if the store holds changes that are not yet committed.

        Reported by `kanban status`, and true when the store has been edited
        outside the application.

        Args:
            path: Restrict the check to this path, or None for the whole store.
        """

    # ------------------------------------------------------------------
    # Remote
    # ------------------------------------------------------------------

    def sync(self, path: Path | None = None) -> None:
        """
        Bring the store level with the remote: pull and rebase, then push.

        The order is fixed, so it is defined here rather than in each
        implementation; the two halves are what an implementation supplies.
        """
        self._pull_rebase(path=path)
        self._push(path=path)

    @abstractmethod
    def _pull_rebase(self, path: Path | None = None) -> None:
        """Fetch the remote branch and rebase local commits on top of it."""

    @abstractmethod
    def _push(self, path: Path | None = None) -> None:
        """Push local commits to the remote branch."""
