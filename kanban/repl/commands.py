"""Subcommand handlers for the kanban REPL."""

from __future__ import annotations

import argparse

from models import Board, Column, Task
from services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from services.repl import handle_list as handle_repl_list

# ---------------------------------------------------------------------------
# Initialization commands
# ---------------------------------------------------------------------------

def handle_init(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	_ = args
	result = svc.init()
	renderer.render_init(args, result)


def handle_use(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	if args.clear or getattr(args, "path", None) is None:
		result = svc.use(clear=True)
		renderer.render_use(args, result)
		return

	result = svc.use(path=args.path)
	renderer.render_use(args, result)

def handle_list(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result, list_type = handle_repl_list(args, svc)
	
	if list_type is Board:
		renderer.render_board_list(args, result)
	elif list_type is Column:
		renderer.render_column_list(args, result)
	elif list_type is Task:
		renderer.render_task_list(args, result)
	else:
		raise ValueError("Unexpected result type from handle_list: {}".format(type(result)))

# ---------------------------------------------------------------------------
# Board subcommands
# ---------------------------------------------------------------------------

def handle_board_create(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.create_board(args.board)
	renderer.render_board_create(args, result)


def handle_board_rename(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.rename_board(args.board, args.new_name)
	renderer.render_board_rename(args, result)


def handle_board_delete(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.delete_board(args.board)
	renderer.render_board_delete(args, result)

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


def handle_column_delete(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.delete_column(args.path)
	renderer.render_column_delete(args, result)

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


def handle_task_delete(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	result = svc.delete_task(args.path)
	renderer.render_task_delete(args, result)


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


def handle_repl(args: argparse.Namespace, svc: KanbanService, renderer: object) -> None:
	noun_first = getattr(args, "noun_first", False)
	from repl import run_repl
	run_repl(svc=svc, renderer=renderer, noun_first=noun_first)
