"""JSON output renderer for the kanban CLI."""

from __future__ import annotations

import argparse
import json
from functools import wraps

from models import Board, Column, Task
from services.kanban import GitCommit, KanbanStatus


def _requires_verbose(method):
    @wraps(method)
    def _wrapped(self, args: argparse.Namespace, result):
        if not getattr(args, "verbose", False):
            return None
        else:
            return method(self, args, result)
    return _wrapped


def _task_dict(task: Task) -> dict:
    """Minimal task representation used in list and search results."""
    return {
        "id": str(task.id),
        "title": task.title,
        "slug": task.slug,
        "board": task.board,
        "column": task.column,
        "assigned_to": task.assigned_to,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "tags": task.tags,
        "created_by": task.created_by,
    }


def _task_detail_dict(task: Task) -> dict:
    """Full task representation including timestamps and body."""
    return {
        **_task_dict(task),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "body": task.body,
    }


def _board_dict(board: Board) -> dict:
    return {
        "name": board.name,
        "slug": board.slug,
        "column_count": board.column_count,
        "task_count": board.task_count,
    }


def _column_dict(column: Column) -> dict:
    return {
        "name": column.name,
        "slug": column.slug,
        "board": column.board,
        "position": column.position,
    }


class JsonRenderer:
    """Renders all CLI output as JSON."""

    def _emit(self, args: argparse.Namespace, value: object) -> None:
        if getattr(args, "quiet", False):
            return
        if value is None:
            return
        print(value)

    # ── Initialisation ────────────────────────────────────────────────────────

    @_requires_verbose
    def render_init(self, args: argparse.Namespace, result: bool) -> None:
        _ = result
        self._emit(args, json.dumps({"initialized": result}, indent=2))

    # ── Boards ────────────────────────────────────────────────────────────────

    def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
        self._emit(args, json.dumps([_board_dict(b) for b in result], indent=2))

    @_requires_verbose
    def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps(_board_dict(result), indent=2))

    @_requires_verbose
    def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
        self._emit(args, json.dumps(_board_dict(result), indent=2))

    @_requires_verbose
    def render_board_delete(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"deleted": getattr(args, "board", None)}, indent=2))

    # ── Columns ───────────────────────────────────────────────────────────────

    def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
        self._emit(args, json.dumps([_column_dict(c) for c in result], indent=2))

    @_requires_verbose
    def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
        self._emit(args, json.dumps(_column_dict(result), indent=2))

    @_requires_verbose
    def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
        self._emit(args, json.dumps(_column_dict(result), indent=2))

    @_requires_verbose
    def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
        self._emit(args, json.dumps([_column_dict(c) for c in result], indent=2))

    @_requires_verbose
    def render_column_delete(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"deleted": getattr(args, "path", None)}, indent=2))

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
        self._emit(args, json.dumps([_task_dict(t) for t in result], indent=2))

    @_requires_verbose
    def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(_task_detail_dict(result), indent=2))

    def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(_task_detail_dict(result), indent=2))

    def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(_task_detail_dict(result), indent=2))

    @_requires_verbose
    def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(_task_detail_dict(result), indent=2))

    @_requires_verbose
    def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
        self._emit(args, json.dumps(_task_detail_dict(result), indent=2))

    @_requires_verbose
    def render_task_delete(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"deleted": getattr(args, "path", None)}, indent=2))

    # ── Search, log, status, config ───────────────────────────────────────────

    def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
        self._emit(args, json.dumps([_task_dict(t) for t in result], indent=2))

    def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
        self._emit(args, json.dumps([{"sha": c.sha} for c in result], indent=2))

    def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
        context = result.user_context
        self._emit(args, json.dumps({
            "board": context.board,
            "column": context.column,
            "board_count": result.board_count,
            "column_count": result.column_count,
            "task_count": result.task_count,
            "index_fresh": result.index_fresh,
            "uncommitted_changes": result.uncommitted_changes,
        }, indent=2))

    @_requires_verbose
    def render_config_set(self, args: argparse.Namespace, result: None) -> None:
        _ = result
        self._emit(args, json.dumps({"key": args.key, "value": args.value}))

    @_requires_verbose
    def render_config_get(self, args: argparse.Namespace, result: str) -> None:
        self._emit(args, json.dumps({"key": args.key, "value": result}, indent=2))
