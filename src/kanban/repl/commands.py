"""
Subcommand handlers for the kanban REPL.
"""

from __future__ import annotations

import argparse
import logging

from ..models import Board, Column, Task
from ..repl.command_helpers import (
    _parse_priority,
    handle_list_helper,
    handle_task_list_helper,
    handle_delete_helper,
    handle_rename_helper
)
from ..services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from ..storage.seeds import BOOTSTRAP_CONFIG


# ---------------------------------------------------------------------------
# Initialization commands
# ---------------------------------------------------------------------------

def handle_init(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	config = BOOTSTRAP_CONFIG if getattr(args, "bootstrap", False) else None
	result = svc.initialize_kanban(config=config)
	renderer.render_init(args, result)

# ---------------------------------------------------------------------------
# Working context commands (use, board, column)
# ---------------------------------------------------------------------------

def handle_change_dir(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.clear or getattr(args, "path", None) is None:
		result = svc.change_dir(clear=True)
		renderer.render_change_dir(args, result)
		return

	result = svc.change_dir(path=args.path)
	renderer.render_change_dir(args, result)


def handle_board_change(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	"""Update current context with the provided board name.

	Relies on `svc.set_board()` for validation and raises if the board does not exist.
	"""
	result = svc.set_board(board=args.board)
	renderer.render_change_board(args, result)


def handle_column_change(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	"""Update current context with the provided column name.

	Relies on `svc.set_column()` for validation and raises if the column does not exist.
	"""
	result = svc.set_column(column=args.column)
	renderer.render_change_column(args, result)

# ---------------------------------------------------------------------------
# Common commands (list, delete)
# ---------------------------------------------------------------------------

def handle_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	typ, results = handle_list_helper(args, svc)
	
	if typ is Board:
		renderer.render_board_list(args, results)
	elif typ is Column:
		renderer.render_column_list(args, results)
	elif typ is Task:
		renderer.render_task_list(args, results)
	else:
		raise ValueError("Unexpected result type from handle_list: {}".format(typ))


def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.get_boards()
	renderer.render_board_list(args, result)


def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.get_columns(board=getattr(args, "board", None))
	renderer.render_column_list(args, result)


def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = handle_task_list_helper(args, svc)
	renderer.render_task_list(args, result)


def handle_delete(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
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


def handle_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
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

def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.create_board(args.board)
	renderer.render_board_create(args, result)


# TODO: REMOVE
def handle_board_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.rename_board(args.board, args.new_name)
	renderer.render_board_rename(args, result)

# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.create_column(args.path)
	renderer.render_column_create(args, result)


# TODO: REMOVE
def handle_column_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.rename_column(args.path, args.new_name)
	renderer.render_column_rename(args, result)


def handle_column_reorder(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.reorder_column(args.path, args.position)
	renderer.render_column_reorder(args, result)

# ---------------------------------------------------------------------------
# Task subcommands
# ---------------------------------------------------------------------------

def handle_task_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	params = TaskCreateParams(
		assigned_to=getattr(args, "assigned_to", None),
		priority=_parse_priority(args),
		tags=getattr(args, "tags", None) or [],
		due_date=getattr(args, "due_date", None),
		created_by=getattr(args, "created_by", None),
	)

	result = svc.create_task(args.path, params)

	if args.edit:
		logging.debug("Opening task in editor: %s", result.path)
		result = svc.edit_task(result.path)

	renderer.render_task_create(args, result)


def handle_task_show(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.get_task(args.path)
	renderer.render_task_show(args, result)


def handle_task_edit(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.edit_task(args.path)
	renderer.render_task_edit(args, result)


def handle_task_update(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	updates = TaskUpdateParams(
		title=getattr(args, "title", None),
		assigned_to=getattr(args, "assigned_to", None),
		priority=_parse_priority(args),
		tags=getattr(args, "tags", None),
		due_date=getattr(args, "due_date", None),
		created_by=getattr(args, "created_by", None),
	)

	result = svc.update_task(args.path, updates=updates)
	renderer.render_task_update(args, result)


# TODO: REMOVE
def handle_task_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.rename_task(args.path, args.new_name)
	renderer.render_task_rename(args, result)


def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.column is not None:
		result = svc.move_task(args.path, args.column)
		renderer.render_task_move(args, result)
	else:
		op = "top" if args.top else "bottom" if args.bottom else "up" if args.up else "down"
		result = svc.reorder_task(args.path, op)
		renderer.render_task_reorder(args, (result, op))


def handle_task_assign(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.assign_task(args.path, args.assigned_to)
	renderer.render_task_assign(args, result)

# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.search(args.query, board=args.board, sort=args.sort, reverse=args.reverse)
	renderer.render_search(args, result)


def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.log(path=args.path, limit=args.limit)
	renderer.render_log(args, result)


def handle_status(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.status(format=args.format)
	renderer.render_status(args, result)


def handle_config_set(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.config_set(args.key, args.value)
	renderer.render_config_set(args, result)


def handle_config_get(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.config_get(args.key)
	renderer.render_config_get(args, result)

