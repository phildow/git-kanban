"""
Subcommand handlers for the kanban REPL.

Command handlers do not query user context, working board or column, or the repository directly.  
They delegate to the KanbanService.

Command handlers do not render output directly.  They delegate to a renderer, 
which is responsible for formatting and printing the output.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import logging

from ..models import Board, Column, ReorderOp, Slug, Task
from ..protocols.command_renderer import CommandRenderer
from ..repl.command_helpers import (
    build_task_filter,
    handle_task_list_helper,
    handle_create_helper,
    handle_delete_helper,
    handle_info_helper,
    handle_rename_helper
)
from ..services.kanban import KanbanService, TaskCreateParams, TaskUnsetParams, TaskUpdateParams
from ..utils.args import parse_priority
from ..utils.str import parse_destination
from ..storage.seeds import BOOTSTRAP_CONFIG

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def with_relative_path(method):
	"""Decorator to rewrite the path to a relative path, removing any forward slashes"""
	def _wrapped(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer):
		path = args.path

		if path is not None:
			if isinstance(path, str):
				args.path = Path(path.lstrip("/"))
			elif isinstance(path, Path):
				args.path = Path(str(path).lstrip("/"))
		return method(args, svc, renderer)
	return _wrapped

def with_task_slug(method):
	"""Decorator to type the path as a Slug, identifying a task by its bare slug.

	Task-target commands (show, edit, update, move, assign) address a task by
	its slug alone; the service resolves the containing column within the active
	board. A slash-bearing token is still forwarded as a Slug so the service can
	treat it as an explicit path override.
	"""
	def _wrapped(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer):
		if args.path is not None:
			args.path = Slug(args.path)
		return method(args, svc, renderer)
	return _wrapped

# ---------------------------------------------------------------------------
# Initialization commands
# ---------------------------------------------------------------------------

def handle_init(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	config = BOOTSTRAP_CONFIG if args.bootstrap == True else None
	result = svc.initialize_kanban(config=config)
	renderer.render_init(args, result)

# ---------------------------------------------------------------------------
# Working context commands (board)
# ---------------------------------------------------------------------------

def handle_set_board(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.set_board(slug=Slug(args.board))
	renderer.render_set_board(args, result)


# ---------------------------------------------------------------------------
# Common commands
# ---------------------------------------------------------------------------

@with_task_slug
def handle_delete(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_delete_helper(args, svc)

	if result is None:
		# user declined deletion
		return
	elif isinstance(result, Board):
		renderer.render_board_delete(args, result)
	elif isinstance(result, Column):
		renderer.render_column_delete(args, result)
	elif isinstance(result, Task):
		renderer.render_task_delete(args, result)
	else:
		raise ValueError("Unexpected result type from handle_delete")


def handle_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_create_helper(args, svc)

	if isinstance(result, Board):
		renderer.render_board_create(args, result)
	elif isinstance(result, Column):
		renderer.render_column_create(args, result)
	elif isinstance(result, Task):
		renderer.render_task_create(args, result)
	else:
		raise ValueError("Unexpected result type from handle_create")

@with_task_slug
def handle_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_rename_helper(args, svc)

	if isinstance(result, Board):
		renderer.render_board_rename(args, result)
	elif isinstance(result, Column):
		renderer.render_column_rename(args, result)
	elif isinstance(result, Task):
		renderer.render_task_rename(args, result)
	else:
		raise ValueError("Unexpected result type from handle_rename")

@with_task_slug
def handle_info(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_info_helper(args, svc)

	if isinstance(result, Board):
		renderer.render_board_info(args, result)
	elif isinstance(result, Column):
		renderer.render_column_info(args, result)
	elif isinstance(result, Task):
		renderer.render_task_info(args, result)
	else:
		raise ValueError("Unexpected result type from handle_info")

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_boards()
	renderer.render_board_list(args, result)


# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_columns(board=None)
	renderer.render_column_list(args, result)


def handle_column_reorder(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.reorder_column(Path(args.column), args.position)
	renderer.render_column_reorder(args, result)

# ---------------------------------------------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_task_list_helper(args, svc)
	renderer.render_task_list(args, result)


@with_task_slug
def handle_task_view(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_task(args.path)
	renderer.render_task_view(args, result)


@with_task_slug
def handle_task_edit(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.edit_task(args.path)
	renderer.render_task_edit(args, result)


@with_task_slug
def handle_task_update(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
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
	destination = parse_destination(args.column, require_absolute=True) if args.column is not None else None

	result = svc.update_task(args.path, updates=updates)

	if destination is not None:
		column, board = destination
		result = svc.move_task(Path(result.path), column, board)

	renderer.render_task_update(args, result)


@with_task_slug
def handle_task_unset(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	unsets = TaskUnsetParams(
		assigned_to=args.assigned_to,
		priority=args.priority,
		tags=args.tags or [],
		due_date=args.due_date,
		created_by=args.created_by,
		description=args.description,
	)

	result = svc.unset_task(args.path, unsets=unsets)
	renderer.render_task_update(args, result)


@with_relative_path
def handle_task_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.rename_task(args.path, args.new_name)
	renderer.render_task_rename(args, result)


@with_task_slug
def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if args.column is not None:
		column, board = parse_destination(args.column, require_absolute=True)
		result = svc.move_task(args.path, column, board)
		renderer.render_task_move(args, result)
	else:
		op = ReorderOp.from_flags(vars(args))
		if op is None:
			raise ValueError("Must specify one of --top, --bottom, --up, or --down")
		result = svc.reorder_task(args.path, op)
		renderer.render_task_reorder(args, (result, op))


@with_task_slug
def handle_task_assign(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if args.remove:
		result = svc.unset_task(args.path, TaskUnsetParams(assigned_to=True))
	else:
		result = svc.assign_task(args.path, args.assigned_to)
	renderer.render_task_assign(args, result)


@with_task_slug
def handle_task_tag(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if args.remove:
		result = svc.untag_task(args.path, args.tags)
	else:
		result = svc.tag_task(args.path, args.tags)
	renderer.render_task_tag(args, result)


@with_task_slug
def handle_task_comment(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.comment_task(args.path, args.comment or "")
	if args.edit:
		result = svc.edit_task(args.path)
	renderer.render_task_comment(args, result)

# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.search(args.query, filter=build_task_filter(args), board=args.board, sort=args.sort, reverse=args.reverse)
	renderer.render_search(args, result)


@with_relative_path
def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	path = args.path if args.path is not None else Path("/")
	result = svc.log(path=path, limit=args.limit)
	renderer.render_log(args, result)


def handle_status(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.status()
	renderer.render_status(args, result)


def handle_set_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.set_config(args.key, args.value)
	renderer.render_set_config(args, result)


def handle_get_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_config(args.key)
	renderer.render_get_config(args, result)


def handle_list_config(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.list_config()
	renderer.render_list_config(args, result)

