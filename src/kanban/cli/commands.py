"""
Subcommand handlers for the kanban CLI.

Command handlers do not query user context, working board or column, or the repository directly.  
They delegate to the KanbanService.

Command handlers do not render output directly.  They delegate to a renderer, 
which is responsible for formatting and printing the output.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

from ..storage.seeds import BOOTSTRAP_CONFIG
from ..models import ReorderOp, Slug, TaskFilter
from ..protocols.command_renderer import CommandRenderer
from ..utils.field_renderer import for_fields
from ..utils.args import parse_priority
from ..utils.str import parse_destination
from ..services.kanban import KanbanService, TaskCreateParams, TaskUnsetParams, TaskUpdateParams


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def with_absolute_path(method):
	"""Decorator to rewrite the path to an absolute path"""
	@wraps(method)
	def _wrapped(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
		"""Normalize args.path to an absolute Path for decorated handlers."""
		path = args.path

		if path is not None:
			if isinstance(path, str):
				path = Path(path if path.startswith("/") else f"/{path}")
			elif isinstance(path, Path) and not path.is_absolute():
				path = Path("/") / path
			setattr(args, "path", path)

		return method(args, svc, renderer, json_renderer)

	return _wrapped

def _pick(args: argparse.Namespace, renderer: CommandRenderer, json_renderer: CommandRenderer) -> CommandRenderer:
    """
    Return the renderer the arguments call for.

    --format chooses between the plain and JSON renderers, and --path or --id
    puts a FieldRenderer in front of whichever was chosen, so the command
    reports those fields alone in that renderer's own form.
    """
    base = json_renderer if args.format == "json" else renderer
    return for_fields(args, base)


# ---------------------------------------------------------------------------
# Initialization commands
# ---------------------------------------------------------------------------

def handle_init(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	config = BOOTSTRAP_CONFIG if args.bootstrap else None
	result = svc.initialize_kanban(config=config)
	_pick(args, renderer, json_renderer).render_init(args, result)

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_boards()
	_pick(args, renderer, json_renderer).render_board_list(args, result)


def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.create_board(args.board)
	_pick(args, renderer, json_renderer).render_board_create(args, result)


@with_absolute_path
def handle_board_info(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_board(args.path)
	_pick(args, renderer, json_renderer).render_board_info(args, result)


@with_absolute_path
def handle_board_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.rename_board(args.path, args.new_name)
	_pick(args, renderer, json_renderer).render_board_rename(args, result)


@with_absolute_path
def handle_board_delete(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if not args.force and not svc.interaction.confirm(f"Delete board {args.path}?"):
		return
	result = svc.delete_board(args.path)
	_pick(args, renderer, json_renderer).render_board_delete(args, result)

# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

@with_absolute_path
def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_columns(args.path)
	_pick(args, renderer, json_renderer).render_column_list(args, result)


@with_absolute_path
def handle_column_info(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_column(args.path)
	_pick(args, renderer, json_renderer).render_column_info(args, result)


@with_absolute_path
def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.create_column(args.path, args.title)
	_pick(args, renderer, json_renderer).render_column_create(args, result)


@with_absolute_path
def handle_column_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.rename_column(args.path, args.new_name)
	_pick(args, renderer, json_renderer).render_column_rename(args, result)


@with_absolute_path
def handle_column_reorder(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.reorder_column(args.path, args.position)
	_pick(args, renderer, json_renderer).render_column_reorder(args, result)


@with_absolute_path
def handle_column_delete(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if not args.force and not svc.interaction.confirm(f"Delete column '{args.path}'?"):
		return
	result = svc.delete_column(args.path)
	_pick(args, renderer, json_renderer).render_column_delete(args, result)

# -----------------------------------get_tasks----------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

# TODO: REMOVE duplicate (in command_helpers.py)
def build_task_filter(args: argparse.Namespace) -> TaskFilter:
	"""Build a TaskFilter from parsed CLI/REPL filter arguments."""
	def _parse_date(s: str | None) -> datetime | None:
		return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

	return TaskFilter(
		assigned_to=args.assigned_to,
		priority=parse_priority(args),
		tags=args.tags or [],
		due_before=_parse_date(args.due_before),
		due_after=_parse_date(args.due_after),
		created_by=args.created_by,
		exclude_columns=[Slug(column) for column in args.column or []],
		include_archived=args.include_archived,
	)


@with_absolute_path
def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_tasks(args.path, filter=build_task_filter(args), sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_task_list(args, result)


@with_absolute_path
def handle_task_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	params = TaskCreateParams(
		title=args.title,
		assigned_to=args.assigned_to,
		priority=parse_priority(args),
		tags=args.tags or [],
		due_date=args.due_date,
		created_by=args.created_by,
		description=args.description,
	)

	result = svc.create_task(args.path, params)
	_pick(args, renderer, json_renderer).render_task_create(args, result)


@with_absolute_path
def handle_task_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.rename_task(args.path, args.new_name)
	_pick(args, renderer, json_renderer).render_task_rename(args, result)


@with_absolute_path
def handle_task_view(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_task(args.path)
	_pick(args, renderer, json_renderer).render_task_view(args, result)

@with_absolute_path
def handle_task_info(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_task(args.path)
	_pick(args, renderer, json_renderer).render_task_info(args, result)

@with_absolute_path
def handle_task_edit(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.edit_task(args.path)
	_pick(args, renderer, json_renderer).render_task_edit(args, result)


@with_absolute_path
def handle_task_update(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	updates = TaskUpdateParams(
		title=None,
		assigned_to=args.assigned_to,
		priority=parse_priority(args),
		tags=args.tags,
		due_date=args.due_date,
		created_by=args.created_by,
		description=args.description,
	)

	# parse the destination before the update so an invalid one writes nothing
	destination = parse_destination(args.column) if args.column is not None else None

	result = svc.update_task(args.path, updates=updates)

	if destination is not None:
		column, board = destination
		result = svc.move_task(Path(result.path), column, board)

	_pick(args, renderer, json_renderer).render_task_update(args, result)


@with_absolute_path
def handle_task_unset(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	unsets = TaskUnsetParams(
		assigned_to=args.assigned_to,
		priority=args.priority,
		tags=args.tags or [],
		due_date=args.due_date,
		created_by=args.created_by,
		description=args.description,
	)

	result = svc.unset_task(args.path, unsets=unsets)
	_pick(args, renderer, json_renderer).render_task_update(args, result)


@with_absolute_path
def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if args.column is not None:
		column, board = parse_destination(args.column)
		result = svc.move_task(args.path, column, board)
		_pick(args, renderer, json_renderer).render_task_move(args, result)
	else:
		op = ReorderOp.from_flags(vars(args))
		if op is None:
			raise ValueError("Must specify one of --top, --bottom, --up, or --down")
		result = svc.reorder_task(args.path, op)
		_pick(args, renderer, json_renderer).render_task_reorder(args, (result, op))


@with_absolute_path
def handle_task_delete(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if not args.force and not svc.interaction.confirm(f"Delete task '{args.path}'?"):
		return
	result = svc.delete_task(args.path)
	_pick(args, renderer, json_renderer).render_task_delete(args, result)

@with_absolute_path
def handle_task_assign(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if args.remove:
		result = svc.unset_task(args.path, TaskUnsetParams(assigned_to=True))
	else:
		result = svc.assign_task(args.path, args.assigned_to)
	_pick(args, renderer, json_renderer).render_task_assign(args, result)


@with_absolute_path
def handle_task_tag(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	if args.remove:
		result = svc.untag_task(args.path, args.tags)
	else:
		result = svc.tag_task(args.path, args.tags)
	_pick(args, renderer, json_renderer).render_task_tag(args, result)


@with_absolute_path
def handle_task_comment(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.comment_task(args.path, args.comment or "")
	if args.edit:
		result = svc.edit_task(args.path)
	_pick(args, renderer, json_renderer).render_task_comment(args, result)


# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.search(args.query, filter=build_task_filter(args), board=args.board, sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_search(args, result)


@with_absolute_path
def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	path = args.path if args.path is not None else Path("/")
	result = svc.log(path=path, limit=args.limit)
	_pick(args, renderer, json_renderer).render_log(args, result)


def handle_status(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.status()
	_pick(args, renderer, json_renderer).render_status(args, result)


def handle_set_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.set_config(args.key, args.value)
	_pick(args, renderer, json_renderer).render_set_config(args, result)


def handle_get_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.get_config(args.key)
	_pick(args, renderer, json_renderer).render_get_config(args, result)


def handle_list_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	result = svc.list_config()
	_pick(args, renderer, json_renderer).render_list_config(args, result)


def handle_repl(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	_ = args, renderer, json_renderer
	from ..services.render_service import RenderService
	from ..repl import run_repl
	from ..repl.rich_renderer import RichRenderer

	render_service = RenderService(service=svc)
	repl_renderer = RichRenderer(render_service=render_service)

	run_repl(svc=svc, renderer=repl_renderer)


def handle_tui(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer, json_renderer: CommandRenderer) -> None:
	_ = args, renderer, json_renderer
	from ..tui import run_tui

	if not svc.is_initialized:
		print(f"No kanban repository found in {svc.root}. Run `kanban init` first.")
		return

	run_tui(svc=svc)
