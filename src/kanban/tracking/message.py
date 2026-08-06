"""
Formatter that turns structured commit data into a commit message.

`CommitMessageBuilder` is pure formatting and knows nothing about git.  The
facade hands `ChangeTrackingService` the structured data for an operation —
entity, action, id, path, board, column, from, to — and the service asks the
builder for the subject line and trailer block that describe it, per the commit
message schema, before forwarding the result to the `ChangeTracker`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

@dataclass
class CommitData:
    """Base fields common to every commit."""
    id: UUID
    path: str  # full path, post-operation

@dataclass
class BoardCommitData(CommitData):
    """create, rename, delete"""
    action: Literal["create", "rename", "delete"]
    name: str              # current name — used in subject and, for rename, as the "to" side
    old_name: str | None = None  # rename only

@dataclass
class ColumnCommitData(CommitData):
    """create, rename, delete"""
    action: Literal["create", "rename", "delete"]
    board: str             # board name, for the trailer
    name: str
    old_name: str | None = None  # rename only

@dataclass
class ColumnReorderCommitData(CommitData):
    """reorder — separate from the above since it carries a position, not a name change"""
    board: str
    name: str
    position: int

@dataclass
class TaskCommitData(CommitData):
    """create, update, unset, delete, comment"""
    action: Literal["create", "update", "unset", "delete", "comment"]
    board: str
    column: str
    title: str

@dataclass
class TaskRenameCommitData(CommitData):
    board: str
    column: str
    old_title: str
    new_title: str

@dataclass
class TaskAssignCommitData(CommitData):
    """assign, unassign"""
    action: Literal["assign", "unassign"]
    board: str
    column: str
    title: str
    assignee: str | None = None  # None on unassign

@dataclass
class TaskTagCommitData(CommitData):
    """tag, untag"""
    action: Literal["tag", "untag"]
    board: str
    column: str
    title: str
    tag: str

@dataclass
class TaskMoveCommitData(CommitData):
    """move — archiving and unarchiving are moves and carry no message of their own"""
    action: Literal["move"]
    title: str
    from_board: str
    from_column: str
    from_path: str          # trailer From — source column path
    to_board: str
    to_column: str
    to_path: str             # trailer To — destination column path


@dataclass(frozen=True)
class CommitMessage:
    """
    A composed commit message: the subject line and the trailers below it.

    `subject` and `trailers` are kept apart so a caller can read either half —
    the TUI shows a subject, a test asserts on a trailer — and `text` renders
    the message a `ChangeTracker` is given.
    """

    subject:  str
    trailers: dict[str, str]

    @property
    def text(self) -> str:
        """Return the full message: subject, a blank line, then the trailers."""
        block = "\n".join(f"{key}: {value}" for key, value in self.trailers.items())
        return f"{self.subject}\n\n{block}"

    def __str__(self) -> str:
        """Return the rendered message."""
        return self.text


class CommitMessageBuilder:
    """
    Builds a commit message — subject line and trailers — from commit data.

    Pure formatting: the builder knows the commit message schema and nothing
    about git, the store, or the operation that produced the data.  `build`
    dispatches on the type of the data it is handed, so a new kind of commit is
    a new `CommitData` subclass and a new `_build_*` method beside it.
    """

    def build(self, data: CommitData) -> CommitMessage:
        """
        Return the message describing data.

        Args:
            data: The structured record of a single operation.

        Raises:
            TypeError: data is not a commit data type the builder knows.
        """
        match data:
            case BoardCommitData():
                return self._build_board(data)
            case ColumnCommitData():
                return self._build_column(data)
            case ColumnReorderCommitData():
                return self._build_column_reorder(data)
            case TaskRenameCommitData():
                return self._build_task_rename(data)
            case TaskAssignCommitData():
                return self._build_task_assign(data)
            case TaskTagCommitData():
                return self._build_task_tag(data)
            case TaskMoveCommitData():
                return self._build_task_move(data)
            case TaskCommitData():
                return self._build_task(data)
            case _:
                raise TypeError(f"Unsupported commit data: {type(data).__name__}")

    # ------------------------------------------------------------------
    # Board
    # ------------------------------------------------------------------

    def _build_board(self, data: BoardCommitData) -> CommitMessage:
        """Build `board(<action>) <name>`, a rename naming both sides."""
        if data.action == "rename" and data.old_name is not None:
            subject = f"board(rename) {data.old_name} → {data.name}"
        else:
            subject = f"board({data.action}) {data.name}"

        return CommitMessage(subject, self._trailers("board", data.action, data))

    # ------------------------------------------------------------------
    # Column
    # ------------------------------------------------------------------

    def _build_column(self, data: ColumnCommitData) -> CommitMessage:
        """Build `column(<action>) <name>`, a rename naming both sides."""
        if data.action == "rename" and data.old_name is not None:
            subject = f"column(rename) {data.old_name} → {data.name}"
        else:
            subject = f"column({data.action}) {data.name}"

        trailers = self._trailers("column", data.action, data, Board=data.board)
        return CommitMessage(subject, trailers)

    def _build_column_reorder(self, data: ColumnReorderCommitData) -> CommitMessage:
        """Build `column(reorder) <name> → position <n>`."""
        subject = f"column(reorder) {data.name} → position {data.position}"
        trailers = self._trailers("column", "reorder", data, Board=data.board)
        return CommitMessage(subject, trailers)

    # ------------------------------------------------------------------
    # Task
    # ------------------------------------------------------------------

    def _build_task(self, data: TaskCommitData) -> CommitMessage:
        """Build `task(<action>) <title>` for an operation with no second side."""
        subject = f"task({data.action}) {data.title}"
        return CommitMessage(subject, self._task_trailers(data.action, data))

    def _build_task_rename(self, data: TaskRenameCommitData) -> CommitMessage:
        """Build `task(rename) <old title> → <new title>`."""
        subject = f"task(rename) {data.old_title} → {data.new_title}"
        return CommitMessage(subject, self._task_trailers("rename", data))

    def _build_task_assign(self, data: TaskAssignCommitData) -> CommitMessage:
        """Build `task(assign) <title> → <assignee>`, or `task(unassign) <title>`."""
        if data.action == "assign" and data.assignee is not None:
            subject = f"task(assign) {data.title} → {data.assignee}"
        else:
            subject = f"task({data.action}) {data.title}"

        return CommitMessage(subject, self._task_trailers(data.action, data))

    def _build_task_tag(self, data: TaskTagCommitData) -> CommitMessage:
        """Build `task(tag) <title> → <tag>`, likewise for untag."""
        subject = f"task({data.action}) {data.title} → {data.tag}"
        return CommitMessage(subject, self._task_trailers(data.action, data))

    def _build_task_move(self, data: TaskMoveCommitData) -> CommitMessage:
        """
        Build `task(move) <title> — <source> → <destination>`.

        The destination is a column name while the task stays on its board and
        `<board>/<column>` once it crosses to another, which is the only place
        the board is worth spelling out.
        """
        destination = data.to_column
        if data.to_board != data.from_board:
            destination = f"{data.to_board}/{data.to_column}"

        subject = f"task(move) {data.title} — {data.from_column} → {destination}"
        trailers = self._trailers(
            "task", "move", data, From=data.from_path, To=data.to_path
        )
        return CommitMessage(subject, trailers)

    # ------------------------------------------------------------------
    # Trailers
    # ------------------------------------------------------------------

    def _trailers(
        self,
        entity: str,
        action: str,
        data:   CommitData,
        **rest: str,
    ) -> dict[str, str]:
        """Return the trailers every commit carries, followed by rest in order."""
        return {
            "Entity": entity,
            "Action": action,
            "Id":     str(data.id),
            "Path":   data.path,
            **rest,
        }

    def _task_trailers(
        self,
        action: str,
        data:   TaskCommitData | TaskRenameCommitData | TaskAssignCommitData | TaskTagCommitData,
    ) -> dict[str, str]:
        """Return the trailers a task commit carries when it names no destination."""
        return self._trailers(
            "task", action, data, Board=data.board, Column=data.column
        )
