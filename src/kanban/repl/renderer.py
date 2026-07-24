"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from pathlib import Path
from functools import wraps
import shutil
from warnings import deprecated

from ..models import UserContext, Board, Column, Task
from ..protocols.command_renderer import CommandRenderer
from ..repl.render_helper import RenderHelper
from ..services.kanban import GitCommit, KanbanStatus

# TODO: Let's just remove this and the no-rich option

@deprecated("The RichRenderer is used by default. This class is deprecated and will be removed in a future version.")
class Renderer(CommandRenderer):
	def __init__(self, render_helper: RenderHelper):
		self.render_helper = render_helper

	def _path_from_args(self, args: argparse.Namespace) -> Path:
		"""Return args.path as a Path for display formatting."""
		path = getattr(args, "path", None)
		if isinstance(path, Path):
			return path
		if path is None:
			return Path(".")
		return Path(str(path))

	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if value is None:
			return
		print(value)


	def _clamped(self, s: str, max_len: int, suffix: str = "...") -> str:
		if len(s) <= max_len:
			return s
		else:
			return s[:max_len - len(suffix)] + suffix

# ---------------------------------------------------------------------------
# Initialization and context rendering
# ---------------------------------------------------------------------------

	def render_init(self, args: argparse.Namespace, result: bool) -> None:
		"""Render a message indicating that the Kanban system has been initialized."""
		if result:
			self._emit(args, "Kanban system initialized successfully.")
		else:
			self._emit(args, "Failed to initialize Kanban system.")


	def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
		"""Render a message indicating the new current context path, or that the context was cleared."""
		board = result.board
		
		if board:
			self._emit(args, f"Current context: {board}")
			return

		self._emit(args, "Current context cleared")

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		"""Render a list of boards, optionally with their column counts"""
		if args.slugs:
			self.render_board_list_slug_only(args, result)
		else:
			self.render_board_list_rich(args, result)

	def render_board_list_slug_only(self, args: argparse.Namespace, result: list[Board]) -> None:
		"""Render a simple list of board slugs, without additional details."""
		if not result:
			return

		slugs = [board.slug for board in result]
		
		# TODO: From this point below shares logic with render_task_list_slug_only, 
		# 		consider refactoring to a shared helper function

		if any(len(slug) > 16 for slug in slugs):
			self._emit(args, "\n".join(slugs))
			return

		term_width, _ = shutil.get_terminal_size(fallback=(80, 24))
		col_width = 16
		gap = 1
		cols = max(1, (term_width + gap) // (col_width + gap))

		formatted = [f"{self._clamped(slug, col_width):<{col_width}}" for slug in slugs]
		lines = []
		for i in range(0, len(formatted), cols):
			row = formatted[i:i + cols]
			lines.append(" ".join(row).rstrip())

		self._emit(args, "\n".join(lines))

	def render_board_list_rich(self, args: argparse.Namespace, result: list[Board]) -> None:
		"""Render a detailed list of boards, including their column counts."""
		items = []

		heading =   [f"{"Name":<32}", f"{"Columns":<16}", f"{"Tasks":<16}"]
		underline = [f"{"----":<32}", f"{"-------":<16}", f"{"-----":<16}"]

		items.append("".join(heading))
		items.append("".join(underline))

		for board in result:
			elems = [
				f"{self._clamped(board.name, 32-1):<32}",
				f"{self._clamped(str(board.column_count), 16-1):<16}",
				f"{self._clamped(str(board.task_count), 16-1):<16}"
			]
			items.append("".join(elems))

		self._emit(args, "\n".join(items))

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was created, including its name."""
		board_name = result.name or args.board
		board_slug = result.slug or args.board
		self._emit(args, f"Created board: {board_name} ({board_slug})")

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		"""Render detailed information for a single board."""
		self.render_board_list_rich(args, [result])

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was renamed, including the old and new names."""
		old_name = args.path
		new_name = result.name or args.new_name
		new_slug = result.slug or args.new_name
		self._emit(args, f"Renamed board: {old_name} -> {new_name} ({new_slug})")

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was deleted, including its name."""
		self._emit(args, f"Deleted board: {result.name} ({result.slug})")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""Render a list of columns, optionally with their board names and positions"""
		if args.slugs:
			self.render_column_list_slug_only(args, result)
		else:
			self.render_column_list_rich(args, result)

	def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
		"""Render detailed information for a single column."""
		self.render_column_list_rich(args, [result])

	def render_column_list_slug_only(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""
		Render a simple list of column slugs, without additional details. 
		If any slugs are longer than 16 characters, render one per line. 
		Otherwise, render in a compact multi-column format.
		"""
		if not result:
			return
		slugs = [column.slug for column in result]

		# TODO: From this point below shares logic with render_task_list_slug_only, 
		# 		consider refactoring to a shared helper function

		if any(len(slug) > 16 for slug in slugs):
			self._emit(args, "\n".join(slugs))
			return

		term_width, _ = shutil.get_terminal_size(fallback=(80, 24))
		col_width = 16
		gap = 1
		cols = max(1, (term_width + gap) // (col_width + gap))

		formatted = [f"{self._clamped(slug, col_width):<{col_width}}" for slug in slugs]
		lines = []
		for i in range(0, len(formatted), cols):
			row = formatted[i:i + cols]
			lines.append(" ".join(row).rstrip())

		self._emit(args, "\n".join(lines))

	def render_column_list_rich(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""Render a detailed list of columns, including their board names and positions."""
		items = []

		heading =  [  f"{"Name":<32}", f"{"Tasks":<16}"]
		uderline = [  f"{"----":<32}", f"{"-----":<16}"]

		items.append("".join(heading))
		items.append("".join(uderline))

		for column in result:
			elems = [
				f"{self._clamped(column.name, 32-1):<32}",
				f"{self._clamped(str(column.task_count), 16-1):<16}",
				]
			items.append("".join(elems))
		
		self._emit(args, "\n".join(items))

	def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
		"""
		Render a message indicating that a column was created, 
		including its name and optionally its board if available.
		"""
		board_name = result.board
		column_name = result.name
		column_slug = result.slug
		
		self._emit(args, f"Column created: {column_name} ({column_slug})")

	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		"""
		Render a message indicating that a column was renamed, including the old and new names,
		and optionally the board if available.
		"""
		path = self._path_from_args(args)
		parts = path.parts
		board_name = result.board or (parts[0] if len(parts) > 0 else None)
		old_name = parts[1] if len(parts) > 1 else (parts[0] if len(parts) > 0 else "")
		new_name = result.name or args.new_name
		new_slug = result.slug or args.new_slug

		self._emit(args, f"Column renamed: {old_name} -> {new_name} ({new_slug})")

	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""
		Render a message indicating that a column was reordered, including its name and new position,
		and optionally the board if available.
		"""
		path = args.column
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		position = args.position
		target = f"{board_name}/{column_name}" if board_name else column_name

		if isinstance(position, int):
			self._emit(args, f"Column reordered: {target} -> position {position + 1}")
		else:
			self._emit(args, f"Column reordered: {target}")

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		"""
		Render a message indicating that a column was deleted,
		including its name and optionally its board if available.
		"""
		self._emit(args, f"Column deleted: {result.name} ({result.slug})")

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		"""Render a list of tasks, optionally with their slugs, titles, and locations."""
		if args.slugs:
			self.render_task_list_slug_only(args, result)
		else:
			self.render_task_list_rich(args, result)


	def render_task_list_slug_only(self, args: argparse.Namespace, result: list[Task]) -> None:
		"""
		Render a simple list of task slugs, without additional details. 
		If any slugs are longer than 16 characters, render one per line. 
		Otherwise, render in a compact multi-column format.
		"""
		if not result:
			return
		
		slugs = [task.slug for task in result]

		if any(len(slug) > 16 for slug in slugs):
			self._emit(args, "\n".join(slugs))
			return

		term_width, _ = shutil.get_terminal_size(fallback=(80, 24))
		col_width = 16
		gap = 1
		cols = max(1, (term_width + gap) // (col_width + gap))

		formatted = [f"{self._clamped(slug, col_width):<{col_width}}" for slug in slugs]
		lines = []
		for i in range(0, len(formatted), cols):
			row = formatted[i:i + cols]
			lines.append(" ".join(row).rstrip())

		self._emit(args, "\n".join(lines))


	def render_task_list_rich(self, args: argparse.Namespace, result: list[Task]) -> None:
		"""Render a detailed list of tasks, including their slugs, titles, and locations."""
		items = []

		# date_format = "%Y-%m-%d"
        # date_format = "%B %d"
		# isoformat()

		width, height = shutil.get_terminal_size(fallback=(80, 24))
		include_tags = width > 80
		include_column = width > 96

		heading =  [f"{"Title":<32}", f"{"Assigned To":<16}", f"{"Priority":<16}", f"{"Due":<16}"]
		uderline = [f"{"-----":<32}", f"{"-----------":<16}", f"{"--------":<16}", f"{"---":<16}"]

		if include_tags:
			heading.insert(3,  f"{"Tags":<16}")
			uderline.insert(3, f"{"----":<16}")
		if include_column:
			heading.insert(1,  f"{"Column":<16}")
			uderline.insert(1, f"{"-----":<16}")

		items.append("".join(heading))
		items.append("".join(uderline))

		for task in result:	
			tags = ", ".join(task.tags) if task.tags else None
			column = self.render_helper.column_for_slug(task.column)
			elems = [
				f"{self._clamped(task.title, 32-1):<32}", 
				*(f"{self._clamped(column.name if column else "-", 16-1):<16}" if include_column else []), 
				f"{self._clamped(task.assigned_to or "-", 16-1):<16}", 
				f"{self._clamped(task.priority.capitalize() if task.priority else "-", 16-1):<16}", 
				*(f"{self._clamped(tags or "-", 16-1):<16}" if include_tags else []),
				f"{self._clamped(task.due_date.date().isoformat() if task.due_date else "-", 16-1):<16}"
				]
			items.append("".join(elems))
		
		items.append("")

		items.insert(0, "---------------------")
		items.insert(1, f"Number of tasks: {len(result)}")
		items.insert(2, "---------------------\n")

		self._emit(args, "\n".join(items))

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was created"""
		self._emit(args, f"Created Task: {result.title}")
		self._emit(args, f"Path: {result.path}")

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		"""Render detailed information about a single task, including all metadata and the body/description."""
		
		lines = [
			"---------------------",
			result.title,
			str(result.path),
			"---------------------",
			"",
			f"Slug: {result.slug}",
			f"ID: {result.id}",
			f"Location: /{result.board}/{result.column}" if result.board and result.column else "Location: (unscoped)",
			f"Assigned To: {result.assigned_to or "-"}",
			f"Priority: {result.priority or "-"}",
			f"Due: {result.due_date.date().isoformat() if result.due_date else "-"}",
			f"Tags: {", ".join(result.tags) if result.tags else "-"}",
			f"Created by: {result.created_by or "-"}",
			"---------------------"
			"",
			result.body,
			"---------------------",
		]
		self._emit(args, "\n".join(lines))

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		# """Render a message indicating that a task was opened in the editor."""
		# self._emit(args, f"Task opened in editor: {result.title} ({result.slug})")
		return
	
	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		# """Render a message indicating that a task was updated, including its slug."""
		# self._emit(args, f"Task updated: {result.title} ({result.slug})")
		return

	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		# TODO: get column.name from slug
		if result.column:
			msg = f"{result.title} → {result.column}"
		else:
			msg = f"Moved task: {result.title})"
		self._emit(args, msg)
	
	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		old_slug = str(self._path_from_args(args))
		new_slug = result.slug
		self._emit(args, f"Task renamed: {result.title}: {old_slug} -> {new_slug}")

	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
		result, op = task_op
		if result.column and op in ["top", "bottom"]:
			msg = f"Task moved to {op} in {result.column}"
		elif result.column and op in ["up", "down"]:
			msg = f"Task moved {op} in {result.column}"
		else:
			msg = f"Task reordered: {result.slug} ({op})"
		self._emit(args, msg)

	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was deleted, including its title."""
		self._emit(args, f"Deleted Task: {result.title}")
		self._emit(args, f"Path: {result.path}")

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, f"Task assigned to: {result.assigned_to}")

# ---------------------------------------------------------------------------
# Additional rendering (search, log, status, config)
# ---------------------------------------------------------------------------

	def render_search(self, args: argparse.Namespace, result: list[Task]) -> None:
		"""Render search results the same way `render_task_list` renders a task list."""
		self.render_task_list(args, result)

	def render_log(self, args: argparse.Namespace, result: list[GitCommit]) -> None:
		self._emit(args, result)

	def render_status(self, args: argparse.Namespace, result: KanbanStatus) -> None:
		self._emit(args, result)

	def render_set_config(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	def render_get_config(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
