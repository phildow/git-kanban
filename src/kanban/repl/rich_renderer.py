"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from functools import wraps
import logging
import shutil

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown
from rich.table import Table
from rich.text import Text
from rich import box, print

from ..models import UserContext, Board, Column, Task
from ..repl.render_helper import RenderHelper
from ..services.kanban import GitCommit, KanbanStatus

# Box style options:
# https://rich.readthedocs.io/en/stable/appendix/box.html#appendix-box

def _requires_verbose(method):
	@wraps(method)
	def _wrapped(self, args: argparse.Namespace, result):
		if not getattr(args, "verbose", False):
			return None
		else:
			return method(self, args, result)

	return _wrapped

# Custom Rich Markdown renderer that left-justifies headings instead of centering them.

class LeftJustifiedHeading(Heading):
	def __rich_console__(
		self,
		console: Console,
		options: ConsoleOptions,
	) -> RenderResult:
		"""Render the heading with left justification."""
		yield from console.render(self.text, options=options.update(justify="left"))


class KanbanMarkdown(Markdown):
	elements = {
		**Markdown.elements,
		"heading_open": LeftJustifiedHeading,
	}

# The class responsible for rendering output to the console in a rich format.

class RichRenderer:
	console = Console(color_system="auto")

	def __init__(self, render_helper: RenderHelper):
		self.render_helper = render_helper

	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if value is None:
			return
		self.console.print(value)


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

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		"""Render a list of boards, optionally with their column counts"""
		if getattr(args, "slugs", False):
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
		table = Table(title=f"Boards ({len(result)})", box=box.ASCII2, show_header=True, header_style="bold")

		table.add_column("Name", width=32, no_wrap=True)
		table.add_column("Slug", width=32, no_wrap=True)
		table.add_column("Columns", width=8, no_wrap=True)
		table.add_column("Tasks", width=8, no_wrap=True)

		for board in result:
			table.add_row(board.name, board.slug, str(board.column_count), str(board.task_count))

		self._emit(args, table)

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was created, including its name."""
		board_name = result.name or getattr(args, "board", None)
		board_slug = result.slug or getattr(args, "board", None)
		self._emit(args, f"Created board: {board_name} ({board_slug})")

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was renamed, including the old and new names."""
		old_name = getattr(args, "board", None)
		new_name = result.name or getattr(args, "new_name", None)
		new_slug = result.slug or getattr(args, "new_name", None)
		self._emit(args, f"Renamed board: {old_name} -> {new_name} ({new_slug})")

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was deleted, including its name."""
		self._emit(args, f"Deleted board: {result.name} ({result.slug})")

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		"""Render a list of columns, optionally with their board names and positions"""
		if getattr(args, "slugs", False):
			self.render_column_list_slug_only(args, result)
		else:
			self.render_column_list_rich(args, result)

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
		table = Table(title=f"Columns ({len(result)})", box=box.ASCII2, show_header=True, header_style="bold")

		table.add_column("Name", width=32, no_wrap=True)
		table.add_column("Slug", width=32, no_wrap=True)
		table.add_column("Tasks", width=8, no_wrap=True)

		for column in result:
			table.add_row(column.name, column.slug, str(column.task_count))
		
		self._emit(args, table)

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
		path = getattr(args, "path", "") or ""
		old_name = path.split("/", 1)[1] if "/" in path else path
		board_name = result.board or (path.split("/", 1)[0] if "/" in path else None)
		new_name = result.name or getattr(args, "new_name", None)
		new_slug = result.slug or getattr(args, "new_slug", None)

		self._emit(args, f"Column renamed: {old_name} -> {new_name} ({new_slug})")

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
		if getattr(args, "slugs", False):
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
		# date_format = "%Y-%m-%d"
		# date_format = "%B %d"
		# date().isoformat()

		width, height = shutil.get_terminal_size(fallback=(80, 24))
		include_tags = width > 80
		include_column = width > 96

		table = Table(title=f"Tasks ({len(result)})", box=box.ASCII2, show_header=True, header_style="bold")

		table.add_column("Title", width=40, no_wrap=True)
		
		if include_column:
			table.add_column("Column", width=16, no_wrap=True)

		table.add_column("Assigned To", width=16, no_wrap=True)
		table.add_column("Priority", width=12, no_wrap=True)

		if include_tags:
			table.add_column("Tags", width=16, no_wrap=True)

		table.add_column("Due", width=12, no_wrap=True)

		for task in result:
			tags = ", ".join(task.tags) if task.tags else "-"
			column_name = self.render_helper.column_name_from_slug(task.board, task.column) or "-"

			elems = [
				task.title,
				task.assigned_to or "-",
				task.priority.capitalize() if task.priority else "-",
				task.due_date.date().isoformat() if task.due_date else "-",
			]

			if include_tags:
				elems.insert(3, tags)
			if include_column:
				elems.insert(1, column_name)

			table.add_row(
				*elems
			)

		self._emit(args, table)

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		"""
		Render a message indicating that a task was created, 
		including its slug and optionally its board/column if available.
		"""
		
		self._emit(args, f"Task created: {result.title} ({result.slug})")

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		"""Render detailed information about a single task, including all metadata and the body/description."""
		
		self._emit(args, "")
		self._emit(args, Text(result.title, style="bold underline"))

		table = Table(box=box.ASCII2, show_header=False, header_style="bold", title_justify="left")

		# table.add_column("Title", width=12, justify="right", no_wrap=True)
		# table.add_column(result.title, width=40, justify="left", no_wrap=False)

		table.add_column("", width=12, justify="right", no_wrap=True)
		table.add_column("", width=40, justify="left", no_wrap=False)

		table.add_row("Slug", result.slug)
		table.add_row("ID", str(result.id))
		table.add_row("Location", f"/{result.board}/{result.column}")
		table.add_row("Assigned To", result.assigned_to or "-")
		table.add_row("Priority", result.priority or "-")
		table.add_row("Due", str(result.due_date.date().isoformat()) if result.due_date else "-")
		table.add_row("Tags", ", ".join(result.tags) if result.tags else "-")
		table.add_row("Created By", result.created_by or "-")

		self._emit(args, "")
		self._emit(args, table)
		self._emit(args, "")
		if not result.body:
			body = ""
		elif getattr(args, "plain", False):
			body = Text(result.body)
		else:
			body = KanbanMarkdown(result.body, justify="left")
		self._emit(args, body)
		self._emit(args, "")

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
			msg = f"{result.title} moved to: {result.column}"
		else:
			msg = f"Moved task: {result.title})"
		self._emit(args, msg)
	
	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		old_slug = getattr(args, "path", "") or ""
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
		self._emit(args, f"Task deleted: {result.title} ({result.slug})")

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

	def render_config_set(self, args: argparse.Namespace, result: None) -> None:
		self._emit(args, result)

	def render_config_get(self, args: argparse.Namespace, result: str) -> None:
		self._emit(args, result)
