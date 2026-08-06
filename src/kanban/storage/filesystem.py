from __future__ import annotations

import configparser
import logging
from os import name
import shutil
from importlib import resources
from typing import cast

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from ..models import (
    Priority,
    RELATIVE_OPS,
    ReorderOp,
    ROLE_ARCHIVE,
    Slug,
    Task,
    Board,
    Column,
)
from ..models.config import CONFIG_DEFAULTS
from ..storage.base import (
    KanbanRepository,
    relative_task_index,
    BoardNotFound,
    BoardAlreadyExists,
    ColumnAlreadyExists, 
    ColumnNotFound, 
    RepositoryAlreadyInitialized,
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
    def config_file(self) -> Path:
        return cast(Path, self.kanban_dir) / "config"

    @property
    def history_file(self) -> Path:
        return cast(Path, self.kanban_dir) / "history"

    @property
    def userdata_file(self) -> Path:
        return cast(Path, self.kanban_dir) / "userdata"

    @property
    def index_file(self) -> Path:
        return cast(Path, self.kanban_dir) / "index.db"

    @property
    def kanban_store_dir(self) -> Path:
        return self.root / ".kanban-store"

    @property
    def boards_dir(self) -> Path:
        return self.kanban_store_dir / "boards"

    @property
    def readme_file(self) -> Path:
        return self.root / "KANBAN.md"

    # ------------------------------------------------------------------
    # Initialization (setup)
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        """Return True when the kanban store exists. Local data is not required."""
        return self.kanban_store_dir.exists()

    @property
    def has_local_data(self) -> bool:
        """Return True when the local data directory exists."""
        return cast(Path, self.kanban_dir).exists()

    def init_storage(self) -> None:
        """Create the .kanban-store directory where boards and tasks are stored."""
        if self.is_initialized:
            raise RepositoryAlreadyInitialized(self.root)

        self.kanban_store_dir.mkdir()

        boards_dir = self.boards_dir
        boards_dir.mkdir()
        (boards_dir / ".metadata").touch()

        self._write_readme()

    def _write_readme(self) -> None:
        """Copy the packaged KANBAN.md into the project root.

        The file explains where the data lives and how to work with it.  It
        belongs to the user once written, so an existing one is never replaced,
        and failing to write it never fails the initialization.
        """
        if self.readme_file.exists():
            return

        try:
            source = resources.files("kanban").joinpath("KANBAN.md")
            self.readme_file.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError as exc:
            logging.warning("Failed to write %s: %s", self.readme_file, exc)

    def init_local_data(self) -> None:
        """Create the .kanban directory holding config, user data, history, and the index.

        The config file is written with the default value of every setting that
        has one, so a new repository starts from stated settings rather than
        from an empty file the user has to guess the shape of.

        Local data is machine-local and disposable, so this is idempotent: existing
        directories and files are left as they are, and a setting already carrying
        a value keeps it.
        """
        kanban_dir = cast(Path, self.kanban_dir)
        kanban_dir.mkdir(exist_ok=True)

        self.history_file.touch()
        self.config_file.touch()
        self.userdata_file.touch()
        self.index_file.touch()

        self._seed_config_defaults()

    def _seed_config_defaults(self) -> None:
        """Write the default of every setting the config file does not already carry."""
        for keypath, value in CONFIG_DEFAULTS.items():
            if self.get_config(keypath) is None:
                self.set_config(keypath, value)

    # ------------------------------------------------------------------
    # Board operations
    # ------------------------------------------------------------------

    def board_exists(self, slug: Slug) -> bool:
        board_path = self.boards_dir / slug
        return board_path.is_dir() and not slug.startswith(".")

    # TODO: SYNC - metadata must match the name and slug of the board directory

    def _board_task_counts(self, board: Slug) -> tuple[int, int]:
        """Return the board's task count and its archived task count.

        The archive column is counted apart from the rest: a board's task_count
        is the work still on the board, and what has been archived is reported
        on its own.
        """
        task_count = 0
        archived_task_count = 0

        for col in (self.boards_dir / board).iterdir():
            if not col.is_dir() or col.name.startswith("."):
                continue
            count = sum(
                1 for f in col.iterdir()
                if f.is_file() and not f.name.startswith(".")
            )
            role = self.get_column_metadata(board, Slug(col.name), "fields.role")
            if role == ROLE_ARCHIVE:
                archived_task_count += count
            else:
                task_count += count

        return task_count, archived_task_count

    def get_boards(self) -> list[Board]:
        boards = []
        for entry in sorted(self.boards_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            column_count = sum(
                1 for e in entry.iterdir()
                if e.is_dir() and not e.name.startswith(".")
            )
            board_slug = Slug(entry.name)
            task_count, archived_task_count = self._board_task_counts(board_slug)
            meta_name = self.get_board_metadata(board_slug, "fields.name")
            meta_slug = self.get_board_metadata(board_slug, "fields.slug")
            meta_uuid = self.get_board_metadata(board_slug, "fields.id")

            if meta_name is None or meta_slug is None or meta_uuid is None:
                # TODO: handle contests between directory name and metadata fields, and raise error if missing
                raise ValueError(f"Missing metadata for board {entry.name}: name={meta_name}, slug={meta_slug}, id={meta_uuid}")

            boards.append(Board(id=UUID(meta_uuid), name=meta_name, slug=Slug(meta_slug), column_count=column_count, task_count=task_count, archived_task_count=archived_task_count))
        return boards

    # TODO: SYNC - metadata must match the name and slug of the board directory
    
    def get_board(self, slug: Slug) -> Board:
        board_path = self.boards_dir / slug

        if not board_path.is_dir() or slug.startswith("."):
            raise BoardNotFound(slug)

        column_count = sum(
            1 for e in board_path.iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )
        task_count, archived_task_count = self._board_task_counts(slug)

        # board_slug = Slug(board_path.name)
        meta_name = self.get_board_metadata(slug, "fields.name")
        meta_slug = self.get_board_metadata(slug, "fields.slug")
        meta_uuid = self.get_board_metadata(slug, "fields.id")
        
        if meta_name is None or meta_slug is None or meta_uuid is None:
            # TODO: handle contests between directory name and metadata fields, and raise error if missing
            raise ValueError(f"Missing metadata for board {board_path.name}: name={meta_name}, slug={meta_slug}, id={meta_uuid}")

        return Board(id=UUID(meta_uuid), name=meta_name, slug=Slug(meta_slug), column_count=column_count, task_count=task_count, archived_task_count=archived_task_count)

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
            raise BoardNotFound(slug)
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

    # TODO: fail gracefully from corrupt metadata files (e.g. missing column in order file) instead of crashing, 
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
        for i, s in enumerate(c for c in order if c in existing):
            slug = Slug(s)
            task_count = self._column_task_count(board, slug)

            name = self.get_column_metadata(board, slug, "fields.name")
            column_slug = self.get_column_metadata(board, slug, "fields.slug")
            uuid = self.get_column_metadata(board, slug, "fields.id")
            role = self.get_column_metadata(board, slug, "fields.role")

            if not name or not column_slug or not uuid:
                # TODO: handle contests between directory name and metadata fields, and raise error if missing
                raise ValueError(f"Missing metadata for column {slug} in board {board}: name={name}, slug={column_slug}, id={uuid}")

            columns.append(Column(id=UUID(uuid), name=name, slug=Slug(column_slug), board=board, position=i, task_count=task_count, role=role or None))

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
        role = self.get_column_metadata(board, slug, "fields.role")
        # TODO: error if missing fields

        return Column(id=UUID(uuid), name=name, slug=Slug(column_slug), board=board, position=position, task_count=task_count, role=role or None)

    def create_column(self, board: Slug, name: str, slug: Slug, role: str | None = None) -> Column:
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
        self.set_column_metadata(board, slug, "fields.slug", str(slug))
        self.set_column_metadata(board, slug, "fields.id", uuid)
        if role is not None:
            self.set_column_metadata(board, slug, "fields.role", role)
        self._set_column_order(board, order)

        return Column(id=UUID(uuid), name=name, slug=slug, board=board, position=len(order) - 1, role=role)

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
                for filename in self._get_task_order(Slug(b), Slug(col)):
                    entry = col_dir / filename
                    if entry.is_file():
                        tasks.append(self._parse_task_file(entry))

        return tasks

    def get_task(self, board: Slug, column: Slug, filename: Slug) -> Task:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, column):
            raise ColumnNotFound(board, column)
        
        task_path = self.boards_dir / board / column / f"{filename}.md"
        
        if not task_path.is_file():
            raise TaskNotFound(f"{board}/{column}/{filename}")
        
        return self._parse_task_file(task_path)

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

        return self._parse_task_file(path)

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

        return self._parse_task_file(new_path)

    def move_task(self, task: Task, column: Slug, board: Slug | None = None) -> Task:
        src_board_slug = task.board
        src_column_slug = task.column
        dest_board_slug = board if board is not None else task.board
        dest_column_slug = column
        filename = f"{task.slug}.md"

        src_file = self.boards_dir / src_board_slug / src_column_slug / filename
        dest_file = self.boards_dir / dest_board_slug / dest_column_slug / filename

        if not src_file.is_file():
            raise TaskNotFound(f"{task.board}/{task.column}/{task.slug}")
        # Raises BoardNotFound of its own when the destination board is not there.
        if not self.column_exists(dest_board_slug, column):
            raise ColumnNotFound(dest_board_slug, column)

        # The board is part of where a task sits, so a task staying in a column
        # of the same name on another board is still moving.
        src_place = (src_board_slug, src_column_slug)
        dest_place = (dest_board_slug, dest_column_slug)

        if src_place != dest_place and dest_file.exists():
            raise TaskAlreadyExists(dest_board_slug, column, task.slug)

        now = datetime.now(timezone.utc)
        lines = src_file.read_text(encoding="utf-8").splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith("updated_at:"):
                lines[i] = f"updated_at: {now.isoformat()}\n"

        if src_place == dest_place:
            src_file.write_text("".join(lines), encoding="utf-8")
        else:
            dest_file.write_text("".join(lines), encoding="utf-8")
            src_file.unlink()

            src_order = self._get_task_order(src_board_slug, src_column_slug)
            if filename in src_order:
                src_order.remove(filename)
            self._set_task_order(src_board_slug, src_column_slug, src_order)

            dest_order = self._get_task_order(dest_board_slug, dest_column_slug)
            if filename not in dest_order:
                dest_order.append(filename)
            self._set_task_order(dest_board_slug, dest_column_slug, dest_order)

        return self._parse_task_file(dest_file)

    def reorder_task(self, task: Task, op: ReorderOp, relative_to: Slug | None = None) -> Task:
        board_slug = task.board
        column_slug = task.column
        filename = f"{task.slug}.md"
        order = self._get_task_order(board_slug, column_slug)

        if filename not in order:
            raise TaskNotFound(f"{task.board}/{task.column}/{task.slug}")

        current_index = order.index(filename)
        new_index = current_index

        if op == ReorderOp.UP:
            new_index = max(0, current_index - 1)
        elif op == ReorderOp.DOWN:
            new_index = min(len(order) - 1, current_index + 1)
        elif op == ReorderOp.TOP:
            new_index = 0
        elif op == ReorderOp.BOTTOM:
            new_index = len(order) - 1
        elif op in RELATIVE_OPS:
            new_index = relative_task_index(
                order,
                current_index,
                op,
                f"{relative_to}.md" if relative_to is not None else None,
                f"{task.board}/{task.column}/{relative_to}",
            )
        else:
            raise ValueError(
                f"Invalid operation '{op}': must be one of "
                f"{', '.join(repr(str(member)) for member in ReorderOp)}"
            )

        if new_index != current_index:
            order.insert(new_index, order.pop(current_index))
            self._set_task_order(board_slug, column_slug, order)

        task.updated_at = datetime.now(timezone.utc)
        self.update_task(task, task.slug)

        return self.get_task(board_slug, column_slug, task.slug)

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

    def _parse_task_file(self, path: Path) -> Task:

        def _parse_dt(raw: str) -> datetime:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

        """Parse a markdown task file with YAML frontmatter into a Task.

        board and column are derived from path's parent directories, which
        follow boards_dir/<board>/<column>/<slug>.md.
        """
        column = path.parent.name
        board = path.parent.parent.name
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
            slug=Slug(slug),
            board=Slug(board),
            column=Slug(column),
            created_by=fm.get("created_by") or None,
            assigned_to=fm.get("assigned_to") or None,
            priority=Priority(p) if (p := fm.get("priority")) else None,
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

