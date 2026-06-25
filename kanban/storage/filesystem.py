from __future__ import annotations

import configparser
from os import name
import shutil

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from models import Slug, Task, Board, Column
from storage.kanban import (
    KanbanRepository, 
    BoardNotFound, 
    BoardAlreadyExists,
    ColumnAlreadyExists, 
    ColumnNotFound, 
    TaskNotFound, 
    TaskAlreadyExists
)


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

    def board_exists(self, slug: Slug) -> bool:
        board_path = self.boards_dir / slug
        return board_path.is_dir() and not slug.startswith(".")

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
            slug = entry.name
            name = self.get_board_metadata(slug, "fields.name")
            slug = self.get_board_metadata(slug, "fields.slug")
            uuid = self.get_board_metadata(slug, "fields.id")   
            # TODO: raise error if fields missing or out of sync with directory name

            boards.append(Board(id=UUID(uuid), name=name, slug=slug, column_count=column_count, task_count=task_count))
        return boards

    # TODO: SYNC - metadata must match the name and slug of the board directory
    # TODO: load the column count and task count
    def get_board(self, slug: Slug) -> Board:
        board_path = self.boards_dir / slug

        if not board_path.is_dir() or slug.startswith("."):
            raise BoardNotFound(slug)
        
        name = self.get_board_metadata(slug, "fields.name")
        slug = self.get_board_metadata(slug, "fields.slug")
        uuid = self.get_board_metadata(slug, "fields.id")
        # TODO: raise error if fields missing or out of sync with directory name

        return Board(id=UUID(uuid), name=name, slug=slug)

    def create_board(self, name: str, slug: Slug) -> Board:
        uuid = str(uuid4())

        if self.board_exists(slug):
            raise BoardAlreadyExists(name)

        (self.boards_dir / slug).mkdir()
        (self.boards_dir / slug / ".metadata").touch()
        
        self.set_board_metadata(slug, "fields.name", name)
        self.set_board_metadata(slug, "fields.slug", slug)
        self.set_board_metadata(slug, "fields.id", uuid)

        return Board(id=UUID(uuid), name=name, slug=slug)

    def rename_board(self, slug: Slug, new_name: str, new_slug: Slug) -> Board:
        if not self.board_exists(slug):
            raise BoardNotFound(name)
        if self.board_exists(new_slug):
            raise BoardAlreadyExists(new_name)
        
        (self.boards_dir / slug).rename(self.boards_dir / new_slug)

        self.set_board_metadata(new_slug, "fields.name", new_name)
        self.set_board_metadata(new_slug, "fields.slug", new_slug)

        uuid = self.get_board_metadata(new_slug, "fields.id")
        # TODO: raise error if no UUID

        return Board(id=UUID(uuid), name=new_name, slug=new_slug)

    def delete_board(self, slug: Slug) -> None:
        if not self.board_exists(slug):
            raise BoardNotFound(slug )
        shutil.rmtree(self.boards_dir / slug)

    # ------------------------------------------------------------------
    # Columns operations
    # ------------------------------------------------------------------

    # TODO: fail gracefully from corrupt metadta files (e.g. missing column in order file) instead of crashing, 
    #       and log warnings to help users fix them
    # TODO: verify that the files listed in the sort order match the actual column directories and log warnings 
    #       if not, and handle missing columns by appending them to the end of the list rather than crashing
    
    # TODO: move these methods

    def _get_task_order(self, board: Slug, column: Slug) -> list[str]:
        """Return the stored task order for a column, falling back to filesystem sort."""
        raw = self.get_column_metadata(board, column, "tasks.order")

        if raw:
            return [f.strip() for f in raw.split("\n") if f.strip()]
        return sorted(
            e.name for e in (self.boards_dir / board / column).iterdir()
            if e.is_file() and not e.name.startswith(".") and e.suffix == ".md"
        )

    def _set_task_order(self, board: Slug, column: Slug, order: list[str]) -> None:
        """Persist the task order for a column to its .metadata file.

        Each filename is stored on its own line using configparser's multi-line
        value support: continuation lines are indented, so configparser treats
        them as part of the same value rather than new keys.
        """
        self.set_column_metadata(board, column, "tasks.order", "\n" + "\n".join(order))

    def _get_column_order(self, board: Slug) -> list[str]:
        """Return the stored column order for a board, falling back to filesystem sort."""
        raw = self.get_board_metadata(board, "columns.order")
        if raw:
            return [c.strip() for c in raw.split("\n") if c.strip()]
        return sorted(
            e.name for e in (self.boards_dir / board).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )

    def _set_column_order(self, board: Slug, order: list[str]) -> None:
        """Persist the column order for a board to its metadata file.

        Each directory name is stored on its own line using configparser's
        multi-line value support: continuation lines are indented, so
        configparser treats them as part of the same value rather than new keys.
        """
        self.set_board_metadata(board, "columns.order", "\n" + "\n".join(order))

    def _column_task_count(self, board: Slug, column: Slug) -> int:
        """Return the number of tasks in a column."""
        return sum(
            1 for e in (self.boards_dir / board / column).iterdir()
            if e.is_file() and not e.name.startswith(".")
        )

    def column_exists(self, board: Slug, slug: Slug) -> bool:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        
        column_path = self.boards_dir / board / slug
        return column_path.is_dir() and not slug.startswith(".")

    def get_columns(self, board: Slug) -> list[Column]:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        
        existing = {
            e.name for e in (self.boards_dir / board).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        }
        
        order = self._get_column_order(board)
         
        columns = []
        for i, slug in enumerate(c for c in order if c in existing):
            task_count = self._column_task_count(board, slug)

            name = self.get_column_metadata(board, slug, "fields.name") or slug
            column_slug = self.get_column_metadata(board, slug, "fields.slug") or slug
            uuid = self.get_column_metadata(board, slug, "fields.id")
            # TODO: error if fields missing

            columns.append(Column(id=UUID(uuid), name=name, slug=column_slug, board=board, position=i, task_count=task_count))
            
        return columns

    def get_column(self, board: Slug, slug: Slug) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)

        column_path = self.boards_dir / board / slug

        if not column_path.is_dir() or slug.startswith("."):
            raise ColumnNotFound(board, slug)

        task_count = self._column_task_count(board, slug)
        order = self._get_column_order(board)
        position = order.index(slug) if slug in order else len(order)

        name = self.get_column_metadata(board, slug, "fields.name") or slug
        column_slug = self.get_column_metadata(board, slug, "fields.slug") or slug
        uuid = self.get_column_metadata(board, slug, "fields.id")
        # TODO: error if missing fields

        return Column(id=UUID(uuid), name=name, slug=column_slug, board=board, position=position, task_count=task_count)

    def create_column(self, board: Slug, name: str, slug: Slug) -> Column:
        uuid = str(uuid4())

        if not self.board_exists(board):
            raise BoardNotFound(board)
        
        column_path = self.boards_dir / board / slug
        
        if column_path.exists():
            raise ColumnAlreadyExists(board, name)
        
        order = self._get_column_order(board)
        column_path.mkdir()
        (column_path / ".metadata").touch()
        order.append(slug)
        
        self.set_column_metadata(board, slug, "fields.name", name)
        self.set_column_metadata(board, slug, "fields.slug", slug)
        self.set_column_metadata(board, slug, "fields.id", uuid)
        self._set_column_order(board, order)

        return Column(id=UUID(uuid), name=name, slug=slug, board=board, position=len(order) - 1)

    def rename_column(self, board: Slug, slug: Slug, new_name: str, new_slug: Slug) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, slug):
            raise ColumnNotFound(board, slug)
        if self.column_exists(board, new_slug):
            raise ColumnAlreadyExists(board, new_name)
        
        (self.boards_dir / board / slug).rename(self.boards_dir / board / new_slug)
        order = self._get_column_order(board)
        
        if slug in order:
            order[order.index(slug)] = new_slug
        
        self.set_column_metadata(board, new_slug, "fields.name", new_name)
        self.set_column_metadata(board, new_slug, "fields.slug", new_slug)
        self._set_column_order(board, order)

        return self.get_column(board, new_slug)

    def reorder_column(self, board: Slug, slug: Slug, position: int) -> list[Column]:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, slug):
            raise ColumnNotFound(board, slug)
        
        order = self._get_column_order(board)
        
        if slug in order:
            order.remove(slug)
        order.insert(max(0, min(position, len(order))), slug)
        
        self._set_column_order(board, order)
        return self.get_columns(board)

    def delete_column(self, board: Slug, slug: Slug) -> None:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, slug):
            raise ColumnNotFound(board, slug)
        
        order = self._get_column_order(board)
        
        if slug in order:
            order.remove(slug)
        
        self._set_column_order(board, order)
        shutil.rmtree(self.boards_dir / board / slug)

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------
    
    def task_exists(self, board: Slug, column: Slug, slug: Slug) -> bool:
        path = self.boards_dir / board / column / f"{slug}.md"
        return path.is_file()

    def get_tasks(self, board: Slug | None = None, column: Slug | None = None ) -> list[Task]:
        if board is None and column is not None:
            raise ValueError("Cannot filter by column without a board: {}".format(column))

        if board is not None and not self.board_exists(board):
            raise BoardNotFound(board)
        if board is not None and column is not None and not self.column_exists(board, column):
            raise ColumnNotFound(board, column)

        tasks: list[Task] = []

        boards = [board] if board is not None else [
            e.name for e in sorted(self.boards_dir.iterdir())
            if e.is_dir() and not e.name.startswith(".")
        ]

        for b in boards:
            columns = [column] if column is not None else [
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
                        tasks.append(self._parse_task_file(entry, b, col))

        return tasks

    def get_task(self, board: Slug, column: Slug, filename: Slug) -> Task:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, column):
            raise ColumnNotFound(board, column)
        
        task_path = self.boards_dir / board / column / f"{filename}.md"
        
        if not task_path.is_file():
            raise TaskNotFound(f"{board}/{column}/{filename}")
        
        return self._parse_task_file(task_path, board, column)

    def create_task(self, task: Task, slug: Slug) -> Task:
        column_slug = task.column
        board_slug = task.board

        if not self.board_exists(board_slug):
            raise BoardNotFound(task.board)
        if not self.column_exists(board_slug, column_slug):
            raise ColumnNotFound(task.board, task.column)
        if self.task_exists(board_slug, column_slug, slug):
            raise TaskAlreadyExists(task.board, task.column, slug)
        
        path = self.boards_dir / board_slug / column_slug / f"{slug}.md"
        now = datetime.now(timezone.utc)
        fm_lines = [
            "---",
            f"id: {task.id}",
            f"title: {task.title}",
            f"slug: {slug}",
            f"created_at: {(task.created_at or now).isoformat()}",
            f"updated_at: {(task.updated_at or now).isoformat()}",
        ]
        
        if task.priority:
            fm_lines.append(f"priority: {task.priority}")
        if task.assigned_to:
            fm_lines.append(f"assigned_to: {task.assigned_to}")
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
        
        if f"{slug}.md" not in order:
            order.append(f"{slug}.md")
        self._set_task_order(board_slug, column_slug, order)

        return self._parse_task_file(path, task.board, task.column)

    def update_task(self, task: Task, slug: Slug) -> Task:
        board_slug = task.board
        column_slug = task.column
        current_filename = f"{slug}.md"
        current_path = self.boards_dir / board_slug / column_slug / current_filename

        if not current_path.is_file():
            raise TaskNotFound(f"{task.board}/{task.column}/{slug}")

        new_slug = task.slug
        new_filename = f"{new_slug}.md"
        new_path = self.boards_dir / board_slug / column_slug / new_filename
        renamed = new_slug != slug

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
        if task.assigned_to:
            fm_lines.append(f"assigned_to: {task.assigned_to}")
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

    def move_task(self, task: Task, column: Slug) -> Task:
        board_slug = task.board
        src_column_slug = task.column
        dest_column_slug = column
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
        board_slug = task.board
        column_slug = task.column
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
    
    def _board_name_from_slug(self, slug: Slug) -> str:
        """Return the board name from its slug, falling back to the slug if not found."""
        return self.get_board_metadata(slug, "fields.name") or slug
    
    def _column_name_from_slug(self, board_slug: Slug, column_slug: Slug) -> str:
        """Return the column name from its slug, falling back to the slug if not found."""
        return self.get_column_metadata(board_slug, column_slug, "fields.name") or column_slug

    def _board_metadata_file(self, board: Slug) -> Path:
        """Return the path to the .metadata INI file for the given board.""" 
        return self.boards_dir / board / ".metadata"

    def get_board_metadata(self, board: Slug, keypath: str) -> str | None:
        """Read a value from a board's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self._board_metadata_file(board), encoding="utf-8")

        if section not in cfg or key not in cfg[section]:
            return None

        return cfg[section][key]

    def set_board_metadata(self, board: Slug, keypath: str, value: str | None) -> None:
        """Write a value to a board's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")
        
        section, key = keypath.split(".", 1)
        metadata_file = self._board_metadata_file(board)
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

    def _column_metadata_file(self, board: Slug, column: Slug) -> Path:
        """Return the path to the .metadata INI file for the given column."""
        return self.boards_dir / board / column / ".metadata"

    def get_column_metadata(self, board: Slug, column: Slug, keypath: str) -> str | None:
        """Read a value from a column's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")
        
        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self._column_metadata_file(board, column), encoding="utf-8")
        
        if section not in cfg or key not in cfg[section]:
            return None
        
        return cfg[section][key]

    def set_column_metadata(self, board: Slug, column: Slug, keypath: str, value: str | None) -> None:
        """Write a value to a column's .metadata INI file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")
        section, key = keypath.split(".", 1)
        metadata_file = self._column_metadata_file(board, column)
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

    def _parse_task_file(self, path: Path, board: Slug, column: Slug) -> Task:
        
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
            assigned_to=fm.get("assigned_to") or None,
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

