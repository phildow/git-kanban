"""Bootstrap seed data for a fresh kanban store."""

from __future__ import annotations

from typing import TypedDict

from ..models import Slug

class BootstrapSeed(TypedDict, total=False):
    """A single task entry in a bootstrap column. title and slug are required."""
    title:       str       # required
    slug:        str        # required
    priority:    str
    assigned_to: str
    body:        str


class BootstrapColumn(TypedDict, total=False):
    """A column entry in a bootstrap board. name and slug are required."""
    name:   str        # required
    slug:   str        # required
    tasks:  list[BootstrapSeed]


class BootstrapBoard(TypedDict, total=False):
    """A board entry in a bootstrap config. name and slug are required."""
    name:    str        # required
    slug:    str        # required
    columns: list[BootstrapColumn]


class BootstrapConfig(TypedDict, total=False):
    """Full configuration for bootstrapping a new repository."""
    boards:      list[BootstrapBoard]
    usercontext: dict[str, str]


DEFAULT_COLUMNS: list[tuple[str, Slug]] = [
    ("To Do", "todo"),
    ("In Progress", "in-progress"),
    ("In Review", "in-review"),
    ("Done", "done"),
]

BOOTSTRAP_CONFIG: BootstrapConfig = {
    "usercontext": {
        "board": "main",
        "column": "todo",
    },
    "boards": [
        {
            "name": "Main",
            "slug": "main",
            "columns": [
                {
                    "name": "To Do",
                    "slug": "todo",
                    "tasks": [
                        {
                            "title": "List your boards and tasks",
                            "slug": "list-your-boards-and-tasks",
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
                            "slug": "create-a-new-task",
                            "body": (
                                "Create a task in the current column with `new task`:\n\n"
                                '    new task "Fix the login bug"\n'
                                '    new task "Write API docs" --priority high --assigned-to Alice'
                            ),
                        },
                        {
                            "title": "Move a task to another column",
                            "slug": "move-a-task-to-another-column",
                            "body": (
                                "Move a task to another column with `mv`:\n\n"
                                '    mv "fix the login bug" in-progress\n'
                                '    mv "fix the login bug" /main/in-review'
                            ),
                        },
                    ],
                },
                {
                    "name": "In Progress",
                    "slug": "in-progress",
                    "tasks": [
                        {
                            "title": "Update a task with details",
                            "slug": "update-a-task-with-details",
                            "priority": "high",
                            "assigned_to": "Alice",
                            "body": (
                                "Update a task's metadata with `update`:\n\n"
                                '    update "update a task with details" --priority medium --assigned-to Bob\n'
                                '    update "update a task with details" --tag Bug --due-date 2026-07-01'
                            ),
                        },
                    ],
                },
                {
                    "name": "In Review",
                    "slug": "in-review",
                    "tasks": [],
                },
                {
                    "name": "Done",
                    "slug": "done",
                    "tasks": [
                        {
                            "title": "Go for a bike ride",
                            "slug": "go-for-a-bike-ride",
                        },
                    ],
                },
            ],
        },
    ],
}
