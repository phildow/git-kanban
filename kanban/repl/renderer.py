"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from functools import wraps
import re
import shutil
from unittest import result

from models import UserContext, Board, Column, Task
from services.kanban import GitCommit, KanbanStatus

def _requires_verbose(method):
	@wraps(method)
	def _wrapped(self, args: argparse.Namespace, result):
		if not getattr(args, "verbose", False):
			return None
		else:
			return method(self, args, result)

	return _wrapped

class Renderer:
	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if getattr(args, "quiet", False):
			return
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

	@_requires_verbose
	def render_change_dir(self, args: argparse.Namespace, result: UserContext) -> None:
		"""Render a message indicating the new current context path, or that the context was cleared."""
		board = result.board
		column = result.column
		
		if board and column:
			self._emit(args, f"Current context: {board}/{column}")
			return
		if board:
			self._emit(args, f"Current context: {board}")
			return

		self._emit(args, "Current context cleared")
	
	@_requires_verbose
	def render_change_board(self, args: argparse.Namespace, result: UserContext) -> None:
		"""Render a message indicating the new current board, or that the board context was cleared."""
		board = result.board
		if board:
			self._emit(args, f"Changed board to: {board}")
		else:
			self._emit(args, "Board cleared")

	@_requires_verbose
	def render_change_column(self, args: argparse.Namespace, result: UserContext) -> None:
		"""Render a message indicating the new current column, or that the column context was cleared."""
		column = result.column
		if column:
			self._emit(args, f"Changed column to: {column}")
		else:
			self._emit(args, "Column cleared")

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		"""Render a list of boards, optionally with their column counts"""
		if args.list == True:
			self.render_board_list_verbose(args, result)
		else:
			self.render_board_list_slug_only(args, result) 
			
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

	def render_board_list_verbose(self, args: argparse.Namespace, result: list[Board]) -> None:
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
		board_name = result.name or getattr(args, "board", None)
		self._emit(args, f"Created board: {board_name}")

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was renamed, including the old and new names."""
		old_name = getattr(args, "board", None)
		new_name = result.name or getattr(args, "new_name", None)
		self._emit(args, f"Renamed board: {old_name} -> {new_name}")

	def render_board_delete(self, args: argparse.Namespace) -> None:
		"""Render a message indicating that a board was deleted, including its name."""
		board_name = getattr(args, "board", None)
		self._emit(args, f"Deleted board: {board_name}")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""Render a list of columns, optionally with their board names and positions"""
		if args.list == True:
			self.render_column_list_verbose(args, result)
		else:
			self.render_column_list_slug_only(args, result)

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

	def render_column_list_verbose(self, args: argparse.Namespace, result: list[Column]) -> None:
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
		if board_name and column_name:
			self._emit(args, f"Column created: {board_name}/{column_name}")
		else:
			self._emit(args, f"Column created: {column_name}")

	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		"""
		Render a message indicating that a column was renamed, including the old and new names,
		and optionally the board if available.
		"""
		path = getattr(args, "path", "") or ""
		old_name = path.split("/", 1)[1] if "/" in path else path
		board_name = result.board or (path.split("/", 1)[0] if "/" in path else None)
		new_name = result.name or getattr(args, "new_name", None)

		if board_name:
			self._emit(args, f"Column renamed: {board_name}/{old_name} -> {board_name}/{new_name}")
		else:
			self._emit(args, f"Column renamed: {old_name} -> {new_name}")

	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""
		Render a message indicating that a column was reordered, including its name and new position,
		and optionally the board if available.
		"""
		path = getattr(args, "path", "") or ""
		column_name = path.split("/", 1)[1] if "/" in path else path
		board_name = path.split("/", 1)[0] if "/" in path else None
		position = getattr(args, "position", None)
		target = f"{board_name}/{column_name}" if board_name else column_name

		if isinstance(position, int):
			self._emit(args, f"Column reordered: {target} -> position {position + 1}")
		else:
			self._emit(args, f"Column reordered: {target}")

	def render_column_delete(self, args: argparse.Namespace) -> None:
		"""
		Render a message indicating that a column was deleted, 
		including its name and optionally its board if available.
		"""
		path = getattr(args, "path", "") or ""
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
		"""Render a list of tasks, optionally with their slugs, titles, and locations."""
		if args.list == True:
			self.render_task_list_verbose(args, result)
		else:
			self.render_task_list_slug_only(args, result)


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


	def render_task_list_verbose(self, args: argparse.Namespace, result: list[Task]) -> None:
		"""Render a detailed list of tasks, including their slugs, titles, and locations."""
		items = []

		# date_format = "%Y-%m-%d"
        # date_format = "%B %d"
		# isoformat()

		width, height = shutil.get_terminal_size(fallback=(80, 24))
		include_tags = width > 80
		include_board = width > 96

		heading =  [f"{"Title":<32}", f"{"Assigned To":<16}", f"{"Priority":<16}", f"{"Due":<16}"]
		uderline = [f"{"-----":<32}", f"{"-----------":<16}", f"{"--------":<16}", f"{"---":<16}"]

		if include_tags:
			heading.insert(3,  f"{"Tags":<16}")
			uderline.insert(3, f"{"----":<16}")
		if include_board:
			heading.insert(1,  f"{"Column":<16}")
			uderline.insert(1, f"{"-----":<16}")

		items.append("".join(heading))
		items.append("".join(uderline))

		for task in result:	
			tags = ", ".join(task.tags) if task.tags else None
			elems = [
				f"{self._clamped(task.title, 32-1):<32}", 
				*(f"{self._clamped(task.column or "-", 16-1):<16}" if include_board else []), 
				f"{self._clamped(task.assignee or "-", 16-1):<16}", 
				f"{self._clamped(task.priority or "-", 16-1):<16}", 
				*(f"{self._clamped(tags or "-", 16-1):<16}" if include_tags else []),
				f"{self._clamped(task.due_date.isoformat() if task.due_date else "-", 16-1):<16}"
				]
			items.append("".join(elems))
		
		items.append("")

		items.insert(0, "---------------------")
		items.insert(1, f"Number of tasks: {len(result)}")
		items.insert(2, "---------------------\n")

		self._emit(args, "\n".join(items))

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		"""
		Render a message indicating that a task was created, 
		including its slug and optionally its board/column if available.
		"""
		# TODO: Consider more detailed output for verbose mode, and a more concise message for non-verbose
		# TODO: Reconsider whether board/column should be Optional
		if result.board and result.column:
			self._emit(args, f"Task created: {result.board}/{result.column}/{result.slug}")
		else:
			self._emit(args, f"Task created: {result.slug}")

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		"""Render detailed information about a single task, including all metadata and the body/description."""
		
		lines = [
			"---------------------",
			result.title,
			"---------------------"
			"",
			f"Slug: {result.slug}",
			f"ID: {result.id}",
			f"Location: /{result.board}/{result.column}" if result.board and result.column else "Location: (unscoped)",
			f"Assignee: {result.assignee or "-"}",
			f"Priority: {result.priority or "-"}",
			f"Due: {result.due_date.isoformat() if result.due_date else "-"}",
			f"Tags: {", ".join(result.tags) if result.tags else "-"}",
			f"Created by: {result.created_by or "-"}",
			"---------------------"
			"",
			result.body,
			"---------------------",
		]
		self._emit(args, "\n".join(lines))

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, result)

	def render_task_move(self, args: argparse.Namespace, task: Task) -> None:
		if task.board and task.column:
			msg = f"Task moved to: {task.board}/{task.column}/{task.slug}"
		else:
			msg = f"Task moved: {task.slug}"
		self._emit(args, msg)
	
	def render_task_delete(self, args: argparse.Namespace) -> None:
		path = getattr(args, "path", None)
		if path:
			self._emit(args, f"Task deleted: {path}")
		else:
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

	def render_config_set(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	def render_config_get(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
