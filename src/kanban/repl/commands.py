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
	config = BOOTSTRAP_CONFIG if args.bootstrap == True else None
	result = svc.initialize_kanban(config=config)
	renderer.render_init(args, result)

# ---------------------------------------------------------------------------
# Working context commands (cd)
# ---------------------------------------------------------------------------

def handle_change_dir(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.board is None:
		result = svc.change_dir(clear=True)
		renderer.render_change_dir(args, result)
		return

	result = svc.set_board(board=args.board)
	renderer.render_change_dir(args, result)


# ---------------------------------------------------------------------------
# Common commands (list, delete)
# ---------------------------------------------------------------------------

def handle_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.boards:
		if args.path is not None:
			raise ValueError("Cannot combine --boards with a path")
		result = svc.get_boards()
		renderer.render_board_list(args, result)
		return

	if args.columns:
		board = args.path or svc.working_board
		if not board:
			raise ValueError("No active board; provide a board or set one with `cd`")
		result = svc.get_columns(board=board)
		renderer.render_column_list(args, result)
		return

	result = handle_list_helper(args, svc)
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

def handle_board_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.get_boards()
	renderer.render_board_list(args, result)


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

def handle_column_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.get_columns(board=args.board)
	renderer.render_column_list(args, result)


def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	board = svc.working_board
	if not board:
		raise ValueError("No active board; set one with `cd` before creating a column")

	result = svc.create_column(f"/{board}/{args.column}")
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

def handle_task_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = handle_task_list_helper(args, svc)
	renderer.render_task_list(args, result)
	

def handle_task_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	board = svc.working_board
	if not board:
		raise ValueError("No active board; set one with `cd` before creating a task")

	params = TaskCreateParams(
		assigned_to=args.assigned_to,
		priority=_parse_priority(args),
		tags=args.tags or [],
		due_date=args.due_date,
		created_by=args.created_by,
	)

	task_path = f"/{board}/{args.column}/{args.title}"
	result = svc.create_task(task_path, params)

	if args.edit:
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
		title=None,
		assigned_to=args.assigned_to,
		priority=_parse_priority(args),
		tags=args.tags,
		due_date=args.due_date,
		created_by=args.created_by,
	)

	result = svc.update_task(args.path, updates=updates)

	if args.column is not None:
		result = svc.move_task(result.path, args.column)

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

