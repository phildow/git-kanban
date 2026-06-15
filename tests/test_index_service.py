"""Tests for index service scaffolding and basic behaviors."""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

from services.index_service import IndexService


class TestIndexService(unittest.TestCase):
    """Contract tests for the index service wrapper."""

    def setUp(self) -> None:
        self.repository = MagicMock()
        self.service = IndexService(self.repository)

    def test_rebuild_sets_index_built_state(self):
        """`rebuild()` updates the in-memory index build timestamp."""
        self.service.rebuild()
        state = self.service.get_state()
        self.assertTrue(state.exists)
        self.assertIsNotNone(state.built_at)

    def test_get_state_reports_missing_index(self):
        """`get_state()` reports non-existent index before first rebuild."""
        state = self.service.get_state()

        self.assertIsNone(state.built_at)
        self.assertFalse(state.exists)

    def test_get_state_reports_existing_index(self):
        """`get_state()` reports existing index after rebuild."""
        self.service.rebuild()

        state = self.service.get_state()

        self.assertIsNotNone(state.built_at)
        self.assertTrue(state.exists)

    def test_is_fresh_false_when_index_missing(self):
        """`is_fresh()` returns False when index has never been built."""
        self.assertFalse(self.service.is_fresh(max_age_seconds=60))

    def test_is_fresh_true_immediately_after_rebuild(self):
        """`is_fresh()` returns True when checked right after rebuild."""
        self.service.rebuild()
        self.assertTrue(self.service.is_fresh(max_age_seconds=60))

    def test_is_fresh_false_for_stale_index(self):
        """`is_fresh()` returns False for index older than max age."""
        self.service._built_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        self.assertFalse(self.service.is_fresh(max_age_seconds=60))

    def test_update_is_scaffold_noop(self):
        """`update()` is a scaffold no-op and accepts a task argument."""
        task = object()
        self.service.update(task)

    def test_delete_is_scaffold_noop(self):
        """`delete()` is a scaffold no-op and accepts a task argument."""
        task = object()
        self.service.delete(task)


if __name__ == "__main__":
    unittest.main()
