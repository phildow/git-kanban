"""Screens presented by the TUI."""

from .board import BoardScreen
from .board_switcher import (
    BoardChoice,
    BoardsChanged,
    BoardSwitcherScreen,
    SwitchToBoard,
)
from .column_prompt import ColumnPromptScreen
from .config import ConfigScreen
from .config_value import ConfigValueScreen
from .confirm import ConfirmScreen
from .help import HelpScreen
from .task_detail import TaskDetailScreen
from .task_form import TaskFormResult, TaskFormScreen

__all__ = [
    "BoardChoice",
    "BoardScreen",
    "BoardsChanged",
    "BoardSwitcherScreen",
    "ColumnPromptScreen",
    "ConfigScreen",
    "ConfigValueScreen",
    "SwitchToBoard",
    "ConfirmScreen",
    "HelpScreen",
    "TaskDetailScreen",
    "TaskFormResult",
    "TaskFormScreen",
]
