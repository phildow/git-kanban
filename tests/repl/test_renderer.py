"""Tests that render_search delegates to render_task_list in the REPL renderers."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from kanban.repl.rich_renderer import RichRenderer


class TestRichRendererSearchDelegatesToTaskList(unittest.TestCase):
    """RichRenderer.render_search renders results the same way render_task_list does."""

    def setUp(self) -> None:
        self.renderer = RichRenderer(render_service=MagicMock())

    def test_render_search_calls_render_task_list_with_same_args_and_result(self) -> None:
        args = Namespace(slugs=False)
        result = [object(), object()]

        with patch.object(self.renderer, "render_task_list") as mock_render_task_list:
            self.renderer.render_search(args, result)

        mock_render_task_list.assert_called_once_with(args, result)

    def test_render_search_respects_slugs_flag_like_task_list(self) -> None:
        args = Namespace(slugs=True)
        result = [object()]

        with patch.object(self.renderer, "render_task_list_slug_only") as slug_only, \
             patch.object(self.renderer, "render_task_list_rich") as rich:
            self.renderer.render_search(args, result)

        slug_only.assert_called_once_with(args, result)
        rich.assert_not_called()


if __name__ == "__main__":
    unittest.main()
