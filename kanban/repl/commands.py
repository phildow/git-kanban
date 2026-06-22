"""Subcommand handlers for the kanban REPL."""

from __future__ import annotations

import argparse

from models import Board, Column, Task
from services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from services.repl import handle_list as handle_list_helper, handle_delete as handle_delete_helper, handle_move as handle_move_helper

# ---------------------------------------------------------------------------
# Working context commands (use, board, column)
# ---------------------------------------------------------------------------

def handle_set_path(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.clear or getattr(args, "path", None) is None:
		result = svc.set_path(clear=True)
		renderer.render_set_path(args, result)
		return

	result = svc.set_path(path=args.path)
	renderer.render_set_path(args, result)


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


def handle_delete(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	typ = handle_delete_helper(args, svc)

	if typ is None:
		# user declined deletion
		return
	elif typ is Board:
		renderer.render_board_delete(args)
	elif typ is Column:
		renderer.render_column_delete(args)
	elif typ is Task:
		renderer.render_task_delete(args)
	else:
		raise ValueError("Unexpected result type from handle_delete: {}".format(typ))


	# TODO: Currenty unused
def handle_move(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	typ, result = handle_move_helper(args, svc)
	
	if typ is None:
		# user declined move
		return
	elif typ is Board:
		renderer.render_board_move(args, result)
	elif typ is Column:
		renderer.render_column_move(args, result)
	elif typ is Task:
		renderer.render_task_move(args, result)
	else:
		raise ValueError("Unexpected result type from handle_move: {}".format(typ))

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.create_board(args.board)
	renderer.render_board_create(args, result)


def handle_board_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.rename_board(args.board, args.new_name)
	renderer.render_board_rename(args, result)

# ---------------------------------------------------------------------------
# Column subcommands
# ---------------------------------------------------------------------------

def handle_column_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.create_column(args.path)
	renderer.render_column_create(args, result)


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
	# TODO - why can't I use args.assignee directly here? Is it because it's an optional argument on the parser?
	params = TaskCreateParams(
		assignee=getattr(args, "assignee", None),
		priority=getattr(args, "priority", None),
		tags=getattr(args, "tags", None) or [],
		due_date=getattr(args, "due_date", None),
		created_by=getattr(args, "created_by", None),
	)

	result = svc.create_task(args.path, params)
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
		assignee=getattr(args, "assignee", None),
		priority=getattr(args, "priority", None),
		tags=getattr(args, "tags", None),
		due_date=getattr(args, "due_date", None),
	)

	result = svc.update_task(args.path, updates=updates)
	renderer.render_task_edit(args, result)


def handle_task_move(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.move_task(args.path, args.dest)
	renderer.render_task_move(args, result)

# ---------------------------------------------------------------------------
# Additional commands (search, log, status, config)
# ---------------------------------------------------------------------------

def handle_search(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.search(args.query, board=args.board, sort=args.sort, reverse=args.reverse)
	renderer.render_search(args, result)


def handle_log(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if not hasattr(svc, "log"):
		raise NotImplementedError("log is not implemented on the service yet")
	result = svc.log(path=args.path, limit=args.limit)
	renderer.render_log(args, result)


def handle_status(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if not hasattr(svc, "status"):
		raise NotImplementedError("status is not implemented on the service yet")
	result = svc.status(format=args.format)
	renderer.render_status(args, result)


def handle_config_set(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if not hasattr(svc, "config_set"):
		raise NotImplementedError("config set is not implemented on the service yet")
	result = svc.config_set(args.key, args.value)
	renderer.render_config_set(args, result)


def handle_config_get(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if not hasattr(svc, "config_get"):
		raise NotImplementedError("config get is not implemented on the service yet")
	result = svc.config_get(args.key)
	renderer.render_config_get(args, result)

