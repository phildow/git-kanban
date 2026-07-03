"""
Subcommand handlers for the kanban CLI.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import wraps

from ..storage.seeds import BOOTSTRAP_CONFIG
from ..models import Priority, TaskFilter
from ..services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from ..utils.shell import prompt_for_confirmation


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def with_absolute_path(method):
	"""Decorator to rewrite the path to an absolute path"""
	@wraps(method)
	def _wrapped(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
		"""Rewrite the path in the result to include the board/column context if applicable."""
		path = getattr(args, "path", None)

		if path is not None and isinstance(path, str) and not path.startswith("/"):
			setattr(args, "path", f"/{path}")

		return method(args, svc, renderer, json_renderer)

	return _wrapped

def _pick(args: argparse.Namespace, renderer: object, json_renderer: object) -> object:
    """Return the JSON renderer when --format json is requested, otherwise the default."""
    if getattr(args, "format", None) == "json":
        return json_renderer
    return renderer


def _parse_priority(args: argparse.Namespace) -> Priority | None:
    """Return the --priority argument as a Priority, or None if not provided."""
    priority = getattr(args, "priority", None)
    return Priority(priority) if priority else None


# ---------------------------------------------------------------------------
# Initialization commands
# ---------------------------------------------------------------------------

def handle_init(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	config = BOOTSTRAP_CONFIG if getattr(args, "bootstrap", False) else None
	result = svc.initialize_kanban(config=config)
	_pick(args, renderer, json_renderer).render_init(args, result)

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.get_boards(sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_board_list(args, result)


def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.create_board(args.board)
	_pick(args, renderer, json_renderer).render_board_create(args, result)


def handle_board_rename(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.rename_board(args.board, args.new_name)
	_pick(args, renderer, json_renderer).render_board_rename(args, result)


def handle_board_delete(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	if not args.force and not prompt_for_confirmation(f"Delete board '{args.board}'?"):
		return
	result = svc.delete_board(args.board)
	_pick(args, renderer, json_renderer).render_board_delete(args, result)

# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.get_columns(board=args.board, sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_column_list(args, result)


@with_absolute_path
def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.create_column(args.path)
	_pick(args, renderer, json_renderer).render_column_create(args, result)


@with_absolute_path
def handle_column_rename(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.rename_column(args.path, args.new_name)
	_pick(args, renderer, json_renderer).render_column_rename(args, result)


@with_absolute_path
def handle_column_reorder(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.reorder_column(args.path, args.position)
	_pick(args, renderer, json_renderer).render_column_reorder(args, result)


@with_absolute_path
def handle_column_delete(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	if not args.force and not prompt_for_confirmation(f"Delete column '{args.path}'?"):
		return
	result = svc.delete_column(args.path)
	_pick(args, renderer, json_renderer).render_column_delete(args, result)

# ---------------------------------------------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

def _build_task_filter(args: argparse.Namespace) -> TaskFilter:
	"""Build a TaskFilter from parsed CLI/REPL filter arguments."""
	def _parse_date(s: str | None) -> datetime | None:
		return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc) if s else None

	return TaskFilter(
		assigned_to=getattr(args, "assigned_to", None),
		priority=_parse_priority(args),
		tags=getattr(args, "tags", None) or [],
		due_before=_parse_date(getattr(args, "due_before", None)),
		due_after=_parse_date(getattr(args, "due_after", None)),
		created_by=getattr(args, "created_by", None),
	)


@with_absolute_path
def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.get_tasks(path=args.path, filter=_build_task_filter(args), sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_task_list(args, result)


@with_absolute_path
def handle_task_create(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	params = TaskCreateParams(
		assigned_to=getattr(args, "assigned_to", None),
		priority=_parse_priority(args),
		tags=getattr(args, "tags", None) or [],
		due_date=getattr(args, "due_date", None),
		created_by=getattr(args, "created_by", None),
	)

	result = svc.create_task(args.path, params)
	_pick(args, renderer, json_renderer).render_task_create(args, result)


@with_absolute_path
def handle_task_rename(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.rename_task(args.path, args.new_name)
	_pick(args, renderer, json_renderer).render_task_rename(args, result)


@with_absolute_path
def handle_task_show(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.get_task(args.path)
	_pick(args, renderer, json_renderer).render_task_show(args, result)

@with_absolute_path
def handle_task_edit(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.edit_task(args.path)
	_pick(args, renderer, json_renderer).render_task_edit(args, result)


@with_absolute_path
def handle_task_update(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	updates = TaskUpdateParams(
		title=getattr(args, "title", None),
		assigned_to=getattr(args, "assigned_to", None),
		priority=_parse_priority(args),
		tags=getattr(args, "tags", None),
		due_date=getattr(args, "due_date", None),
		created_by=getattr(args, "created_by", None),
	)

	result = svc.update_task(args.path, updates=updates)
	_pick(args, renderer, json_renderer).render_task_edit(args, result)


@with_absolute_path
def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	if args.column is not None:
		result = svc.move_task(args.path, args.column)
		_pick(args, renderer, json_renderer).render_task_move(args, result)
	else:
		op = "top" if args.top else "bottom" if args.bottom else "up" if args.up else "down"
		result = svc.reorder_task(args.path, op)
		_pick(args, renderer, json_renderer).render_task_reorder(args, (result, op))


@with_absolute_path
def handle_task_delete(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	if not args.force and not prompt_for_confirmation(f"Delete task '{args.path}'?"):
		return
	result = svc.delete_task(args.path)
	_pick(args, renderer, json_renderer).render_task_delete(args, result)

@with_absolute_path
def handle_task_assign(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.assign_task(args.path, args.assigned_to)
	_pick(args, renderer, json_renderer).render_task_assign(args, result)


# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.search(args.query, board=args.board, sort=args.sort, reverse=args.reverse)
	_pick(args, renderer, json_renderer).render_search(args, result)


@with_absolute_path
def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.log(path=args.path, limit=args.limit)
	_pick(args, renderer, json_renderer).render_log(args, result)


def handle_status(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.status(format=args.format)
	_pick(args, renderer, json_renderer).render_status(args, result)


def handle_config_set(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.config_set(args.key, args.value)
	_pick(args, renderer, json_renderer).render_config_set(args, result)


def handle_config_get(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	result = svc.config_get(args.key)
	_pick(args, renderer, json_renderer).render_config_get(args, result)


def handle_repl(args: argparse.Namespace, svc: KanbanService, renderer: object, json_renderer: object) -> None:
	_ = renderer, json_renderer
	from ..repl.render_helper import RenderHelper
	from ..repl import run_repl

	render_helper = RenderHelper(service=svc)

	if getattr(args, "rich", False):
		from ..repl.rich_renderer import RichRenderer
		repl_renderer = RichRenderer(render_helper=render_helper)
	else:
		from ..repl.renderer import Renderer as REPLRenderer
		repl_renderer = REPLRenderer(render_helper=render_helper)

	run_repl(svc=svc, renderer=repl_renderer)
