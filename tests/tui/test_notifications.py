"""Tests for `tui.notifications`: which toasts the setting lets through."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import (
    CONFIG_TUI_NOTIFICATIONS,
    KanbanService,
    NOTIFICATIONS_ALL,
    NOTIFICATIONS_ERRORS,
    NOTIFICATIONS_NONE,
)
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp


def _make_service(setting: str | None = None) -> KanbanService:
    """Return a service over one board, with `setting` configured when given."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "To Do", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    if setting is not None:
        svc.set_config(CONFIG_TUI_NOTIFICATIONS, setting)

    return svc


class TestNotificationsAll(unittest.IsolatedAsyncioTestCase):
    """`all`, and an unset setting, show every notification."""

    async def test_all_shows_an_information_notification(self) -> None:
        """An informational toast is shown when every notification is wanted."""
        app = KanbanApp(_make_service(NOTIFICATIONS_ALL))

        async with app.run_test() as pilot:
            app.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 1)

    async def test_all_shows_an_error_notification(self) -> None:
        """An error toast is shown when every notification is wanted."""
        app = KanbanApp(_make_service(NOTIFICATIONS_ALL))

        async with app.run_test() as pilot:
            app.notify("broke", severity="error")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 1)

    async def test_unrecognised_setting_shows_the_notification(self) -> None:
        """
        A value the app does not know is not read as a reason to stay quiet.

        The service refuses to store one, so it is written straight to the
        repository here — the way it would arrive, from a config file edited by
        hand.
        """
        svc = _make_service()
        svc.repository.set_config(CONFIG_TUI_NOTIFICATIONS, "sometimes")
        app = KanbanApp(svc)

        async with app.run_test() as pilot:
            app.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 1)


class TestNotificationsErrors(unittest.IsolatedAsyncioTestCase):
    """`errors` shows what went wrong and passes over the rest."""

    async def test_errors_shows_an_error_notification(self) -> None:
        """A failed command still reaches the user."""
        app = KanbanApp(_make_service(NOTIFICATIONS_ERRORS))

        async with app.run_test() as pilot:
            app.notify("broke", severity="error")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 1)

    async def test_errors_hides_an_information_notification(self) -> None:
        """A report of something that worked is not shown."""
        app = KanbanApp(_make_service(NOTIFICATIONS_ERRORS))

        async with app.run_test() as pilot:
            app.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)

    async def test_errors_hides_a_warning_notification(self) -> None:
        """A warning is not an error, so it is not shown either."""
        app = KanbanApp(_make_service(NOTIFICATIONS_ERRORS))

        async with app.run_test() as pilot:
            app.notify("careful", severity="warning")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)


class TestNotificationsNone(unittest.IsolatedAsyncioTestCase):
    """`none` shows nothing at all."""

    async def test_none_hides_an_information_notification(self) -> None:
        """An informational toast is withheld."""
        app = KanbanApp(_make_service(NOTIFICATIONS_NONE))

        async with app.run_test() as pilot:
            app.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)

    async def test_none_hides_an_error_notification(self) -> None:
        """Even an error is withheld: the setting is asked for by name."""
        app = KanbanApp(_make_service(NOTIFICATIONS_NONE))

        async with app.run_test() as pilot:
            app.notify("broke", severity="error")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)

    async def test_a_screen_notification_is_hidden_too(self) -> None:
        """A notification raised by a screen goes through the same gate."""
        app = KanbanApp(_make_service(NOTIFICATIONS_NONE))

        async with app.run_test() as pilot:
            app.screen.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)


class TestNotificationsRereadPerCall(unittest.IsolatedAsyncioTestCase):
    """The setting is read on each notification, never cached at startup."""

    async def test_a_change_takes_effect_without_a_restart(self) -> None:
        """Turning notifications off mid-session silences the next one."""
        svc = _make_service(NOTIFICATIONS_ALL)
        app = KanbanApp(svc)

        async with app.run_test() as pilot:
            svc.set_config(CONFIG_TUI_NOTIFICATIONS, NOTIFICATIONS_NONE)
            app.notify("hello")
            await pilot.pause()

            self.assertEqual(len(app._notifications), 0)
