"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from functools import wraps

from ..models import Board, Column, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus


def _requires_verbose(method):
	""""Decorator to ensure that the decorated method only executes when verbose mode is enabled."""
	@wraps(method)
	def _wrapped(self, args: argparse.Namespace, result):
		if not args.verbose:
			return None
		else:
			return method(self, args, result)

	return _wrapped


class Renderer(CommandRenderer):
	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if value is None:
			return
		print(value)

# ---------------------------------------------------------------------------
# Initialization and context rendering
# ---------------------------------------------------------------------------

	@_requires_verbose
	def render_init(self, args: argparse.Namespace, result: bool) -> None:
		if result:
			self._emit(args, "Kanban system initialized successfully.")
		else:
			self._emit(args, "Failed to initialize Kanban system.")

	@_requires_verbose
	def render_change_dir(self, args: argparse.Namespace, result: object) -> None:
		_ = args, result
		raise NotImplementedError("Change directory is not supported by the CLI JSON renderer. Use the `cd` command in the REPL instead.")

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		fmt = args.format

		if not result:
			self._emit(args, "No boards")
			return

		if fmt == "plain":
			self._emit(args, "\n".join(board.name for board in result))
			return

		lines = ["Boards", "------"]
		for board in result:
			lines.append(f"{board.name} ({board.column_count} columns)")
		self._emit(args, "\n".join(lines))

	@_requires_verbose
	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		board_name = result.name or args.board
		self._emit(args, f"Board created: {board_name}")

	@_requires_verbose
	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		# TODO: get this from a result parameter as well
		old_name = args.path
		new_name = result.name or args.new_name
		self._emit(args, f"Board renamed: {old_name} -> {new_name}")

	@_requires_verbose
	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		board_name = result.name or args.new_name
		self._emit(args, f"Board deleted: {board_name}")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		fmt = args.format

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
		else:
			self._emit(args, f"Column created: {column_name}")

	@_requires_verbose
	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		path = args.path or ""
		old_name = path.split("/", 1)[1] if "/" in path else path
		board_name = result.board or (path.split("/", 1)[0] if "/" in path else None)
		new_name = result.name or args.new_name

		if board_name:
			self._emit(args, f"Column renamed: {board_name}/{old_name} -> {board_name}/{new_name}")
		else:
			self._emit(args, f"Column renamed: {old_name} -> {new_name}")

	@_requires_verbose
	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		path = args.path or ""
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		position = args.position
		target = f"{board_name}/{column_name}" if board_name else column_name

		if isinstance(position, int):
			self._emit(args, f"Column reordered: {target} -> position {position + 1}")
		else:
			self._emit(args, f"Column reordered: {target}")

	@_requires_verbose
	def render_column_delete(self, args: argparse.Namespace, result: None) -> None:
		_ = result
		path = args.path or ""
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		if board_name:
			self._emit(args, f"Column deleted: {board_name}/{column_name}")
		else:
			self._emit(args, f"Column deleted: {column_name}")

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		fmt = args.format

		if not result:
			self._emit(args, "No tasks")
			return

		if fmt == "plain":
			self._emit(args, "\n".join(str(task.path) for task in result))
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
		self._emit(args, f"Created Task: {result.title}")
		self._emit(args, f"Path: {result.path}")

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

	@_requires_verbose
	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		old_slug = args.path or ""
		new_slug = result.slug
		self._emit(args, f"Task renamed: {result.title}: {old_slug} -> {new_slug}")

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
		result, op = task_op
		if result.column and op in ["top", "bottom"]:
			msg = f"Task moved to {op} in {result.column}"
		elif result.column and op in ["up", "down"]:
			msg = f"Task moved {op} in {result.column}"
		else:
			msg = f"Task reordered: {result.slug} ({op})"
		self._emit(args, msg)

	@_requires_verbose
	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, f"Deleted Task: {result.title}")
		self._emit(args, f"Path: {result.path}")

	@_requires_verbose
	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

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
	def render_set_config(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	@_requires_verbose
	def render_get_config(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
