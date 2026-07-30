"""Screens presented by the TUI."""

from .board import BoardScreen
from .board_form import BoardFormScreen
from .board_switcher import (
    BoardChoice,
    BoardSwitcherScreen,
    CreateBoard,
    SwitchToBoard,
)
from .confirm import ConfirmScreen
from .help import HelpScreen
from .output import OutputScreen
from .task_detail import TaskDetailScreen
from .task_form import TaskFormResult, TaskFormScreen

__all__ = [
    "BoardChoice",
    "BoardFormScreen",
    "BoardScreen",
    "BoardSwitcherScreen",
    "CreateBoard",
    "SwitchToBoard",
    "ConfirmScreen",
    "HelpScreen",
    "OutputScreen",
    "TaskDetailScreen",
    "TaskFormResult",
    "TaskFormScreen",
]
