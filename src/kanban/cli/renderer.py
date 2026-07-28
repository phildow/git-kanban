"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console, ConsoleOptions, RenderResult
from rich.text import Text

from ..models import Board, Column, Slug, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus
from ..utils.render_helper import RenderHelper


class Renderer(CommandRenderer):
	def __init__(self, render_helper: RenderHelper) -> None:
		self.render_helper = render_helper
		# rich
		self.console = Console(color_system="auto")

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
		# rich
		self.console.print(value, highlight=False)
		# print(value)

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

	def render_board(self, args: argparse.Namespace, board: Board) -> None:
		self._emit(args, Text("Name: ") + Text(board.name, style="bold"))
		lines = [
			f"Path: {board.path}",
			f"Tasks: {board.task_count}",
		]
		self._emit(args, "\n".join(lines))

	# -----------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		if not result:
			self._emit(args, "No boards")
			return

		length = len(result)
		for i, board in enumerate(result):
			self.render_board(args, board)
			if length - i > 1:
				self._emit(args, "")

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board(args, result)

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board(args, result)

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board(args, result)

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		self._emit(args, Text("Deleted: ") + Text(result.name, style="bold"))
		self._emit(args, f"Path: {result.path}")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column(self, args: argparse.Namespace, column: Column) -> None:
		self._emit(args, Text("Name: ") + Text(column.name, style="bold"))
		lines = [
			f"Path: {column.path}",
			f"Tasks: {column.task_count}",
		]
		self._emit(args, "\n".join(lines))

	# -----------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		if not result:
			self._emit(args, "No columns")
			return

		length = len(result)
		for i, column in enumerate(result):
			self.render_column(args, column)
			if length - i > 1:
				self._emit(args, "")

	def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
		self.render_column(args, result)

	def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
		self.render_column(args, result)

	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		self.render_column(args, result)

	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		board = self.board_for_slug(result[0].board) if result else None
		if board is None:
			self._emit(args, "Unable to determine board for reordered columns.")
			return
		self.render_board(args, board)

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, Text("Deleted: ") + Text(result.name, style="bold"))
		self._emit(args, f"Path: {result.path}")

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task(self, args: argparse.Namespace, task: Task) -> None:
		column = self.column_for_path(task.path.parent)
		board = self.board_for_slug(task.board)
		self._emit(args, Text("Title: ") + Text(task.title, style="bold"))
		lines = [
			f"Path: {task.path}",
			f"",
			f"    Board: {board.name if board else '-'}",
			f"    Column: {column.name if column else '-'}",
			f"    Assigned To: {task.assigned_to or '-'}",
			f"    Priority: {task.priority or '-'}",
			f"    Due: {task.due_date.date().isoformat() if task.due_date else '-'}",
			f"    Tags: {', '.join(task.tags) if task.tags else '-'}",
			f"    Created by: {task.created_by or '-'}",
		]
		self._emit(args, "\n".join(lines))

	# -----------------------------------------------------------------------

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		if not result:
			self._emit(args, "No tasks")
			return

		length = len(result)
		for i, task in enumerate(result):
			self.render_task(args, task)
			if length - i > 1:
				self._emit(args, "")

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)
	
	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, Text("Edited: ") + Text(result.title, style="bold"))
		self._emit(args, f"Path: {result.path}")

	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
		result, _op = task_op
		self.render_task(args, result)

	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, Text("Deleted: ") + Text(result.title, style="bold"))
		self._emit(args, f"Path: {result.path}")

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

# ---------------------------------------------------------------------------
# Additional rendering (search, log, status, config)
# ---------------------------------------------------------------------------

	def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
		if not result:
			result = []
		self.render_task_list(args, result)

	def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
		# TODO: implement
		self._emit(args, result)

	def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
		# TODO: implement
		self._emit(args, result)

	def render_set_config(self, args: argparse.Namespace, result: None) -> None:
		# TODO: implement
		self._emit(args, result)

	def render_get_config(self, args: argparse.Namespace, result: str) -> None:
		# TODO: implement
		self._emit(args, result)

# ---------------------------------------------------------------------------
# Utilities and shared behavior for rendering commands
# ---------------------------------------------------------------------------

	def board_for_slug(self, slug: Slug) -> Board | None:
		"""Given a board slug, return the corresponding board."""
		return self.render_helper.board_for_slug(slug)
	
	def column_for_path(self, path: Path) -> Column | None:
		"""Given a column path, return the corresponding column."""
		return self.render_helper.column_for_path(path)