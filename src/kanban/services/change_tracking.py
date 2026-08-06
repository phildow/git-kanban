"""Domain service over a ChangeTracker implementation.

The facade depends on ChangeTrackingService rather than importing a
ChangeTracker implementation directly.  The service offers one method per
operation the facade performs — `commit_task_move`, `commit_board_rename`, and
so on — each taking the domain object the operation produced.  It builds the
commit data itself, hands it to a CommitMessageBuilder for formatting, and
gives the result to the ChangeTracker to write, so the facade knows nothing
about commit data or the message schema.

A commit message names a board and a column by name while a domain object
carries only its parent's slug, so the service holds the repository and
resolves those names itself.  Every commit covers the whole store: an
operation writes the task file and the .metadata files that order it, and a
move across boards touches two boards, so scoping a commit to one path would
leave part of the operation out of it.
"""

from __future__ import annotations

from pathlib import Path
from warnings import deprecated

from ..models.board import Board
from ..models.column import Column
from ..models.slug import Slug
from ..models.task import Task
from ..storage.base import BoardNotFound, ColumnNotFound, KanbanRepository
from ..tracking.base import ChangeTracker, Commit
from ..tracking.message import (
    BoardCommitData,
    ColumnCommitData,
    ColumnReorderCommitData,
    CommitData,
    CommitMessage,
    CommitMessageBuilder,
    TaskAssignCommitData,
    TaskCommitData,
    TaskMoveCommitData,
    TaskRenameCommitData,
    TaskTagCommitData,
)


