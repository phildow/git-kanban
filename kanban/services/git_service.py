"""Git orchestration service scaffolding.

This service wraps git-related operations so the coordinating facade can
compose commit, squash, and log workflows behind a single interface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GitCommit:
    """Represents a single git commit entry."""

    sha: str
    message: str | None = None


class GitService:
    """Coordinates git commit, squash, and log operations."""

    def __init__(self) -> None:
        """Create a git service scaffold with no backing implementation yet."""

    def add_commit(self, *, message: str, scope: str | None = None) -> GitCommit:
        """Create a commit and return the resulting commit metadata."""
        _ = message, scope
        raise NotImplementedError("GitService.add_commit() is not implemented yet")

    def squash_commits(self, *, message: str, scope: str | None = None) -> GitCommit:
        """Squash commits in scope and return the newly created squash commit."""
        _ = message, scope
        raise NotImplementedError("GitService.squash_commits() is not implemented yet")

    def get_history(self, *, limit: int = 20, scope: str | None = None) -> list[GitCommit]:
        """Return commit history entries for an optional scope."""
        _ = limit, scope
        raise NotImplementedError("GitService.get_history() is not implemented yet")

    def sync(self, *, scope: str | None = None) -> None:
        """Synchronize git state by pull/rebase first, then push."""
        self._pull_rebase(scope=scope)
        self._push(scope=scope)

    def _pull_rebase(self, *, scope: str | None = None) -> None:
        """Scaffold for pulling and rebasing from remote."""
        _ = scope
        raise NotImplementedError("GitService._pull_rebase() is not implemented yet")

    def _push(self, *, scope: str | None = None) -> None:
        """Scaffold for pushing local commits to remote."""
        _ = scope
        raise NotImplementedError("GitService._push() is not implemented yet")
