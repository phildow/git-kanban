"""Forwarding facade over a ChangeTracker implementation.

The facade depends on ChangeTrackingService rather than importing a
ChangeTracker implementation directly. ChangeTrackingService holds a concrete
ChangeTracker and forwards every call to it unchanged, and it is where the work
that belongs to change tracking rather than to git itself — composing what a
commit covers, deciding when one is worth making — will go.
"""

from __future__ import annotations

from pathlib import Path

from ..tracking.base import ChangeTracker, Commit


class ChangeTrackingService:
    """Forwards change tracking operations to an injected implementation."""

    def __init__(self, change_tracker: ChangeTracker) -> None:
        """Wrap change_tracker, the concrete implementation to forward calls to."""
        self.change_tracker = change_tracker

    # Forwarding methods

    def initialize(
        self,
        root:     Path,
        worktree: str = ".kanban-store",
        branch:   str = "kanban",
    ) -> None:
        """Prepare change tracking for the store and leave it ready to commit."""
        self.change_tracker.initialize(root, worktree, branch)

    @property
    def is_initialized(self) -> bool:
        """Return True if the store has a worktree that can be committed to."""
        return self.change_tracker.is_initialized

    def add_commit(self, message: str, path: Path | None = None) -> Commit:
        """Stage what has changed and commit it, returning the new commit."""
        return self.change_tracker.add_commit(message, path)

    def squash_commits(self, message: str, path: Path | None = None) -> Commit:
        """Collapse the commits since the last squash into a single commit."""
        return self.change_tracker.squash_commits(message, path)

    def get_history(self, path: Path | None = None, limit: int = 20) -> list[Commit]:
        """Return commits touching path, most recent first."""
        return self.change_tracker.get_history(path, limit)

    def has_uncommitted_changes(self, path: Path | None = None) -> bool:
        """Return True if the store holds changes that are not yet committed."""
        return self.change_tracker.has_uncommitted_changes(path)

    def sync(self, path: Path | None = None) -> None:
        """Bring the store level with the remote: pull and rebase, then push."""
        self.change_tracker.sync(path)