class ChangeTrackingService:
    """Commits an operation, composing the message that describes it."""

    def __init__(
        self,
        change_tracker:  ChangeTracker,
        repository:      KanbanRepository,
        message_builder: CommitMessageBuilder | None = None,
    ) -> None:
        """
        Wrap the implementation to commit with, the repository, and the builder.

        Args:
            change_tracker:  The concrete implementation that writes commits.
            repository:      Read to resolve the board and column names a
                             message spells out from the slugs a domain object
                             carries.
            message_builder: The formatter that turns commit data into a
                             message.  A plain `CommitMessageBuilder` when none
                             is given — the builder is pure formatting, so
                             there is nothing to configure.
        """
        self.change_tracker = change_tracker
        self.repository = repository
        self.message_builder = message_builder or CommitMessageBuilder()

    # ── Boards ────────────────────────────────────────────────────────────────

    def commit_board_create(self, board: Board) -> Commit:
        """Commit the creation of board."""
        return self.add_commit(self._board_data("create", board))

    def commit_board_rename(self, board: Board, old_name: str) -> Commit:
        """
        Commit the rename of board.

        Args:
            board:    The board under its new name.
            old_name: The name it carried before.
        """
        return self.add_commit(self._board_data("rename", board, old_name))

    def commit_board_delete(self, board: Board) -> Commit:
        """Commit the deletion of board."""
        return self.add_commit(self._board_data("delete", board))

    # ── Columns ───────────────────────────────────────────────────────────────

    def commit_column_create(self, column: Column) -> Commit:
        """Commit the creation of column."""
        return self.add_commit(self._column_data("create", column))

    def commit_column_rename(self, column: Column, old_name: str) -> Commit:
        """
        Commit the rename of column.

        Args:
            column:   The column under its new name.
            old_name: The name it carried before.
        """
        return self.add_commit(self._column_data("rename", column, old_name))

    def commit_column_reorder(self, column: Column) -> Commit:
        """Commit the move of column to the position it now holds on its board."""
        data = ColumnReorderCommitData(
            id=column.id,
            path=str(column.path),
            board=self._board_name(column.board),
            name=column.name,
            position=column.position,
        )
        return self.add_commit(data)

    def commit_column_delete(self, column: Column) -> Commit:
        """Commit the deletion of column."""
        return self.add_commit(self._column_data("delete", column))

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def commit_task_create(self, task: Task) -> Commit:
        """Commit the creation of task."""
        return self.add_commit(self._task_data("create", task))

    def commit_task_update(self, task: Task) -> Commit:
        """Commit an update to task's fields."""
        return self.add_commit(self._task_data("update", task))

    def commit_task_unset(self, task: Task) -> Commit:
        """Commit the clearing of one or more of task's fields."""
        return self.add_commit(self._task_data("unset", task))

    def commit_task_comment(self, task: Task) -> Commit:
        """Commit a comment appended to task."""
        return self.add_commit(self._task_data("comment", task))

    def commit_task_delete(self, task: Task) -> Commit:
        """Commit the deletion of task."""
        return self.add_commit(self._task_data("delete", task))

    def commit_task_rename(self, task: Task, old_title: str) -> Commit:
        """
        Commit the rename of task.

        Args:
            task:      The task under its new title.
            old_title: The title it carried before.
        """
        data = TaskRenameCommitData(
            id=task.id,
            path=str(task.path),
            board=self._board_name(task.board),
            column=self._column_name(task.board, task.column),
            old_title=old_title,
            new_title=task.title,
        )
        return self.add_commit(data)

    def commit_task_assign(self, task: Task) -> Commit:
        """Commit the assignment of task to whoever it now names."""
        return self.add_commit(self._assign_data("assign", task, task.assigned_to))

    def commit_task_unassign(self, task: Task) -> Commit:
        """Commit the clearing of task's assignee."""
        return self.add_commit(self._assign_data("unassign", task))

    def commit_task_tag(self, task: Task, tag: str) -> Commit:
        """
        Commit a tag added to task.

        Args:
            task: The task the tag was added to.
            tag:  The tag added.
        """
        return self.add_commit(self._tag_data("tag", task, tag))

    def commit_task_untag(self, task: Task, tag: str) -> Commit:
        """
        Commit a tag removed from task.

        Args:
            task: The task the tag was removed from.
            tag:  The tag removed.
        """
        return self.add_commit(self._tag_data("untag", task, tag))

    def commit_task_move(
        self,
        task:        Task,
        from_board:  Slug,
        from_column: Slug,
    ) -> Commit:
        """
        Commit the move of task out of the column it was in.

        Archiving and unarchiving are moves into and out of the archive column
        and commit through here like any other.

        Args:
            task:        The task in the column it landed in.
            from_board:  The board it left, the same as the one it landed on
                         unless it crossed boards.
            from_column: The column it left.
        """
        data = TaskMoveCommitData(
            id=task.id,
            path=str(task.path),
            action="move",
            title=task.title,
            from_board=self._board_name(from_board),
            from_column=self._column_name(from_board, from_column),
            from_path=f"/{from_board}/{from_column}",
            to_board=self._board_name(task.board),
            to_column=self._column_name(task.board, task.column),
            to_path=f"/{task.board}/{task.column}",
        )
        return self.add_commit(data)

    # ── Commit data ───────────────────────────────────────────────────────────

    def _board_data(
        self,
        action:   str,
        board:    Board,
        old_name: str | None = None,
    ) -> BoardCommitData:
        """Return the commit data for an operation on board."""
        return BoardCommitData(
            id=board.id,
            path=str(board.path),
            action=action,
            name=board.name,
            old_name=old_name,
        )

    def _column_data(
        self,
        action:   str,
        column:   Column,
        old_name: str | None = None,
    ) -> ColumnCommitData:
        """Return the commit data for an operation on column."""
        return ColumnCommitData(
            id=column.id,
            path=str(column.path),
            action=action,
            board=self._board_name(column.board),
            name=column.name,
            old_name=old_name,
        )

    def _task_data(self, action: str, task: Task) -> TaskCommitData:
        """Return the commit data for an operation on task that names no second side."""
        return TaskCommitData(
            id=task.id,
            path=str(task.path),
            action=action,
            board=self._board_name(task.board),
            column=self._column_name(task.board, task.column),
            title=task.title,
        )

    def _assign_data(
        self,
        action:   str,
        task:     Task,
        assignee: str | None = None,
    ) -> TaskAssignCommitData:
        """Return the commit data for an assignment or its removal."""
        return TaskAssignCommitData(
            id=task.id,
            path=str(task.path),
            action=action,
            board=self._board_name(task.board),
            column=self._column_name(task.board, task.column),
            title=task.title,
            assignee=assignee,
        )

    def _tag_data(self, action: str, task: Task, tag: str) -> TaskTagCommitData:
        """Return the commit data for a tag added or removed."""
        return TaskTagCommitData(
            id=task.id,
            path=str(task.path),
            action=action,
            board=self._board_name(task.board),
            column=self._column_name(task.board, task.column),
            title=task.title,
            tag=tag,
        )

    # ── Names ─────────────────────────────────────────────────────────────────

    def _board_name(self, board: Slug) -> str:
        """
        Return the display name of the board, falling back to its slug.

        A name is worth a commit message reading well, never a commit failing:
        a board that has gone missing under us is reported by slug rather than
        raised.
        """
        try:
            return self.repository.get_board(board).name
        except BoardNotFound:
            return str(board)

    def _column_name(self, board: Slug, column: Slug) -> str:
        """Return the display name of the column, falling back to its slug."""
        try:
            return self.repository.get_column(board, column).name
        except (BoardNotFound, ColumnNotFound):
            return str(column)

    # ── Commit composition ────────────────────────────────────────────────────

    def build_message(self, data: CommitData) -> CommitMessage:
        """
        Return the message describing data, without committing anything.

        Args:
            data: The structured record of a single operation.
        """
        return self.message_builder.build(data)

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

    def add_commit(self, data: CommitData, path: Path | None = None) -> Commit:
        """
        Compose the message for data, then stage and commit, returning the commit.

        The tracker is handed the `CommitMessage` whole rather than its text:
        rendering it is the implementation's business, and git is only one way
        to hold a subject and its trailers.

        Args:
            data: The structured record of the operation being committed.
            path: Restrict the commit to this path within the store, relative
                  to the worktree root, or None to commit everything
                  outstanding.  The domain path data carries identifies the
                  object, not the file, so the facade supplies this.

        Raises:
            NothingToCommit: No change is outstanding within path.
            TypeError:       data is not a commit data type the builder knows.
        """
        return self.change_tracker.add_commit(self.build_message(data), path)

    @deprecated("Squashing is out of scope; nothing in the facade calls squash_commits().")
    def squash_commits(self, message: str, path: Path | None = None) -> Commit:
        """
        Collapse the commits since the last squash into a single commit.

        Deprecated: squashing is out of scope for now.  Nothing in the facade
        calls this and the git tracker does not implement it.
        """
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
