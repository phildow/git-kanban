"""JSON output renderer for the kanban CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..models import Board, Column, Task, UserContext
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus
from ..services.render_service import RenderService


def _task_dict(task: Task, board: dict | None, column: dict | None) -> dict:
    """Minimal task representation used in list and search results."""
    return {
        "title": task.title,
        "path": str(task.path),
        "slug": task.slug,
        "board": board,
        "column": column,
        "assigned_to": task.assigned_to,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "tags": task.tags,
        "created_by": task.created_by,
    }


def _task_detail_dict(task: Task, board: dict | None, column: dict | None) -> dict:
    """Full task representation including timestamps and body."""
    return {
        **_task_dict(task, board, column),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "body": task.body,
    }


def _board_dict(board: Board) -> dict:
    return {
        "name": board.name,
        "path": str(board.path),
        "slug": board.slug,
        "column_count": board.column_count,
        "task_count": board.task_count,
    }


def _column_dict(column: Column, board: dict | None) -> dict:
    return {
        "name": column.name,
        "path": str(column.path),
        "slug": column.slug,
        "board": board,
        "position": column.position,
        "task_count": column.task_count,
    }


def _board_ref_dict(board: Board) -> dict:
    """Nested board reference embedded in task output."""
    return {"name": board.name, "path": str(board.path), "slug": board.slug}


def _column_ref_dict(column: Column) -> dict:
    """Nested column reference embedded in task output."""
    return {"name": column.name, "path": str(column.path), "slug": column.slug}


class JsonRenderer(CommandRenderer):
    """Renders all CLI output as JSON."""

    def __init__(self, render_service: RenderService) -> None:
        self.render_service = render_service

    def _path_str(self, args: argparse.Namespace) -> str:
        """Return args.path serialized as a string path."""
        path = args.path
        if isinstance(path, Path):
            return str(path)
        if path is None:
            return ""
        return str(Path(str(path)))

    def _emit(self, args: argparse.Namespace, value: object) -> None:
        if value is None:
            return
        print(value)

    def _task_refs(self, task: Task) -> tuple[dict | None, dict | None]:
        """Resolve nested board and column reference dicts for a task.

        Returns `None` for either ref when the render service cannot resolve
        the underlying slug.
        """
        board = self.render_service.board_for_slug(task.board)
        column = self.render_service.column_for_path(Path(f"/{task.board}/{task.column}"))
        board_ref = _board_ref_dict(board) if board is not None else None
        column_ref = _column_ref_dict(column) if column is not None else None
        return board_ref, column_ref

    def _task_dict(self, task: Task) -> dict:
        board, column = self._task_refs(task)
        return _task_dict(task, board, column)

    def _task_detail_dict(self, task: Task) -> dict:
        board, column = self._task_refs(task)
        return _task_detail_dict(task, board, column)

    def _column_dict(self, column: Column) -> dict:
        """Column representation with the board resolved as a nested ref dict.

        The `board` value is `None` when the render service cannot resolve
        the column's board slug.
        """
        board = self.render_service.board_for_slug(column.board)
        board_ref = _board_ref_dict(board) if board is not None else None
        return _column_dict(column, board_ref)

    # ── Initialisation ────────────────────────────────────────────────────────

    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        _ = result
        self._emit(args, json.dumps({"initialized": result}, indent=2))

    def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
        raise NotImplementedError("Change directory is not supported by the CLI JSON renderer. Use the `cd` command in the REPL instead.")

    # ── Boards ────────────────────────────────────────────────────────────────

    def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
        self._emit(args, json.dumps([_board_dict(b) for b in result], indent=2))

    def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps(_board_dict(result), indent=2))

    def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps(_board_dict(result), indent=2))

    def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps(_board_dict(result), indent=2))

    def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps({"deleted": result.name}, indent=2))

    # ── Columns ───────────────────────────────────────────────────────────────

    def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
        self._emit(args, json.dumps([self._column_dict(c) for c in result], indent=2))

    def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
        self._emit(args, json.dumps(self._column_dict(result), indent=2))

    def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
        self._emit(args, json.dumps(self._column_dict(result), indent=2))

    def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
        self._emit(args, json.dumps(self._column_dict(result), indent=2))

    def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
        self._emit(args, json.dumps([self._column_dict(c) for c in result], indent=2))

    def render_column_delete(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"deleted": self._path_str(args)}, indent=2))

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
        self._emit(args, json.dumps([self._task_dict(t) for t in result], indent=2))

    def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_view(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_info(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_dict(result), indent=2))

    def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
        result, _ = task_op
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(self._task_detail_dict(result), indent=2))

    def render_task_delete(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"deleted": self._path_str(args)}, indent=2))

    # ── Search, log, status, config ───────────────────────────────────────────

    def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
        self._emit(args, json.dumps([self._task_dict(t) for t in result], indent=2))

    def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
        self._emit(args, json.dumps([{"sha": c.sha} for c in result], indent=2))

    def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
        context = result.user_context
        self._emit(args, json.dumps({
            "board": context.board,
            "board_count": result.board_count,
            "column_count": result.column_count,
            "task_count": result.task_count,
            "index_fresh": result.index_fresh,
            "uncommitted_changes": result.uncommitted_changes,
        }, indent=2))

    def render_set_config(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"key": args.key, "value": args.value}))

    def render_get_config(self, args: argparse.Namespace, result: str) -> None:
        self._emit(args, json.dumps({"key": args.key, "value": result}, indent=2))
