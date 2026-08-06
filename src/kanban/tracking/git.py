"""Git-backed change tracker.

Drives the git worktree that holds the kanban store.  Every operation runs
against the worktree directory rather than the project root, so commits land on
the store's own branch and never touch the user's working tree.

Scaffolding: the interface is settled, the implementation is not written yet.
"""

from __future__ import annotations

from pathlib import Path

from .base import ChangeTracker, Commit


class GitChangeTracker(ChangeTracker):
    """Coordinates git commit, squash, log, and sync operations."""

    def __init__(self) -> None:
        """Create a git service scaffold with no backing implementation yet."""
        self._root: Path | None = None
        self._worktree: str = ".kanban-store"
        self._branch: str = "kanban"

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(
        self,
        root:     Path,
        worktree: str = ".kanban-store",
        branch:   str = "kanban",
    ) -> None:
        """Create the orphan branch and add the worktree that holds the store."""
        _ = root, worktree, branch
        raise NotImplementedError("GitChangeTracker.initialize() is not implemented yet")

    @property
    def is_initialized(self) -> bool:
        """Return True if the worktree exists and has the store branch checked out."""
        raise NotImplementedError("GitChangeTracker.is_initialized is not implemented yet")

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def add_commit(self, message: str, path: Path | None = None) -> Commit:
        """Create a commit and return the resulting commit metadata."""
        _ = message, path
        raise NotImplementedError("GitChangeTracker.add_commit() is not implemented yet")

    def squash_commits(self, message: str, path: Path | None = None) -> Commit:
        """Squash commits in scope and return the newly created squash commit."""
        _ = message, path
        raise NotImplementedError("GitChangeTracker.squash_commits() is not implemented yet")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def get_history(self, path: Path | None = None, limit: int = 20) -> list[Commit]:
        """Return commit history entries for an optional path."""
        _ = path, limit
        raise NotImplementedError("GitChangeTracker.get_history() is not implemented yet")

    def has_uncommitted_changes(self, path: Path | None = None) -> bool:
        """Report whether the worktree holds changes that have not been committed."""
        _ = path
        raise NotImplementedError("GitChangeTracker.has_uncommitted_changes() is not implemented yet")

    # ------------------------------------------------------------------
    # Remote
    # ------------------------------------------------------------------

    def _pull_rebase(self, path: Path | None = None) -> None:
        """Scaffold for pulling and rebasing from remote."""
        _ = path
        raise NotImplementedError("GitChangeTracker._pull_rebase() is not implemented yet")

    def _push(self, path: Path | None = None) -> None:
        """Scaffold for pushing local commits to remote."""
        _ = path
        raise NotImplementedError("GitChangeTracker._push() is not implemented yet")
