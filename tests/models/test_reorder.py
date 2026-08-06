"""Tests for the ReorderOp enum and the flags it is read from."""

import unittest

from kanban.models import RELATIVE_OPS, ReorderOp


class TestReorderOpValues(unittest.TestCase):
    """ReorderOp members carry the strings the repositories dispatch on."""

    def test_members_are_their_strings(self) -> None:
        """Each member equals the operation string it stands for."""
        self.assertEqual(ReorderOp.UP, "up")
        self.assertEqual(ReorderOp.DOWN, "down")
        self.assertEqual(ReorderOp.TOP, "top")
        self.assertEqual(ReorderOp.BOTTOM, "bottom")
        self.assertEqual(ReorderOp.ABOVE, "above")
        self.assertEqual(ReorderOp.BELOW, "below")

    def test_relative_ops_are_the_positioning_operations(self) -> None:
        """RELATIVE_OPS holds the two operations that take a task to position against."""
        self.assertEqual(RELATIVE_OPS, {ReorderOp.ABOVE, ReorderOp.BELOW})


class TestReorderOpFromFlags(unittest.TestCase):
    """from_flags reads the operation a command's flags name."""

    def test_returns_the_operation_whose_flag_is_set(self) -> None:
        """A set flag names its operation."""
        self.assertEqual(ReorderOp.from_flags({"top": True}), ReorderOp.TOP)
        self.assertEqual(ReorderOp.from_flags({"bottom": True}), ReorderOp.BOTTOM)
        self.assertEqual(ReorderOp.from_flags({"up": True}), ReorderOp.UP)
        self.assertEqual(ReorderOp.from_flags({"down": True}), ReorderOp.DOWN)

    def test_returns_none_when_no_flag_is_set(self) -> None:
        """No operation is named when every flag it could be is unset."""
        flags = {"top": False, "bottom": False, "up": False, "down": False}
        self.assertIsNone(ReorderOp.from_flags(flags))

    def test_returns_none_for_flags_that_name_no_operation(self) -> None:
        """Flags belonging to the rest of the command are passed over."""
        self.assertIsNone(ReorderOp.from_flags({"column": "done", "force": True}))

    def test_ignores_flags_that_name_no_operation(self) -> None:
        """A whole command's arguments may be handed in alongside the flags."""
        flags = {"path": "/main/todo/fix-bug", "force": True, "up": True}
        self.assertEqual(ReorderOp.from_flags(flags), ReorderOp.UP)

    def test_returns_none_for_no_flags_at_all(self) -> None:
        """An empty mapping names no operation."""
        self.assertIsNone(ReorderOp.from_flags({}))


if __name__ == "__main__":
    unittest.main()
