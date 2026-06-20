from __future__ import annotations

import configparser
import logging
import shutil

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from models import Task, TaskFilter, Board, Column, UserContext
from storage.kanban import KanbanRepository, BoardNotFound, BoardAlreadyExists, ColumnAlreadyExists, ColumnNotFound, TaskNotFound


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
    def index_file(self) -> Path:
        return self.kanban_dir / "index.db"

    # ------------------------------------------------------------------
    # Bootstrap and initialization
    # ------------------------------------------------------------------

    # Bootstrap
    def init_storage(self, default_board: str = "main", default_column: str = "todo") -> None:
        if self.is_initialized:
            raise ValueError("Kanban is already initialized")

        kanban_dir = self.kanban_dir
        kanban_dir.mkdir()
        (kanban_dir / "history").touch()
            
        kanban_store_dir = self.kanban_store_dir
        kanban_store_dir.mkdir()

        cfg = configparser.ConfigParser()
        cfg["user-context"] = {"board": default_board, "column": default_column}
        self.config_file.write_text(self._write_config(cfg), encoding="utf-8")
        
        self.index_file.touch()

        boards_dir = self.boards_dir
        boards_dir.mkdir()
        (boards_dir / ".metadata").touch()

    # TODO: improve boostrapping with more frontmatter metadata and sample tasks, 
    #       use existing methods to create them instead of writing files directly, 
    #       which will ensure consistency and proper indexing
    def bootstrap(self) -> list[Task]:
        self.create_board("main")
        for col in ("todo", "in-progress", "in-review", "done"):
            self.create_column("main", col)

        now = datetime.now(timezone.utc)
        seeds = [
            ("create your first todo", "create-your-first-todo", "todo"),
            ("go for a bike ride", "go-for-a-bike-ride", "in-progress"),
        ]
        created: list[Task] = []
        for title, slug, column in seeds:
            task_id = uuid4()
            path = self.boards_dir / "main" / column / f"{slug}.md"
            path.write_text(
                f"---\n"
                f"id: {task_id}\n"
                f"title: {title}\n"
                f"slug: {slug}\n"
                f"created_at: {now.isoformat()}\n"
                f"updated_at: {now.isoformat()}\n"
                f"---\n",
                encoding="utf-8",
            )
            created.append(self._parse_task_file(path, "main", column))
        return created

    @property
    def is_initialized(self) -> bool:
        return self.kanban_dir.exists() and self.kanban_store_dir.exists()

    # Board operations
    def get_boards(self) -> list[Board]:
        return [
            Board(name=entry.name)
            for entry in sorted(self.boards_dir.iterdir())
            if entry.is_dir() and not entry.name.startswith(".")
        ]

    def get_board(self, name: str) -> Board:
        board_path = self.boards_dir / name
        if not board_path.is_dir() or name.startswith("."):
            raise BoardNotFound(name)
        return Board(name=name)

    def board_exists(self, name: str) -> bool:
        board_path = self.boards_dir / name
        return board_path.is_dir() and not name.startswith(".")

    def create_board(self, name: str) -> Board:
        if self.board_exists(name):
            raise BoardAlreadyExists(name)
        (self.boards_dir / name).mkdir()
        return Board(name=name, columns=[])

    def rename_board(self, name: str, new_name: str) -> Board:
        if not self.board_exists(name):
            raise BoardNotFound(name)
        if self.board_exists(new_name):
            raise BoardAlreadyExists(new_name)
        (self.boards_dir / name).rename(self.boards_dir / new_name)
        return Board(name=new_name)

    def delete_board(self, name: str) -> None:
        if not self.board_exists(name):
            raise BoardNotFound(name)
        shutil.rmtree(self.boards_dir / name)

    # Column operations
    def get_columns(self, board: str) -> list[Column]:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        board_path = self.boards_dir / board
        return [
            Column(name=entry.name, board=board, position=i)
            for i, entry in enumerate(sorted(board_path.iterdir()))
            if entry.is_dir() and not entry.name.startswith(".")
        ]

    # TODO: implement sorted in a metadata file to avoid relying on filesystem ordering
    def get_column(self, board: str, name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        if not column_path.is_dir() or name.startswith("."):
            raise ColumnNotFound(board, name)
        task_count = sum(
            1 for e in column_path.iterdir()
            if e.is_file() and not e.name.startswith(".")
        )
        siblings = sorted(
            e.name for e in (self.boards_dir / board).iterdir()
            if e.is_dir() and not e.name.startswith(".")
        )
        position = siblings.index(name)
        return Column(name=name, board=board, position=position, task_count=task_count)

    def column_exists(self, board: str, name: str) -> bool:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        return column_path.is_dir() and not name.startswith(".")

    def create_column(self, board: str, name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        column_path = self.boards_dir / board / name
        if column_path.exists():
            raise ColumnAlreadyExists(board, name)
        column_path.mkdir()
        position = len([e for e in (self.boards_dir / board).iterdir() if e.is_dir() and not e.name.startswith(".")]) - 1
        return Column(name=name, board=board, position=position)

    def rename_column(self, board: str, name: str, new_name: str) -> Column:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, name):
            raise ColumnNotFound(board, name)
        if self.column_exists(board, new_name):
            raise ColumnAlreadyExists(board, new_name)
        (self.boards_dir / board / name).rename(self.boards_dir / board / new_name)
        return self.get_column(board, new_name)

    def reorder_column(self, board: str, name: str, position: int) -> list[Column]:
        raise NotImplementedError()

    def delete_column(self, board: str, name: str) -> None:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, name):
            raise ColumnNotFound(board, name)
        shutil.rmtree(self.boards_dir / board / name)

    # Task operations
    def get_tasks(
        self,
        board: Optional[str] = None,
        column: Optional[str] = None,
        filter: Optional[TaskFilter] = None,
    ) -> list[Task]:

        # if board and not column, return all the tasks in that board across all columns, applying filter if provided
        # if board and column, return all the tasks in that column, applying filter if provided
        # if no board, return all tasks across all boards and columns, applying filter if provided
        # if no board and column, raise an error since we don't want to return all tasks without at least a board filter to limit scope

        if board is None and column is not None:
            raise ValueError("Cannot filter by column without a board: {}".format(column))

        if board is not None and not self.board_exists(board):
            raise BoardNotFound(board)
        if board is not None and column is not None and not self.column_exists(board, column):
            raise ColumnNotFound(board, column)

        if board is not None:
            boards = [board]
        else:
            boards = [e.name for e in sorted(self.boards_dir.iterdir()) if e.is_dir() and not e.name.startswith(".")]

        tasks: list[Task] = []

        for b in boards:
            columns = [column] if column is not None else [e.name for e in sorted((self.boards_dir / b).iterdir()) if e.is_dir() and not e.name.startswith(".")]
            for col in columns:
                col_path = self.boards_dir / b / col
                for entry in sorted(col_path.iterdir()):
                    if not entry.is_file() or entry.name.startswith(".") or entry.suffix != ".md":
                        continue
                    task = self._parse_task_file(entry, b, col)
                    if filter is not None and not self._task_matches_filter(task, filter):
                        continue
                    tasks.append(task)
        return tasks

    def get_task_by_id(self, task_id: UUID) -> Task:
        raise NotImplementedError()

    def get_task(self, board: str, column: str, filename: str) -> Task:
        if not self.board_exists(board):
            raise BoardNotFound(board)
        if not self.column_exists(board, column):
            raise ColumnNotFound(board, column)
        task_path = self.boards_dir / board / column / f"{filename}.md"
        if not task_path.is_file():
            raise TaskNotFound(f"{board}/{column}/{filename}")
        return self._parse_task_file(task_path, board, column)

    def task_exists(self, board: str, column: str, filename: str) -> bool:
        raise NotImplementedError()

    def create_task(self, task: Task, filename: str) -> Task:
        raise NotImplementedError()

    def update_task(self, task: Task) -> Task:
        raise NotImplementedError()

    def move_task(self, task_id: UUID, dest_board: str, dest_column: str) -> Task:
        raise NotImplementedError()

    def delete_task(self, task_id: UUID) -> None:
        raise NotImplementedError()

    # Search
    def search_tasks(self, query: str, filter: Optional[TaskFilter] = None) -> list[Task]:
        raise NotImplementedError()

    # Config
    def get_config(self, keypath: str) -> Optional[str]:
        """Read a value from the INI config file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.config_file, encoding="utf-8")

        if section not in cfg:
            raise KeyError(f"Config section '{section}' not found")
        if key not in cfg[section]:
            raise KeyError(f"Config key '{key}' not found in section '{section}'")

        return cfg[section][key]

    def set_config(self, keypath: str, value: str | None) -> None:
        """Write a value to the INI config file using a 'section.key' keypath."""
        if "." not in keypath:
            raise KeyError(f"Invalid keypath '{keypath}': expected 'section.key' format")

        section, key = keypath.split(".", 1)
        cfg = configparser.ConfigParser()
        cfg.read(self.config_file, encoding="utf-8")

        if value is None:
            if key in cfg[section]:
                del cfg[section][key]
        else:
            cfg[section][key] = value
            
        self.config_file.write_text(self._write_config(cfg), encoding="utf-8")


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
    def _write_config(cfg: configparser.ConfigParser) -> str:
        """Serialise a ConfigParser to a string."""
        import io
        buf = io.StringIO()
        cfg.write(buf)
        return buf.getvalue()

    def _task_matches_filter(self, task: Task, filter: TaskFilter) -> bool:
        """Return True if the task satisfies all non-None filter criteria."""
        if filter.assignee is not None and task.assignee != filter.assignee:
            return False
        if filter.priority is not None and task.priority != filter.priority:
            return False
        if filter.tag is not None and filter.tag not in task.tags:
            return False
        if filter.created_by is not None and task.created_by != filter.created_by:
            return False
        if filter.due_before is not None and (task.due_date is None or task.due_date >= filter.due_before):
            return False
        if filter.due_after is not None and (task.due_date is None or task.due_date <= filter.due_after):
            return False
        return True
