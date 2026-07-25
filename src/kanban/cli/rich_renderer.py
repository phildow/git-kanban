"""Rich rendering helpers for the kanban CLI.

The `RichRenderer` uses the `rich` library to emit output to the terminal.
Behaviour currently mirrors the plain `Renderer`: each write emits the path
of the affected object. Info/show/list methods and the additional rendering
category (search, log, status, config) will grow richer formatting later.
"""

# CURRENTLY UNUSED: The rich renderer is not currently used in the CLI, but is
# available for future use. The CLI currently uses the plain `Renderer` class.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown
from rich.table import Table
from rich.text import Text
from rich import box

from ..models import Board, Column, Slug, Task
from ..protocols.command_renderer import CommandRenderer
from ..services.kanban import GitCommit, KanbanStatus
from ..utils.render_helper import RenderHelper

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

class RichRenderer(CommandRenderer):
	"""CLI renderer that uses the `rich` library for output."""

	def __init__(self, render_helper: RenderHelper) -> None:
		self.render_helper = render_helper
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
		self.console.print(value)

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
		raise NotImplementedError("Change directory is not supported by the CLI rich renderer. Use the `cd` command in the REPL instead.")

# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

	def render_board_list(self, args: argparse.Namespace, result: list[Board]) -> None:
		if not result:
			self._emit(args, "No boards")
			return
		
		"""Render a detailed list of boards, including their column counts."""
		table = Table(title="", box=box.ASCII2, show_header=True, header_style="bold")

		table.add_column("Name", width=32, no_wrap=True)
		table.add_column("Path", width=32, no_wrap=True)
		table.add_column("Columns", width=8, no_wrap=True)
		table.add_column("Tasks", width=8, no_wrap=True)

		for board in result:
			table.add_row(board.name, str(board.path), str(board.column_count), str(board.task_count))

		self._emit(args, table)

	def render_board_create(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board_list(args, [result])

	def render_board_info(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board_list(args, [result])

	def render_board_rename(self, args: argparse.Namespace, result: Board) -> None:
		self.render_board_list(args, [result])

	def render_board_delete(self, args: argparse.Namespace, result: Board) -> None:
		board_name = result.name
		
		table = Table(title="", box=box.ASCII2, show_header=False, header_style="bold")
		
		table.add_column("Label", width=16, no_wrap=True, justify="right")
		table.add_column("Value", width=32, no_wrap=True)
		
		table.add_row("Deleted Board", board_name)
		table.add_row("Path", str(result.path))

		self._emit(args, table)

# ---------------------------------------------------------------------------
# Column rendering
# ---------------------------------------------------------------------------

	def render_column_list(self, args: argparse.Namespace, result: list[Column]) -> None:
		if not result:
			self._emit(args, "No columns")
			return
		
		table = Table(title="", box=box.ASCII2, show_header=True, header_style="bold")

		table.add_column("Name", width=32, no_wrap=True)
		table.add_column("Path", width=32, no_wrap=True)
		table.add_column("Tasks", width=8, no_wrap=True)

		for column in result:
			table.add_row(column.name, str(column.path), str(column.task_count))
		
		self._emit(args, table)

	def render_column_info(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, str(result.path))

	def render_column_create(self, args: argparse.Namespace, result: Column) -> None:
		self.render_column_list(args, [result])

	def render_column_rename(self, args: argparse.Namespace, result: Column) -> None:
		self.render_column_list(args, [result])

	def render_column_reorder(self, args: argparse.Namespace, result: list[Column]) -> None:
		board = self.board_for_slug(result[0].board) if result else None
		if board is None:
			self._emit(args, "No columns")
			return
		self.render_board_list(args, [board])

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		column_name = result.name
		
		table = Table(title="", box=box.ASCII2, show_header=False, header_style="bold")
		
		table.add_column("Label", width=16, no_wrap=True, justify="right")
		table.add_column("Value", width=32, no_wrap=True)
		
		table.add_row("Deleted Column", column_name)
		table.add_row("Path", str(result.path))

		self._emit(args, table)

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_tasks_slim_table(self, args: argparse.Namespace, result: list[Task]) -> None:
		width, height = shutil.get_terminal_size(fallback=(80, 24))
		include_tags = width > 80
		include_column = width > 96

		table = Table(title="", box=box.ASCII2, show_header=True, header_style="bold")

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
			column = self.column_for_path(task.path.parent)

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

	def render_tasks_table(self, args: argparse.Namespace, result: list[Task]) -> None:
		table = Table(title="", box=box.ASCII2, show_header=False, header_style="bold")

		table.add_column("", width=12, justify="right", no_wrap=True)
		table.add_column("", width=60, justify="left", no_wrap=False)

		for task in result:
			column = self.column_for_path(task.path.parent)
			board = self.board_for_slug(task.board)

			table.add_row("Title", Text(task.title, style="bold"))
			table.add_row("Path", str(task.path), end_section=True)
			
			table.add_row("Board", board.name if board else "-")
			table.add_row("Column", column.name if column else "-")
			table.add_row("Assigned To", task.assigned_to or "-")
			table.add_row("Priority", task.priority or "-")
			table.add_row("Due", str(task.due_date.date().isoformat()) if task.due_date else "-")
			table.add_row("Tags", ", ".join(task.tags) if task.tags else "-")
			table.add_row("Created By", task.created_by or "-", end_section=True)

		self._emit(args, table)

	def render_tasks_cards(self, args: argparse.Namespace, result: list[Task]) -> None:
		self._emit(args, "")

		for task in result:
			column = self.column_for_path(task.path.parent)
			board = self.board_for_slug(task.board)

			table = Table(title="", box=box.ASCII2, show_header=False, header_style="bold")

			table.add_column("", width=12, justify="right", no_wrap=True)
			table.add_column("", width=60, justify="left", no_wrap=False)

			table.add_row("Title", Text(task.title, style="bold"))
			table.add_row("Path", str(task.path), end_section=True)
			
			table.add_row("Board", board.name if board else "-")
			table.add_row("Column", column.name if column else "-")
			table.add_row("Assigned To", task.assigned_to or "-")
			table.add_row("Priority", task.priority or "-")
			table.add_row("Due", str(task.due_date.date().isoformat()) if task.due_date else "-")
			table.add_row("Tags", ", ".join(task.tags) if task.tags else "-")
			table.add_row("Created By", task.created_by or "-")

			self._emit(args, table)
			self._emit(args, "")

	def render_task_list(self, args: argparse.Namespace, result: list[Task]) -> None:
		if not result:
			self._emit(args, "No tasks")
			return
		
		# date_format = "%Y-%m-%d"
		# date_format = "%B %d"
		# date().isoformat()

		if args.cards:
			self.render_tasks_cards(args, result)
		else:
			self.render_tasks_slim_table(args, result)

	def render_task_create(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_show(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, "")
		self._emit(args, Text(result.title, style="bold"))
		self._emit(args, "")
		self.render_task_metadata(args, result)
		self._emit(args, "")

		body: str | Text | KanbanMarkdown = ""

		if not result.body:
			body = ""
		# elif args.plain:
		# 	body = Text(result.body)
		else:
			body = KanbanMarkdown(result.body, justify="left")
			
		self._emit(args, body)

	def render_task_rename(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_metadata(args, result)

	def render_task_edit(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_update(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_metadata(args, result)

	def render_task_move(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_metadata(args, result)

	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, str]) -> None:
		result, _op = task_op
		self._emit(args, str(result.path))

	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, str(result.path))

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task_metadata(args, result)

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
		board = self.board_for_slug(task.board)
		column = self.column_for_path(task.path.parent	)

		table = Table(box=box.ASCII2, show_header=False, header_style="bold", title_justify="left")

		table.add_column("", width=12, justify="right", no_wrap=True)
		table.add_column("", width=60, justify="left", no_wrap=False)

		table.add_row("Path", str(task.path), end_section=True)
		
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
		return self.render_helper.board_for_slug(slug)
	
	def column_for_path(self, path: Path) -> Column | None:
		"""Given a column path, return the corresponding column."""
		return self.render_helper.column_for_path(path)