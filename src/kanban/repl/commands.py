"""
Subcommand handlers for the kanban REPL.

Command handlers do not query user context, working board or column, or the repository directly.  
They delegate to the KanbanService.

Command handlers do not render output directly.  They delegate to a renderer, 
which is responsible for formatting and printing the output.
"""

from __future__ import annotations

import argparse
import logging

from ..models import Board, Column, Task
from ..protocols.command_renderer import CommandRenderer
from ..repl.command_helpers import (
    parse_priority,
    handle_task_list_helper,
    handle_delete_helper,
    handle_rename_helper
)
from ..services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from ..storage.seeds import BOOTSTRAP_CONFIG

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def with_relative_path(method):
	"""Decorator to rewrite the path to a relative path, removing any forward slashes"""
	def _wrapped(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer):
		path = args.path

		if path is not None and isinstance(path, str):
			args.path = args.path.lstrip("/")
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
# Working context commands (cd)
# ---------------------------------------------------------------------------

def handle_change_dir(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if args.board is None:
		result = svc.change_dir(clear=True)
		renderer.render_change_dir(args, result)
		return

	result = svc.set_board(board=args.board)
	renderer.render_change_dir(args, result)


# ---------------------------------------------------------------------------
# Common commands
# ---------------------------------------------------------------------------

@with_relative_path
def handle_delete(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	typ, result = handle_delete_helper(args, svc)

	if typ is None:
		# user declined deletion
		return
	elif typ is Board:
		renderer.render_board_delete(args, result)
	elif typ is Column:
		renderer.render_column_delete(args, result)
	elif typ is Task:
		renderer.render_task_delete(args, result)
	else:
		raise ValueError("Unexpected result type from handle_delete: {}".format(typ))


@with_relative_path
def handle_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	typ, result = handle_rename_helper(args, svc)

	if typ is None:
		# user declined rename
		return
	elif typ is Board:
		renderer.render_board_rename(args, result)
	elif typ is Column:
		renderer.render_column_rename(args, result)
	elif typ is Task:
		renderer.render_task_rename(args, result)
	else:
		raise ValueError("Unexpected result type from handle_rename: {}".format(typ))

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_boards()
	renderer.render_board_list(args, result)


def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.create_board(args.board)
	renderer.render_board_create(args, result)
	

# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_columns(board=args.board)
	renderer.render_column_list(args, result)


def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if svc.working_board is None:
		raise ValueError("No active board; set one with `cd` before creating a column")

	result = svc.create_column(".", args.column)
	renderer.render_column_create(args, result)


def handle_column_reorder(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.reorder_column(args.column, args.position)
	renderer.render_column_reorder(args, result)

# ---------------------------------------------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = handle_task_list_helper(args, svc)
	renderer.render_task_list(args, result)
	

def handle_task_create(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if svc.working_board is None and not args.column.startswith("/"):
		raise ValueError("No active board; set one with `cd` before creating a task")

	params = TaskCreateParams(
		title=args.title,
		assigned_to=args.assigned_to,
		priority=parse_priority(args),
		tags=args.tags or [],
		due_date=args.due_date,
		created_by=args.created_by,
	)

	result = svc.create_task(args.column, params)

	if args.edit:
		result = svc.edit_task(result.path)

	renderer.render_task_create(args, result)


@with_relative_path
def handle_task_show(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.get_task(args.path)
	renderer.render_task_show(args, result)


@with_relative_path
def handle_task_edit(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.edit_task(args.path)
	renderer.render_task_edit(args, result)


@with_relative_path
def handle_task_update(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	updates = TaskUpdateParams(
		title=None,
		assigned_to=args.assigned_to,
		priority=parse_priority(args),
		tags=args.tags,
		due_date=args.due_date,
		created_by=args.created_by,
	)

	result = svc.update_task(args.path, updates=updates)

	if args.column is not None:
		result = svc.move_task(result.path, args.column)

	renderer.render_task_update(args, result)


@with_relative_path
def handle_task_rename(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.rename_task(args.path, args.new_name)
	renderer.render_task_rename(args, result)


@with_relative_path
def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	if args.column is not None:
		result = svc.move_task(args.path, args.column)
		renderer.render_task_move(args, result)
	else:
		op = "top" if args.top else "bottom" if args.bottom else "up" if args.up else "down" if args.down else None
		if op is None:
			raise ValueError("Must specify one of --top, --bottom, --up, or --down")
		result = svc.reorder_task(args.path, op)
		renderer.render_task_reorder(args, (result, op))


@with_relative_path
def handle_task_assign(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.assign_task(args.path, args.assigned_to)
	renderer.render_task_assign(args, result)

# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.search(args.query, board=args.board, sort=args.sort, reverse=args.reverse)
	renderer.render_search(args, result)


@with_relative_path
def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: CommandRenderer) -> None:
	result = svc.log(path=args.path, limit=args.limit)
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

