"""Seed data for a fresh kanban store.

`DEFAULT_CONFIG` is what every new repository is initialized with: the main
board with its default columns and no tasks.  `BOOTSTRAP_CONFIG` is the same
board with the example tasks `init --bootstrap` adds.
"""

from __future__ import annotations

from typing import TypedDict

from ..models import ARCHIVE_COLUMN_NAME, ARCHIVE_COLUMN_SLUG, ROLE_ARCHIVE, Slug

class BootstrapSeed(TypedDict, total=False):
    """A single task entry in a bootstrap column. title and slug are required."""
    title:       str     # required
    slug:        Slug    # required
    priority:    str
    assigned_to: str
    body:        str


class BootstrapColumn(TypedDict, total=False):
    """A column entry in a bootstrap board. name and slug are required."""
    name:   str         # required
    slug:   Slug        # required
    role:   str
    tasks:  list[BootstrapSeed]


class BootstrapBoard(TypedDict, total=False):
    """A board entry in a bootstrap config. name and slug are required."""
    name:    str        # required
    slug:    Slug       # required
    columns: list[BootstrapColumn]


class BootstrapConfig(TypedDict, total=False):
    """Full configuration for bootstrapping a new repository."""
    boards:      list[BootstrapBoard]
    usercontext: dict[str, str]


MAIN_BOARD_NAME: str = "Main"
MAIN_BOARD_SLUG: Slug = Slug("main")

DEFAULT_COLUMNS: list[tuple[str, Slug]] = [
    ("To Do", Slug("todo")),
    ("In Progress", Slug("in-progress")),
    ("In Review", Slug("in-review")),
    ("Done", Slug("done")),
]

# Every board ends with an archive column.  It is not one of the default
# columns because it is not a step in the workflow and is created whatever
# columns a board is asked for.
ARCHIVE_COLUMN: tuple[str, Slug] = (ARCHIVE_COLUMN_NAME, ARCHIVE_COLUMN_SLUG)


def default_board(
    name: str,
    slug: Slug,
    tasks: dict[Slug, list[BootstrapSeed]] | None = None,
) -> BootstrapBoard:
    """
    Return a board config carrying the default columns and the archive last.

    `tasks` places seed tasks in the column named by its key; a column absent
    from it is created empty.
    """
    seeds = tasks or {}

    columns: list[BootstrapColumn] = [
        {"name": col_name, "slug": col_slug, "tasks": seeds.get(col_slug, [])}
        for col_name, col_slug in DEFAULT_COLUMNS
    ]

    archive_name, archive_slug = ARCHIVE_COLUMN
    columns.append({
        "name": archive_name,
        "slug": archive_slug,
        "role": ROLE_ARCHIVE,
        "tasks": seeds.get(archive_slug, []),
    })

    return {"name": name, "slug": slug, "columns": columns}


# The main board every repository is initialized with, without example tasks.
DEFAULT_CONFIG: BootstrapConfig = {
    "usercontext": {
        "board": MAIN_BOARD_SLUG,
    },
    "boards": [
        default_board(MAIN_BOARD_NAME, MAIN_BOARD_SLUG),
    ],
}

# The example tasks `init --bootstrap` adds to the main board, by column.
BOOTSTRAP_SEEDS: dict[Slug, list[BootstrapSeed]] = {
    Slug("todo"): [
        {
            "title": "List your boards and tasks",
            "slug": Slug("list-your-boards-and-tasks"),
            "body": (
                "Use `ls` to list tasks in the current context."
                " Navigate with `cd`:\n\n"
                "    cd /main\n"
                "    ls\n\n"
                "    cd /main/todo\n"
                "    ls"
            ),
        },
        {
            "title": "Create a new task",
            "slug": Slug("create-a-new-task"),
            "body": (
                "Create a task in the current column with `new task`:\n\n"
                '    new task "Fix the login bug"\n'
                '    new task "Write API docs" --priority high --assigned-to Alice'
            ),
        },
        {
            "title": "Move a task to another column",
            "slug": Slug("move-a-task-to-another-column"),
            "body": (
                "Move a task to another column with `mv`:\n\n"
                '    mv "fix the login bug" in-progress\n'
                '    mv "fix the login bug" /main/in-review'
            ),
        },
    ],
    Slug("in-progress"): [
        {
            "title": "Update a task with details",
            "slug": Slug("update-a-task-with-details"),
            "priority": "high",
            "assigned_to": "Alice",
            "body": (
                "Update a task's metadata with `update`:\n\n"
                '    update "update a task with details" --priority medium --assigned-to Bob\n'
                '    update "update a task with details" --tag Bug --due-date 2026-07-01'
            ),
        },
    ],
    Slug("done"): [
        {
            "title": "Go for a bike ride",
            "slug": Slug("go-for-a-bike-ride"),
        },
    ],
}

BOOTSTRAP_CONFIG: BootstrapConfig = {
    "usercontext": {
        "board": MAIN_BOARD_SLUG,
    },
    "boards": [
        default_board(MAIN_BOARD_NAME, MAIN_BOARD_SLUG, BOOTSTRAP_SEEDS),
    ],
}
