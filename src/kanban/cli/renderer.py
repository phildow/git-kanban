"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..models import Board, Column, Slug, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus
from ..utils.render_helper import RenderHelper


class Renderer(CommandRenderer):
	def __init__(self, render_helper: RenderHelper) -> None:
		self.render_helper = render_helper

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

		# self._emit(args, "\n".join(str(board.path) for board in result))

		length = len(result)
		for i, board in enumerate(result):
			lines = [
				f"Name: {board.name}",
				f"Path: {board.path}",
				# f"    Columns: {board.column_count}",
				f"Tasks: {board.task_count}",
			]
			self._emit(args, "\n".join(lines))
			if length - i > 1:
				self._emit(args, "")

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		self._emit(args, str(result.path))

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		lines = [
			f"Name: {result.name}",
			f"Path: {result.path}",
			# f"Slug: {result.slug}",
			# f"Columns: {result.column_count}",
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

		# self._emit(args, "\n".join(str(column.path) for column in result))

		length = len(result)
		for i, column in enumerate(result):
			lines = [
				f"Name: {column.name}",
				f"Path: {column.path}",
				# f"    Slug: {column.slug}",
				# f"    Board: {column.board}",
				# f"Position: {column.position}",
				f"Tasks: {column.task_count}",
			]
			self._emit(args, "\n".join(lines))
			if length - i > 1:
				self._emit(args, "")

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

		length = len(result)
		for i, task in enumerate(result):
			column = self.column_for_path(task.path.parent)
			board = self.board_for_slug(task.board)

			lines = [
				f"Title: {task.title}",
				f"Path: {task.path}",
				f"",
				# f"    Slug: {task.slug}",
				f"    Board: {board.name if board else '-'}",
				f"    Column: {column.name if column else '-'}",
				f"    Assigned To: {task.assigned_to or "-"}",
				f"    Priority: {task.priority or "-"}",
				f"    Due: {task.due_date.date().isoformat() if task.due_date else "-"}",
				f"    Tags: {", ".join(task.tags) if task.tags else "-"}",
				f"    Created by: {task.created_by or "-"}",
			]

			self._emit(args, "\n".join(lines))
			if length - i > 1:
				self._emit(args, "")

		# self._emit(args, "\n".join(str(task.path) for task in result))

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_list(args, [result])

	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_list(args, [result])

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_list(args, [result])

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
		if not result:
			self._emit(args, "No results")
			return
		self.render_task_list(args, result)

	def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
		self._emit(args, result)

	def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
		self._emit(args, result)

	def render_set_config(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	def render_get_config(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)

# ---------------------------------------------------------------------------
# Utilities and shared behavior for rendering commands
# ---------------------------------------------------------------------------

	def render_task_metadata(self, args: argparse.Namespace, task: Task) -> None:
		"""Render the metadata of a task in a table format."""
		lines = [
			f"Title: {task.title}",
			f"Path: {task.path}",
			f"Slug: {task.slug}",
			f"Board: {task.board or '-'}",
			f"Column: {task.column or '-'}",
			f"Assigned To: {task.assigned_to or "-"}",
			f"Priority: {task.priority or "-"}",
			f"Due: {task.due_date.date().isoformat() if task.due_date else "-"}",
			f"Tags: {", ".join(task.tags) if task.tags else "-"}",
			f"Created by: {task.created_by or "-"}",
		]

		self._emit(args, "\n".join(lines))

	def board_for_slug(self, slug: Slug) -> Board | None:
		"""Given a board slug, return the corresponding board."""
		return self.render_helper.board_for_slug(slug)
	
	def column_for_path(self, path: Path) -> Column | None:
		"""Given a column path, return the corresponding column."""
		return self.render_helper.column_for_path(path)