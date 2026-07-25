"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..models import Board, Column, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus


class Renderer(CommandRenderer):
	def _path_from_args(self, args: argparse.Namespace) -> Path:
		"""Return args.path as a Path for display formatting."""
		path = getattr(args, "path", None)
		if isinstance(path, Path):
			return path
		if path is None:
			return Path("/")
		return Path(str(path))

	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if value is None:
			return
		print(value)

# ---------------------------------------------------------------------------
# Initialization and context rendering
# ---------------------------------------------------------------------------

	def render_init(self, args: argparse.Namespace, result: bool) -> None:
		if result:
			self._emit(args, "Kanban system initialized successfully.")
		else:
			self._emit(args, "Failed to initialize Kanban system.")

	def render_set_board(self, args: argparse.Namespace, result: object) -> None:
		_ = args, result
		raise NotImplementedError("Change directory is not supported by the CLI JSON renderer. Use the `cd` command in the REPL instead.")

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		if not result:
			self._emit(args, "No boards")
			return

		self._emit(args, "\n".join(str(board.path) for board in result))

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		self._emit(args, str(result.path))

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		lines = [
			f"Name: {result.name}",
			f"Path: {result.path}",
			# f"Slug: {result.slug}",
			f"Columns: {result.column_count}",
			f"Tasks: {result.task_count}",
		]
		self._emit(args, "\n".join(lines))

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		self._emit(args, str(result.path))

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		self._emit(args, str(result.path))

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		if not result:
			self._emit(args, "No columns")
			return

		self._emit(args, "\n".join(str(column.path) for column in result))

	def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
		lines = [
			f"Name: {result.name}",
			f"Path: {result.path}",
			# f"Slug: {result.slug}",
			# f"Board: {result.board}",
			f"Position: {result.position}",
			f"Tasks: {result.task_count}",
		]
		self._emit(args, "\n".join(lines))

	def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, str(result.path))

	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, str(result.path))

	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		self._emit(args, "\n".join(str(column.path) for column in result))

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, str(result.path))

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		if not result:
			self._emit(args, "No tasks")
			return

		self._emit(args, "\n".join(str(task.path) for task in result))

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		lines = [
			f"Title: {result.title}",
			f"Slug: {result.slug}",
			f"ID: {result.id}",
			f"Location: {result.board}/{result.column}" if result.board and result.column else "Location: (unscoped)",
			f"Assigned To: {result.assigned_to or "-"}",
			f"Priority: {result.priority or "-"}",
			f"Due: {result.due_date.date().isoformat() if result.due_date else "-"}",
			f"Tags: {", ".join(result.tags) if result.tags else "-"}",
			f"Created by: {result.created_by or "-"}",
		]
		# TODO: add body
		self._emit(args, "\n".join(lines))

	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
		result, _op = task_op
		self._emit(args, str(result.path))

	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

# ---------------------------------------------------------------------------
# Additional rendering (search, log, status, config)
# ---------------------------------------------------------------------------

	def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
		self._emit(args, result)

	def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
		self._emit(args, result)

	def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
		self._emit(args, result)

	def render_set_config(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	def render_get_config(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
