"""CLI rendering helpers."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console, ConsoleOptions, RenderResult
from rich.markdown import Heading, Markdown
from rich.text import Text

from ..models import Board, Column, ReorderOp, Slug, Task, UserContext
from ..protocols.command_renderer import CommandRenderer, ObjectField, field_value
from ..services.kanban import GitCommit, KanbanStatus
from ..services.render_service import RenderService

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

class Renderer(CommandRenderer):
	def __init__(self, render_service: RenderService) -> None:
		self.render_service = render_service
		# rich
		self.console = Console(color_system="auto", highlight=False)

	def _path_from_args(self, args: argparse.Namespace) -> Path:
		"""Return args.path as a Path for display formatting."""
		path = getattr(args, "path", None)
		if isinstance(path, Path):
			return path
		if path is None:
			return Path("/")
		return Path(str(path))

	def _emit(self, args: argparse.Namespace, value: object) -> None:
		if value is None or self._silent:
			return
		# rich
		self.console.print(value, highlight=False)
		# print(value)

# ---------------------------------------------------------------------------
# Initialization and context rendering
# ---------------------------------------------------------------------------

	def render_init(self, args: argparse.Namespace, result: bool) -> None:
		if result:
			self._emit(args, "Kanban system initialized successfully. See KANBAN.md for more info or get started with `kanban tui`.")
		else:
			self._emit(args, "Failed to initialize Kanban system.")

	def render_set_board(self, args: argparse.Namespace, result: UserContext) -> None:
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
		if not result:
			self._emit(args, "Unable to determine board for reordered columns.")
			return
		board = self.board_for_slug(result[0].board)
		self.render_board(args, board)

	def render_column_delete(self, args: argparse.Namespace, result: Column) -> None:
		self._emit(args, Text("Deleted: ") + Text(result.name, style="bold"))
		self._emit(args, f"Path: {result.path}")

# ---------------------------------------------------------------------------
# Task rendering
# ---------------------------------------------------------------------------

	def render_task(self, args: argparse.Namespace, task: Task, spacing: int = 4) -> None:
		column = self.column_for_path(task.path.parent)
		board = self.board_for_slug(task.board)
		self._emit(args, Text("Title: ") + Text(task.title, style="bold"))
		lines = [
			f"Path: {task.path}",
			f"",
			f"{' ' * spacing}Board: {board.name}",
			f"{' ' * spacing}Column: {column.name}",
			f"{' ' * spacing}Assigned To: {task.assigned_to or '-'}",
			f"{' ' * spacing}Priority: {task.priority or '-'}",
			f"{' ' * spacing}Due: {task.due_date.date().isoformat() if task.due_date else '-'}",
			f"{' ' * spacing}Tags: {', '.join(task.tags) if task.tags else '-'}",
			f"{' ' * spacing}Created by: {task.created_by or '-'}",
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
		if args.description:
			setattr(args, "markdown", False)
			self.render_task_view(args, result)
		else:
			self.render_task(args, result)

	def render_task_view(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a task's metadata followed by its body."""
		self.render_task(args, result)

		body: str | Text | KanbanMarkdown = ""

		if not result.body:
			body = ""
		elif args.markdown:
			body = KanbanMarkdown(result.body, justify="left")
		else:
			body = Text(result.body)
			
		self._emit(args, "")
		self._emit(args, body)

	def render_task_info(self, args: argparse.Namespace, result: Task) -> None:
		"""Render a task's metadata without its body."""
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

	def render_task_reorder(self, args: argparse.Namespace, task_op: tuple[Task, ReorderOp]) -> None:
		result, _op = task_op
		self.render_task(args, result)

	def render_task_delete(self, args: argparse.Namespace, result: Task) -> None:
		self._emit(args, Text("Deleted: ") + Text(result.title, style="bold"))
		self._emit(args, f"Path: {result.path}")

	def render_task_assign(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_tag(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

	def render_task_comment(self, args: argparse.Namespace, result: Task) -> None:
		self.render_task(args, result)

# ---------------------------------------------------------------------------
# Additional rendering (search, log, status, config)
# ---------------------------------------------------------------------------

	def render_fields(self, args: argparse.Namespace, result: Board | Column | Task, fields: tuple[ObjectField, ...]) -> None:
		"""Print the named fields of a board, column, or task, one to a line."""
		for field in fields:
			self._emit(args, field_value(result, field))

	def render_fields_list(self, args: argparse.Namespace, result: Sequence[Board | Column | Task], fields: tuple[ObjectField, ...]) -> None:
		"""Print the named fields of every object in a list, one to a line."""
		for obj in result:
			self.render_fields(args, obj, fields)

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

	def render_set_config(self, args: argparse.Namespace, result: str | None) -> None:
		# TODO: implement
		self._emit(args, result)

	def render_get_config(self, args: argparse.Namespace, result: str | None) -> None:
		# TODO: implement
		self._emit(args, result)

	def render_list_config(self, args: argparse.Namespace, result: dict[str, str | None]) -> None:
		"""Print every supported key and its value, one per line, unset keys included."""
		if not result:
			self._emit(args, "No configuration keys")
			return

		for key, value in result.items():
			self._emit(args, Text(f"{key} = ") + Text(value or "", style="bold"))

# ---------------------------------------------------------------------------
# Utilities and shared behavior for rendering commands
# ---------------------------------------------------------------------------

	def board_for_slug(self, slug: Slug) -> Board:
		"""Given a board slug, return the corresponding board."""
		return self.render_service.board_for_slug(slug)
	
	def column_for_path(self, path: Path) -> Column:
		"""Given a column path, return the corresponding column."""
		return self.render_service.column_for_path(path)