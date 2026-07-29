"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from pathlib import Path
from functools import wraps
import logging
import shutil
from typing import Any

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown
from rich.table import Table
from rich.text import Text
from rich import box, print

from ..models import UserContext, Board, Column, Slug, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.render_service import RenderService
from ..services.kanban import GitCommit, KanbanStatus

# Box style options:
# https://rich.readthedocs.io/en/stable/appendix/box.html#appendix-box

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

class RichRenderer(CommandRenderer):
	console = Console(color_system="auto")

	def __init__(self, render_service: RenderService):
		self.render_service = render_service

	def _path_from_args(self, args: argparse.Namespace) -> Path:
		"""Return args.path as a Path for display formatting."""
		path = getattr(args, "path", None)
		if isinstance(path, Path):
			return path
		if path is None:
			return Path(".")
		return Path(str(path))

	def _emit(self, args: argparse.Namespace, value: Any) -> None:
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
		board_name = result.name or args.board
		board_slug = result.slug or args.board
		self._emit(args, f"Created: {board_name} ({board_slug})")

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		"""Render detailed information for a single board."""
		self.render_board_list_rich(args, [result])

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was renamed, including the old and new names."""
		old_name = args.path
		new_name = result.name or args.new_name
		new_slug = result.slug or args.new_name
		self._emit(args, f"Renamed: {old_name} → {new_name} ({new_slug})")

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		"""Render a message indicating that a board was deleted, including its name."""
		self._emit(args, f"Deleted: {result.name} ({result.slug})")

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
		
		self._emit(args, f"Created: {column_name} ({column_slug})")

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

		self._emit(args, f"Renamed: {old_name} → {new_name} ({new_slug})")

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
			self._emit(args, f"Reordered: {target} → position {position + 1}")
		else:
			self._emit(args, f"Reordered: {target}")

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		"""
		Render a message indicating that a column was deleted,
		including its name and optionally its board if available.
		"""
		self._emit(args, f"Deleted: {result.name} ({result.slug})")

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
			column = self.column_for_slug(task.column)

			elems = [
				task.title,
				task.assigned_to or "-",
				task.priority.capitalize() if task.priority else "-",
				task.due_date.date().isoformat() if task.due_date else "-",
			]

			if include_tags:
				elems.insert(3, tags)
			if include_column:
				elems.insert(1, column.name if column else "-")

			table.add_row(
				*elems
			)

		self._emit(args, table)

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was created"""
		self._emit(args, f"Created Task: {result.title}")
		self._emit(args, f"Path: {result.path}")

	def render_task_view(self, args: argparse.Namespace, result: Task) -> None:
		"""Render detailed information about a single task, including all metadata and the body/description."""
		self._emit(args, "")
		self.render_task_metadata(args, result)
		self._emit(args, "")

		body: str | Text | KanbanMarkdown = ""

		if not result.body:
			body = ""
		elif args.plain:
			body = Text(result.body)
		else:
			body = KanbanMarkdown(result.body, justify="left")
			
		self._emit(args, body)
		self._emit(args, "")

	def render_task_info(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a task's metadata without its body."""
		self._emit(args, "")
		self.render_task_metadata(args, result)
		self._emit(args, "")

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was opened in the editor."""
		self._emit(args, f"Edited: {result.title} ({result.slug})")
		return
	
	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was updated, including its slug."""
		self._emit(args, "")
		self.render_task_metadata(args, result)
		self._emit(args, "")

	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was moved to a new column."""
		if result.column:
			column = self.column_for_slug(result.column)
			column_name = column.name if column else result.column
			msg = f"Moved: {result.title} → {column_name}"
		else:
			msg = f"Moved: {result.title}"
		self._emit(args, msg)
	
	# TODO: change output
	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was renamed, including the old and new slugs."""
		old_slug = str(self._path_from_args(args))
		new_slug = result.slug
		self._emit(args, f"Renamed: {result.title} ({old_slug} → {new_slug})")

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
		"""Render a message indicating that a task was deleted, including its slug."""
		self._emit(args, f"Deleted: {result.title} ({result.slug})")

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was assigned to a user."""
		self._emit(args, f"Task assigned to: {result.assigned_to}")

	def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a task was tagged, showing its current tags."""
		tags = ", ".join(result.tags) if result.tags else "(none)"
		self._emit(args, f"Task tags: {tags}")

	def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a message indicating that a comment was appended to a task."""
		self._emit(args, f"Comment added to: {result.slug}")

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


# ---------------------------------------------------------------------------
# Utilities and shared behavior for rendering commands
# ---------------------------------------------------------------------------

	def render_task_metadata(self, args: argparse.Namespace, task: Task) -> None:
		"""Render the metadata of a task in a table format."""
		board = self.board_for_slug(task.board)
		column = self.column_for_slug(task.column)

		table = Table(box=box.ASCII2, show_header=False, header_style="bold", title_justify="left")

		table.add_column("", width=12, justify="right", no_wrap=True)
		table.add_column("", width=60, justify="left", no_wrap=False)

		table.add_row("Title", Text(task.title, style="bold"))
		table.add_row("Slug", str(task.slug), end_section=True)
		
		table.add_row("Board", board.name if board else "-")
		table.add_row("Column", column.name if column else "-")
		table.add_row("Assigned To", task.assigned_to or "-")
		table.add_row("Priority", task.priority or "-")
		table.add_row("Due", str(task.due_date.date().isoformat()) if task.due_date else "-")
		table.add_row("Tags", ", ".join(task.tags) if task.tags else "-")
		table.add_row("Created By", task.created_by or "-")

		self._emit(args, table)

	def board_for_slug(self, slug: Slug) -> Board | None:
		"""Given a board slug, return the corresponding board."""
		return self.render_service.board_for_slug(slug)
	
	def column_for_slug(self, slug: Slug) -> Column | None:
		"""Given a column slug, return the corresponding column."""
		return self.render_service.column_for_slug(slug)
	