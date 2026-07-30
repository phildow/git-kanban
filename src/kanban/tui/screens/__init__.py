"""Screens presented by the TUI."""

from .board import BoardScreen
from .board_switcher import BoardSwitcherScreen
from .confirm import ConfirmScreen
from .help import HelpScreen
from .output import OutputScreen
from .task_detail import TaskDetailScreen
from .task_form import TaskFormResult, TaskFormScreen

__all__ = [
    "BoardScreen",
    "BoardSwitcherScreen",
    "ConfirmScreen",
    "HelpScreen",
    "OutputScreen",
    "TaskDetailScreen",
    "TaskFormResult",
    "TaskFormScreen",
]
