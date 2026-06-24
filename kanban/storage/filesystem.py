from __future__ import annotations

import configparser
import logging
import shutil

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column
from storage.kanban import KanbanRepository, BoardNotFound, BoardAlreadyExists, ColumnAlreadyExists, ColumnNotFound, TaskNotFound, TaskAlreadyExists
from utils.str import kebab_case


class FilesystemRepository(KanbanRepository):
    """Filesystem-backed repository scaffold.

    This class is intentionally scaffold-only for now. Each method is wired
    with the final interface and can be incrementally implemented.
    """

    def __init__(self, root: Path) -> None:
        super().__init__(root)

    # ------------------------------------------------------------------
    # Filepaths
    # ------------------------------------------------------------------

    # TODO: make some of these properties private

    @property
    def kanban_dir(self) -> Path | None:
        return self.root / ".kanban"

    @property
    def kanban_store_dir(self) -> Path:
        return self.root / ".kanban-store"

    @property
    def boards_dir(self) -> Path:
        return self.kanban_store_dir / "boards"
    
    @property
    def config_file(self) -> Path:
        return self.kanban_dir / "config"

    @property
    def userdata_file(self) -> Path:
        return self.kanban_dir / "userdata"

    @property
    def index_file(self) -> Path:
        return self.kanban_dir / "index.db"

    # ------------------------------------------------------------------
    # Initialization (setup)
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self.kanban_dir.exists() and self.kanban_store_dir.exists()

    def init_storage(self) -> None:
        if self.is_initialized:
            raise ValueError("Kanban is already initialized")

        kanban_dir = self.kanban_dir
        kanban_dir.mkdir()
        (kanban_dir / "history").touch()
        self.config_file.touch()

        kanban_store_dir = self.kanban_store_dir
        kanban_store_dir.mkdir()
        self.userdata_file.touch()
        
        self.index_file.touch()

        boards_dir = self.boards_dir
        boards_dir.mkdir()
        (boards_dir / ".metadata").touch()

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    def board_exists(self, name: str) -> bool:
        slug = kebab_case(name)

        board_path = self.boards_dir / slug
        return board_path.is_dir() and not name.startswith(".")

    # TODO: SYNC - metadata must match the name and slug of the board directory
    def get_boards(self) -> list[Board]:
        boards = []
        for entry in sorted(self.boards_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            column_count = sum(
                1 for e in entry.iterdir()
                if e.is_dir() and not e.name.startswith(".")
            )
            task_count = sum(
                1
                for col in entry.iterdir()
                if col.is_dir() and not col.name.startswith(".")
                for f in col.iterdir()
                if f.is_file() and not f.name.startswith(".")
            )
            slug = kebab_case(entry.name)
            name = self.get_board_metadata(slug, "fields.name") or entry.name
            slug = self.get_board_metadata(slug, "fields.slug") or kebab_case(entry.name)

            boards.append(Board(name=name, slug=slug, column_count=column_count, task_count=task_count))
        return boards

    # TODO: SYNC - metadata must match the name and slug of the board directory
    # TODO: load the column count and task count
    def get_board(self, name: str) -> Board:
        slug = kebab_case(name)
        board_path = self.boards_dir / slug

        if not board_path.is_dir() or name.startswith("."):
            raise BoardNotFound(name)
        
        name = self.get_board_metadata(slug, "fields.name") or name
        slug = self.get_board_metadata(slug, "fields.slug") or slug

        return Board(name=name, slug=slug)

    def create_board(self, name: str) -> Board:
        slug = kebab_case(name)

        if self.board_exists(slug):
            raise BoardAlreadyExists(name)

        (self.boards_dir / slug).mkdir()
        (self.boards_dir / slug / ".metadata").touch()
        
        self.set_board_metadata(slug, "fields.name", name)
        self.set_board_metadata(slug, "fields.slug", slug)

        return Board(name=name, slug=slug)

    def rename_board(self, name: str, new_name: str) -> Board:
        slug = kebab_case(name)
        new_slug = kebab_case(new_name)

        if not self.board_exists(slug):
            raise BoardNotFound(name)
        if self.board_exists(new_slug):
            raise BoardAlreadyExists(new_name)
        
        (self.boards_dir / slug).rename(self.boards_dir / new_slug)

        self.set_board_metadata(new_slug, "fields.name", new_name)
        self.set_board_metadata(new_slug, "fields.slug", new_slug)

        return Board(name=new_name, slug=new_slug)

    def delete_board(self, name: str) -> None:
        slug = kebab_case(name)

        if not self.board_exists(slug):
            raise BoardNotFound(name)
        shutil.rmtree(self.boards_dir / slug)

    # ------------------------------------------------------------------
    # Columns operations
    # ------------------------------------------------------------------

    # TODO: fail gracefully from corrupt metadta files (e.g. missing column in order file) instead of crashing, 
    #       and log warnings to help users fix them
    # TODO: verify that the files listed in the sort order match the actual column directories and log warnings 
    #       if not, and handle missing columns by appending them to the end of the list rather than crashing
    
    # TODO: move these methods

    def _get_task_order(self, board: str, column: str) -> list[str]:
        """Return the stored task order for a column, falling back to filesystem sort."""
        column_slug = kebab_case(column)
        board_slug = kebab_case(board)
        raw = self.get_column_metadata(board_slug, column_slug, "tasks.order")

        if raw:
            return [f.strip() for f in raw.split("\n") if f.strip()]
        return sorted(
            e.name for e in (self.boards_dir / board_slug / column_slug).iterdir()
            if e.is_file() and not e.name.startswith(".") and e.suffix == ".md"
        )

    def _set_task_order(self, board: str, column: str, order: list[str]) -> None:
        """Persist the task order for a column to its .metadata file.

        Each filename is stored on its own line using configparser's multi-line
        value support: continuation lines are indented, so configparser treats
        them as part of the same value rather than new keys.
        """
        board_slug = kebab_case(board)
        column_slug = kebab_case(column)
        self.set_column_metadata(board_slug, column_slug, "tasks.order", "\n" + "\n".join(order))

    def _get_column_order(self, board: str) -> list[str]:
        """Return the stored column order for a board, falling back to filesystem sort."""
        board_slug = kebab_case(board)

        raw = self.get_board_metadata(board_slug, "columns.order")
        if raw:
            return [c.strip() for c in raw.split("\n") if c.strip()]
        return sorted(
            e.name for e in (self.boards_dir / board_slug).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )

    def _set_column_order(self, board: str, order: list[str]) -> None:
        """Persist the column order for a board to its metadata file.

        Each directory name is stored on its own line using configparser's
        multi-line value support: continuation lines are indented, so
        configparser treats them as part of the same value rather than new keys.
        """
        board_slug = kebab_case(board)
        self.set_board_metadata(board_slug, "columns.order", "\n" + "\n".join(order))

    def _column_task_count(self, board: str, column: str) -> int:
        """Return the number of tasks in a column."""
        column_slug = kebab_case(column)
        board_slug = kebab_case(board)
        
        return sum(
            1 for e in (self.boards_dir / board_slug / column_slug).iterdir()
            if e.is_file() and not e.name.startswith(".")
        )

    def column_exists(self, board: str, name: str) -> bool:
        board_slug = kebab_case(board)
        column_slug = kebab_case(name)

        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        
        column_path = self.boards_dir / board_slug / column_slug
        return column_path.is_dir() and not name.startswith(".")

    def get_columns(self, board: str) -> list[Column]:
        board_slug = kebab_case(board)
        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        
        existing = {
            e.name for e in (self.boards_dir / board_slug).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        }
        
        order = self._get_column_order(board)
         
        columns = []
        for i, name in enumerate(c for c in order if c in existing):
            task_count = self._column_task_count(board, name)
            column_slug = kebab_case(name)
            name = self.get_column_metadata(board_slug, name, "fields.name") or name
            column_slug = self.get_column_metadata(board_slug, name, "fields.slug") or column_slug
            columns.append(Column(name=name, slug=column_slug, board=board, position=i, task_count=task_count))
            
        return columns

    def get_column(self, board: str, name: str) -> Column:
        column_slug = kebab_case(name)
        board_slug = kebab_case(board)
        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        
        column_path = self.boards_dir / board_slug / name
        
        if not column_path.is_dir() or name.startswith("."):
            raise ColumnNotFound(board, name)
        
        task_count = self._column_task_count(board, name)
        order = self._get_column_order(board)
        position = order.index(name) if name in order else len(order)
        name = self.get_column_metadata(board_slug, name, "fields.name") or name
        column_slug = self.get_column_metadata(board_slug, name, "fields.slug") or column_slug

        return Column(name=name, slug=column_slug, board=board, position=position, task_count=task_count)

    def create_column(self, board: str, name: str) -> Column:
        column_slug = kebab_case(name)
        board_slug = kebab_case(board)

        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        
        column_path = self.boards_dir / board_slug / column_slug
        
        if column_path.exists():
            raise ColumnAlreadyExists(board, name)
        
        order = self._get_column_order(board_slug)
        column_path.mkdir()
        (column_path / ".metadata").touch()
        order.append(column_slug)
        
        self.set_column_metadata(board_slug, column_slug, "fields.name", name)
        self.set_column_metadata(board_slug, column_slug, "fields.slug", column_slug)
        self._set_column_order(board_slug, order)

        return Column(name=name, slug=column_slug, board=board, position=len(order) - 1)

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        new_column_slug = kebab_case(new_name)
        column_slug = kebab_case(name)
        board_slug = kebab_case(board)
        
        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        if not self.column_exists(board_slug, column_slug):
            raise ColumnNotFound(board, name)
        if self.column_exists(board_slug, new_column_slug):
            raise ColumnAlreadyExists(board, new_name)
        
        (self.boards_dir / board_slug / column_slug).rename(self.boards_dir / board_slug / new_column_slug)
        order = self._get_column_order(board_slug)
        
        if column_slug in order:
            order[order.index(column_slug)] = new_column_slug
        
        self.set_column_metadata(board_slug, new_column_slug, "fields.name", new_name)
        self.set_column_metadata(board_slug, new_column_slug, "fields.slug", new_column_slug)
        self._set_column_order(board_slug, order)

        return self.get_column(board, new_name)

    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        board_slug = kebab_case(board)

        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        if not self.column_exists(board_slug, name):
            raise ColumnNotFound(board, name)
        
        column_slug = kebab_case(name)
        order = self._get_column_order(board_slug)
        
        if column_slug in order:
            order.remove(column_slug)
        order.insert(max(0, min(position, len(order))), column_slug)
        
        self._set_column_order(board_slug, order)
        return self.get_columns(board_slug)

    def delete_column(self, board: str, name: str) -> None:
        column_slug = kebab_case(name)
        board_slug = kebab_case(board)

        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        if not self.column_exists(board_slug, column_slug):
            raise ColumnNotFound(board, name)
        
        order = self._get_column_order(board_slug)
        
        if column_slug in order:
            order.remove(column_slug)
        
        self._set_column_order(board_slug, order)
        shutil.rmtree(self.boards_dir / board_slug / column_slug)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------
    
    def task_exists(self, board: str, column: str, filename: str) -> bool:
        board_slug = kebab_case(board)
        path = self.boards_dir / board_slug / column / f"{filename}.md"
        return path.is_file()

    def get_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
    ) -> list[Task]:
        if board is None and column is not None:
            raise ValueError("Cannot filter by column without a board: {}".format(column))

        if board is not None and not self.board_exists(board):
            raise BoardNotFound(board)
        if board is not None and column is not None and not self.column_exists(board, column):
            raise ColumnNotFound(board, column)

        column_slug = kebab_case(column) if column is not None else None
        board_slug = kebab_case(board) if board is not None else None

        boards = [board_slug] if board_slug is not None else [
            e.name for e in sorted(self.boards_dir.iterdir())
            if e.is_dir() and not e.name.startswith(".")
        ]

        tasks: list[Task] = []
        
        for b in boards:
            columns = [column_slug] if column_slug is not None else [
                e.name for e in sorted((self.boards_dir / b).iterdir())
                if e.is_dir() and not e.name.startswith(".")
            ]
            for col in columns:
                col_dir = self.boards_dir / b / col
                for filename in self._get_task_order(b, col):
                    entry = col_dir / filename
                    if entry.is_file():
                        board_name = self._board_name_from_slug(b)
                        column_name = self._column_name_from_slug(b, col)
                        tasks.append(self._parse_task_file(entry, board_name, column_name))

        return tasks

    def get_task(self, board: str, column: str, filename: str) -> Task:
        column_slug = kebab_case(column)
        board_slug = kebab_case(board)

        if not self.board_exists(board_slug):
            raise BoardNotFound(board)
        if not self.column_exists(board_slug, column_slug):
            raise ColumnNotFound(board, column)
        
        task_path = self.boards_dir / board_slug / column_slug / f"{filename}.md"
        
        if not task_path.is_file():
            raise TaskNotFound(f"{board}/{column}/{filename}")
        
        return self._parse_task_file(task_path, board, column)

    def create_task(self, task: Task, filename: str) -> Task:
        column_slug = kebab_case(task.column)
        board_slug = kebab_case(task.board)

        if not self.board_exists(board_slug):
            raise BoardNotFound(task.board)
        if not self.column_exists(board_slug, column_slug):
            raise ColumnNotFound(task.board, task.column)
        if self.task_exists(board_slug, column_slug, filename):
            TaskAlreadyExists(task.board, task.column, filename)
        
        path = self.boards_dir / board_slug / column_slug / f"{filename}.md"
        now = datetime.now(timezone.utc)
        fm_lines = [
            "---",
            f"id: {task.id}",
            f"title: {task.title}",
            f"slug: {task.slug}",
            f"created_at: {(task.created_at or now).isoformat()}",
            f"updated_at: {(task.updated_at or now).isoformat()}",
        ]
        
        if task.priority:
            fm_lines.append(f"priority: {task.priority}")
        if task.assignee:
            fm_lines.append(f"assignee: {task.assignee}")
        if task.tags:
            fm_lines.append(f"tags: [{', '.join(task.tags)}]")
        if task.due_date:
            fm_lines.append(f"due_date: {task.due_date.isoformat()}")
        if task.created_by:
            fm_lines.append(f"created_by: {task.created_by}")
        
        fm_lines.append("---")
        content = "\n".join(fm_lines) + "\n"
        
        if task.body:
            content += f"\n{task.body}\n"
        
        path.write_text(content, encoding="utf-8")
        order = self._get_task_order(board_slug, column_slug)
        
        if f"{filename}.md" not in order:
            order.append(f"{filename}.md")
        self._set_task_order(board_slug, column_slug, order)

        return self._parse_task_file(path, task.board, task.column)

    def update_task(self, task: Task) -> Task:
        board_slug = kebab_case(task.board)
        column_slug = kebab_case(task.column)
        current_filename = f"{task.slug}.md"
        current_path = self.boards_dir / board_slug / column_slug / current_filename

        if not current_path.is_file():
            raise TaskNotFound(f"{task.board}/{task.column}/{task.slug}")

        new_slug = kebab_case(task.title)
        new_filename = f"{new_slug}.md"
        new_path = self.boards_dir / board_slug / column_slug / new_filename
        renamed = new_slug != task.slug

        if renamed and new_path.exists():
            raise TaskAlreadyExists(task.board, task.column, new_slug)

        now = datetime.now(timezone.utc)
        fm_lines = [
            "---",
            f"id: {task.id}",
            f"title: {task.title}",
            f"slug: {new_slug}",
            f"created_at: {task.created_at.isoformat() if task.created_at else now.isoformat()}",
            f"updated_at: {now.isoformat()}",
        ]
        if task.priority:
            fm_lines.append(f"priority: {task.priority}")
        if task.assignee:
            fm_lines.append(f"assignee: {task.assignee}")
        if task.tags:
            fm_lines.append(f"tags: [{', '.join(task.tags)}]")
        if task.due_date:
            fm_lines.append(f"due_date: {task.due_date.isoformat()}")
        if task.created_by:
            fm_lines.append(f"created_by: {task.created_by}")
        fm_lines.append("---")
        content = "\n".join(fm_lines) + "\n"
        if task.body:
            content += f"\n{task.body}\n"

        new_path.write_text(content, encoding="utf-8")

        if renamed:
            current_path.unlink()
            order = self._get_task_order(board_slug, column_slug)
            if current_filename in order:
                order[order.index(current_filename)] = new_filename
            else:
                order.append(new_filename)
            self._set_task_order(board_slug, column_slug, order)

        return self._parse_task_file(new_path, task.board, task.column)

    def move_task(self, task: Task, column: str) -> Task:
        board_slug = kebab_case(task.board)
        src_column_slug = kebab_case(task.column)
        dest_column_slug = kebab_case(column)
        filename = f"{task.slug}.md"

        src_file = self.boards_dir / board_slug / src_column_slug / filename
        dest_file = self.boards_dir / board_slug / dest_column_slug / filename
    
        if not src_file.is_file():
            raise TaskNotFound(f"{task.board}/{task.column}/{task.slug}")
        if not self.column_exists(task.board, column):
            raise ColumnNotFound(task.board, column)
        if src_column_slug != dest_column_slug and dest_file.exists():
            raise TaskAlreadyExists(task.board, column, task.slug)

        now = datetime.now(timezone.utc)
        lines = src_file.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith("updated_at:"):
                lines[i] = f"updated_at: {now.isoformat()}\n"

        if src_column_slug == dest_column_slug:
            src_file.write_text("".join(lines), encoding="utf-8")
        else:
            dest_file.write_text("".join(lines), encoding="utf-8")
            src_file.unlink()

            src_order = self._get_task_order(board_slug, src_column_slug)
            if filename in src_order:
                src_order.remove(filename)
            self._set_task_order(board_slug, src_column_slug, src_order)

            dest_order = self._get_task_order(board_slug, dest_column_slug)
            if filename not in dest_order:
                dest_order.append(filename)
            self._set_task_order(board_slug, dest_column_slug, dest_order)

        board_name = self.get_board_metadata(board_slug, "fields.name") or task.board
        column_name = self.get_column_metadata(board_slug, dest_column_slug, "fields.name") or column
        return self._parse_task_file(dest_file, board_name, column_name)

    def delete_task(self, task: Task) -> None:
        board_slug = kebab_case(task.board)
        column_slug = kebab_case(task.column)
        filename = f"{task.slug}.md"
        path = self.boards_dir / board_slug / column_slug / filename
        order = self._get_task_order(board_slug, column_slug)
        
        if filename in order:
            order.remove(filename)

        self._set_task_order(board_slug, column_slug, order)
        
        if not path.is_file():
            raise TaskNotFound(f"{task.board}/{task.column}/{task.slug}")
        else:
            path.unlink()

    # ------------------------------------------------------------------
    # Config, user data, and metadata
    # ------------------------------------------------------------------

    # TODO: Refactor all this shared code, rename config to avoid ambiguity with the configparser module

    # Config
    
    def get_config(self, keypath: str) -> str | None:
        """Read a value from the config INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.config_file, encoding="utf-8")

        if section not in cfg or key not in cfg[section]:
            return None

        return cfg[section][key]

    def set_config(self, keypath: str, value: str | None) -> None:
        """Write a value to the config INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.config_file, encoding="utf-8")

        if value is None:
            if section in cfg and key in cfg[section]:
                del cfg[section][key]
        else:
            if section not in cfg:
                cfg[section] = {}
            cfg[section][key] = value

        self.config_file.write_text(self._write_ini(cfg), encoding="utf-8")

    # User data

    def get_userdata(self, keypath: str) -> str | None:
        """Read a value from the userdata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.userdata_file, encoding="utf-8")

        if section not in cfg or key not in cfg[section]:
            return None

        return cfg[section][key]

    def set_userdata(self, keypath: str, value: str | None) -> None:
        """Write a value to the userdata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.userdata_file, encoding="utf-8")

        if value is None:
            if section in cfg and key in cfg[section]:
                del cfg[section][key]
        else:
            if section not in cfg:
                cfg[section] = {}
            cfg[section][key] = value

        self.userdata_file.write_text(self._write_ini(cfg), encoding="utf-8")

    # Board metadata
    
    def _board_name_from_slug(self, slug: str) -> str:
        """Return the board name from its slug, falling back to the slug if not found."""
        return self.get_board_metadata(slug, "fields.name") or slug
    
    def _column_name_from_slug(self, board_slug: str, column_slug: str) -> str:
        """Return the column name from its slug, falling back to the slug if not found."""
        return self.get_column_metadata(board_slug, column_slug, "fields.name") or column_slug

    def _board_metadata_file(self, board: str) -> Path:
        """Return the path to the .metadata INI file for the given board."""
        board_slug = kebab_case(board)
        return self.boards_dir / board_slug / ".metadata"

    def get_board_metadata(self, board: str, keypath: str) -> str | None:
        """Read a value from a board's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        board_slug = kebab_case(board)
        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self._board_metadata_file(board_slug), encoding="utf-8")

        if section not in cfg or key not in cfg[section]:
            return None

        return cfg[section][key]

    def set_board_metadata(self, board: str, keypath: str, value: str | None) -> None:
        """Write a value to a board's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        board_slug = kebab_case(board)
        section, key = keypath.split(".", 1)
        metadata_file = self._board_metadata_file(board_slug)
        cfg = configparser.ConfigParser()
        cfg.read(metadata_file, encoding="utf-8")

        if value is None:
            if section in cfg and key in cfg[section]:
                del cfg[section][key]
        else:
            if section not in cfg:
                cfg[section] = {}
            cfg[section][key] = value

        metadata_file.write_text(self._write_ini(cfg), encoding="utf-8")

    # Column metadata

    def _column_metadata_file(self, board: str, column: str) -> Path:
        """Return the path to the .metadata INI file for the given column."""
        column_slug = kebab_case(column)
        board_slug = kebab_case(board)
        return self.boards_dir / board_slug / column_slug / ".metadata"

    def get_column_metadata(self, board: str, column: str, keypath: str) -> str | None:
        """Read a value from a column's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")
        
        board_slug = kebab_case(board)
        column_slug = kebab_case(column)
        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self._column_metadata_file(board_slug, column_slug), encoding="utf-8")
        
        if section not in cfg or key not in cfg[section]:
            return None
        
        return cfg[section][key]

    def set_column_metadata(self, board: str, column: str, keypath: str, value: str | None) -> None:
        """Write a value to a column's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")
        board_slug = kebab_case(board)
        column_slug = kebab_case(column)
        section, key = keypath.split(".", 1)
        metadata_file = self._column_metadata_file(board_slug, column_slug)
        cfg = configparser.ConfigParser()
        cfg.read(metadata_file, encoding="utf-8")
        
        if value is None:
            if section in cfg and key in cfg[section]:
                del cfg[section][key]
        else:
            if section not in cfg:
                cfg[section] = {}
            cfg[section][key] = value
        
        metadata_file.write_text(self._write_ini(cfg), encoding="utf-8")

    # TODO: kanban service also does task parsing move to a utility module to avoid duplication between service and repository layers

    # ------------------------------------------------------------------
    # Task file parsing and utilities
    # ------------------------------------------------------------------

    def _parse_task_file(self, path: Path, board: str, column: str) -> Task:
        
        def _parse_dt(raw: str) -> datetime:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        
        """Parse a markdown task file with YAML frontmatter into a Task."""
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()

        end_idx: int | None = None
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break

        fm: dict[str, str] = {}
        if end_idx is not None:
            for line in lines[1:end_idx]:
                if not line.strip() or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                fm[key.strip()] = value.strip()
            body = "\n".join(lines[end_idx + 1:]).strip("\n")
        else:
            body = content.strip("\n")

        task_id = UUID(fm["id"]) if "id" in fm else UUID(int=0)
        title = fm.get("title", path.stem)
        slug = fm.get("slug", path.stem)

        due_date: datetime | None = None
        if raw := fm.get("due_date", "").strip():
            due_date = _parse_dt(raw)

        created_at: datetime | None = None
        if raw := fm.get("created_at", "").strip():
            created_at = _parse_dt(raw)

        updated_at: datetime | None = None
        if raw := fm.get("updated_at", "").strip():
            updated_at = _parse_dt(raw)

        tags_raw = fm.get("tags", "").strip().strip("[]")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        return Task(
            id=task_id,
            title=title,
            slug=slug,
            board=board,
            column=column,
            created_by=fm.get("created_by") or None,
            assignee=fm.get("assignee") or None,
            priority=fm.get("priority") or None,
            due_date=due_date,
            tags=tags,
            created_at=created_at,
            updated_at=updated_at,
            body=body,
        )

    @staticmethod
    def _write_ini(cfg: configparser.ConfigParser) -> str:
        """
        Serialise a ConfigParser to a string with tab-indented key-value pairs.
        
        Extens the INI format to support multi-line values by allowing newlines 
        in values and indenting continuation lines with tabs. This allows us to 
        store lists (e.g. column order) and other complex data structures more
        naturally than trying to encode them as single-line strings.
        """
        import io
        buf = io.StringIO()
        cfg.write(buf)
        lines = []
        for line in buf.getvalue().splitlines(keepends=True):
            stripped = line.lstrip()
            if stripped and not stripped.startswith("["):
                line = "\t" + line  # preserve existing indentation (continuation lines)
            lines.append(line)
        return "".join(lines)

