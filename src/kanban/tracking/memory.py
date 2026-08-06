"""In-memory ChangeTracker implementation, for use in tests.

Keeps the commits it is given in an ordered list, so a test can assert on what
was committed and in what order without a repository on disk.  Shas are derived
from the commit's position and message, which makes them stable across runs and
safe to assert on.

The double is deliberately permissive: it does not require `initialize` before
a commit, and `add_commit` never refuses.  A test that wants the refusing
behaviour drives it through `record_change`, which is also what makes
`has_uncommitted_changes` report True.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .base import ChangeTracker, Commit, NothingToCommit


@dataclass
class _Entry:
    """A commit as recorded, alongside the path it was scoped to."""

    commit: Commit
    path:   Path | None = None


def _matches(entry_path: Path | None, query: Path | None) -> bool:
    """
    Return True if a commit scoped to entry_path is in scope for query.

    A commit with no path touched the whole store and answers every query; a
    query with no path asks about the whole store and takes every commit.
    """
    if query is None or entry_path is None:
        return True
    return entry_path == query or entry_path.is_relative_to(query)


class InMemoryChangeTracker(ChangeTracker):
    """ChangeTracker backed by a list of commits."""

    def __init__(self, author: str | None = "kanban") -> None:
        """
        Create an empty history.

        Args:
            author: The author recorded on every commit, or None for no author.
        """
        self.author = author
        self._entries: list[_Entry] = []
        self._pending: list[Path] = []
        self._initialized = False
        self._root: Path | None = None
        self._worktree = ".kanban-store"
        self._branch = "kanban"
        self.pulls = 0
        self.pushes = 0

    # ------------------------------------------------------------------
    # Test inspection
    # ------------------------------------------------------------------

    @property
    def commits(self) -> list[Commit]:
        """Return every commit recorded, oldest first."""
        return [entry.commit for entry in self._entries]

    @property
    def messages(self) -> list[str | None]:
        """Return the message of every commit recorded, oldest first."""
        return [entry.commit.message for entry in self._entries]

    @property
    def branch(self) -> str:
        """Return the branch the store was initialized on."""
        return self._branch

    @property
    def worktree(self) -> str:
        """Return the worktree directory the store was initialized in."""
        return self._worktree

    def record_change(self, path: Path) -> None:
        """
        Mark path as changed but not yet committed.

        Nothing in the service layer calls this — it is how a test arranges for
        `has_uncommitted_changes` to report True.  The next `add_commit` clears
        what it covers.
        """
        self._pending.append(path)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        root:     Path,
        worktree: str = ".kanban-store",
        branch:   str = "kanban",
    ) -> None:
        """Record the worktree settings and open the history with an init commit."""
        self._root = root
        self._worktree = worktree
        self._branch = branch
        self._initialized = True
        self._append("kanban: initialize", None)

    @property
    def is_initialized(self) -> bool:
        """Return True if `initialize` has been called."""
        return self._initialized

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def add_commit(self, message: str, path: Path | None = None) -> Commit:
        """Record a commit and clear the pending changes it covers."""
        self._pending = [p for p in self._pending if not _matches(p, path)]
        return self._append(message, path)

    def squash_commits(self, message: str, path: Path | None = None) -> Commit:
        """
        Replace every commit in scope with a single commit carrying message.

        The squashed commit takes the position of the last commit it replaced,
        so commits outside the scope keep their order around it.
        """
        squashed = [entry for entry in self._entries if _matches(entry.path, path)]
        if not squashed:
            raise NothingToCommit(path)

        last = squashed[-1]
        kept: list[_Entry] = []
        position = 0

        for entry in self._entries:
            if entry is last:
                position = len(kept)
            if not _matches(entry.path, path):
                kept.append(entry)

        entry = _Entry(self._make_commit(message, position), path)
        kept.insert(position, entry)

        self._entries = kept
        return entry.commit

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get_history(self, path: Path | None = None, limit: int = 20) -> list[Commit]:
        """Return the commits in scope, most recent first."""
        history = [entry.commit for entry in self._entries if _matches(entry.path, path)]
        history.reverse()
        return history[:limit]

    def has_uncommitted_changes(self, path: Path | None = None) -> bool:
        """Return True if a change recorded by `record_change` is still pending."""
        return any(_matches(pending, path) for pending in self._pending)

    # ------------------------------------------------------------------
    # Remote
    # ------------------------------------------------------------------

    def _pull_rebase(self, path: Path | None = None) -> None:
        """Count the pull; there is no remote to fetch from."""
        _ = path
        self.pulls += 1

    def _push(self, path: Path | None = None) -> None:
        """Count the push; there is no remote to send to."""
        _ = path
        self.pushes += 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, message: str, path: Path | None) -> Commit:
        """Append a commit for message scoped to path and return it."""
        entry = _Entry(self._make_commit(message, len(self._entries)), path)
        self._entries.append(entry)
        return entry.commit

    def _make_commit(self, message: str, index: int) -> Commit:
        """Build a commit whose sha is derived from its position and message."""
        sha = hashlib.sha1(f"{index}:{message}".encode()).hexdigest()
        return Commit(
            sha=sha,
            message=message,
            author=self.author,
            date=datetime.now(timezone.utc),
        )
