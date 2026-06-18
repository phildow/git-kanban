"""CLI rendering helpers."""

from __future__ import annotations

import argparse
import json
from functools import wraps

from models import UserContext, Board, Column, Task
from services.kanban import GitCommit, KanbanRoot, KanbanStatus


def _requires_verbose(method):
	@wraps(method)
	def _wrapped(self, args: argparse.Namespace, result):
		if not getattr(args, "verbose", False):
			return None
		return method(self, args, result)

	return _wrapped


class Renderer:
	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if getattr(args, "quiet", False):
			return
		if value is None:
			return
		print(value)

# ---------------------------------------------------------------------------
# Initialization and context rendering
# ---------------------------------------------------------------------------

	@_requires_verbose
	def render_init(self, args: argparse.Namespace, result: KanbanRoot) -> None:
		self._emit(args, result)

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		fmt = getattr(args, "format", "plain")

		if fmt == "json":
			payload = [
				{
					"name": board.name,
					"column_count": len(board.columns),
				}
				for board in result
			]
			self._emit(args, json.dumps(payload, indent=2))
			return

		if not result:
			self._emit(args, "No boards")
			return

		if fmt == "plain":
			self._emit(args, "\n".join(board.name for board in result))
			return

		lines = ["Boards", "------"]
		for board in result:
			lines.append(f"{board.name} ({len(board.columns)} columns)")
		self._emit(args, "\n".join(lines))

	@_requires_verbose
	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		board_name = result.name or getattr(args, "board", None)
		self._emit(args, f"Board created: {board_name}")

	@_requires_verbose
	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		old_name = getattr(args, "board", None)
		new_name = result.name or getattr(args, "new_name", None)
		self._emit(args, f"Board renamed: {old_name} -> {new_name}")

	@_requires_verbose
	def render_board_delete(self, args: argparse.Namespace, result: None) -> None:
		_ = result
		board_name = getattr(args, "board", None)
		self._emit(args, f"Board deleted: {board_name}")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		fmt = getattr(args, "format", "plain")

		if fmt == "json":
			payload = [
				{
					"name": column.name,
					"board": column.board,
					"position": column.position,
				}
				for column in result
			]
			self._emit(args, json.dumps(payload, indent=2))
			return

		if not result:
			self._emit(args, "No columns")
			return

		if fmt == "plain":
			self._emit(args, "\n".join(column.name for column in result))
			return

		lines = ["Columns", "-------"]
		for column in result:
			lines.append(f"{column.position + 1}. {column.name}")
		self._emit(args, "\n".join(lines))

	@_requires_verbose
	def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
		board_name = result.board
		column_name = result.name
		if board_name and column_name:
			self._emit(args, f"Column created: {board_name}/{column_name}")
			return
		self._emit(args, f"Column created: {column_name}")

	@_requires_verbose
	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		path = getattr(args, "path", "") or ""
		old_name = path.split("/", 1)[1] if "/" in path else path
		board_name = result.board or (path.split("/", 1)[0] if "/" in path else None)
		new_name = result.name or getattr(args, "new_name", None)

		if board_name:
			self._emit(args, f"Column renamed: {board_name}/{old_name} -> {board_name}/{new_name}")
			return
		self._emit(args, f"Column renamed: {old_name} -> {new_name}")

	@_requires_verbose
	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		path = getattr(args, "path", "") or ""
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		position = getattr(args, "position", None)
		target = f"{board_name}/{column_name}" if board_name else column_name

		if isinstance(position, int):
			self._emit(args, f"Column reordered: {target} -> position {position + 1}")
			return
		self._emit(args, f"Column reordered: {target}")

	@_requires_verbose
	def render_column_delete(self, args: argparse.Namespace, result: None) -> None:
		_ = result
		path = getattr(args, "path", "") or ""
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		if board_name:
			self._emit(args, f"Column deleted: {board_name}/{column_name}")
			return
		self._emit(args, f"Column deleted: {column_name}")

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		fmt = getattr(args, "format", "plain")

		if fmt == "json":
			payload = [
				{
					"id": str(task.id),
					"title": task.title,
					"slug": task.slug,
					"board": task.board,
					"column": task.column,
					"assignee": task.assignee,
					"priority": task.priority,
					"due_date": task.due_date.isoformat() if task.due_date else None,
					"tags": task.tags,
					"created_by": task.created_by,
				}
				for task in result
			]
			self._emit(args, json.dumps(payload, indent=2))
			return

		if not result:
			self._emit(args, "No tasks")
			return

		if fmt == "plain":
			self._emit(args, "\n".join(task.slug for task in result))
			return

		lines = ["Tasks", "-----"]
		for task in result:
			location = ""
			if task.board and task.column:
				location = f" ({task.board}/{task.column})"
			elif task.board:
				location = f" ({task.board})"
			lines.append(f"- {task.slug}{location}")
		self._emit(args, "\n".join(lines))

	@_requires_verbose
	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		# TODO: Consider more detailed output for verbose mode, and a more concise message for non-verbose
		# TODO: Reconsider whether board/column should be Optional
		if result.board and result.column:
			self._emit(args, f"Task created: {result.board}/{result.column}/{result.slug}")
		else:
			self._emit(args, f"Task created: {result.slug}")

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		fmt = getattr(args, "format", "plain")

		if fmt == "json":
			payload = {
				"id": str(result.id),
				"title": result.title,
				"slug": result.slug,
				"board": result.board,
				"column": result.column,
				"assignee": result.assignee,
				"priority": result.priority,
				"due_date": result.due_date.isoformat() if result.due_date else None,
				"tags": result.tags,
				"created_by": result.created_by,
				"created_at": result.created_at.isoformat() if result.created_at else None,
				"updated_at": result.updated_at.isoformat() if result.updated_at else None,
				"body": result.body,
			}
			self._emit(args, json.dumps(payload, indent=2))
			return

		lines = [
			f"Slug: {result.slug}",
			f"ID: {result.id}",
			f"Location: {result.board}/{result.column}" if result.board and result.column else "Location: (unscoped)",
			f"Assignee: {result.assignee or "-"}",
			f"Priority: {result.priority or "-"}",
			f"Due: {result.due_date.isoformat() if result.due_date else "-"}",
			f"Tags: {", ".join(result.tags) if result.tags else "-"}",
			f"Created by: {result.created_by or "-"}",
		]
		self._emit(args, "\n".join(lines))

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_task_delete(self, args: argparse.Namespace, result: None) -> None:
		_ = result
		path = getattr(args, "path", None)
		if path:
			self._emit(args, f"Task deleted: {path}")
			return
		self._emit(args, "Task deleted")

# ---------------------------------------------------------------------------
# Additional rendering (search, log, status, config)
# ---------------------------------------------------------------------------

	def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
		self._emit(args, result)

	def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
		self._emit(args, result)

	def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_config_set(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_config_get(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
