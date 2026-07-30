"""A text field with a prefix-matched dropdown of candidate values."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Input, OptionList

# Enough suggestions to be useful without burying the rest of the form.
MAX_SUGGESTIONS = 8

# Bindings the dropdown takes over from the field, and only while it is open.
_DROPDOWN_ACTIONS = {
    "next_suggestion",
    "previous_suggestion",
    "accept_suggestion",
    "close_suggestions",
}


def matching_candidates(
    candidates: list[str], text: str, limit: int = MAX_SUGGESTIONS
) -> list[str]:
    """
    Return the candidates prefixed by `text`, at most `limit` of them.

    Matching ignores case, and a candidate identical to what has already been
    typed is left out so accepting a suggestion does not immediately offer it
    again.  An empty `text` matches everything.
    """
    needle = text.lower()
    return [
        candidate
        for candidate in candidates
        if candidate.lower().startswith(needle) and candidate != text
    ][:limit]


class SuggestionInput(Input):
    """
    The text field of an `AutoCompleteInput`.

    Releases Enter while suggestions are showing so the key reaches the
    dropdown instead of submitting the surrounding form.
    """

    suggesting: reactive[bool] = reactive(False)
    """True while the dropdown is open."""

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Disable submit while the dropdown is open, letting Enter bubble up."""
        _ = parameters
        if action == "submit" and self.suggesting:
            return False
        return True


class AutoCompleteInput(Vertical):
    """
    An input that offers matching values from a list of candidates.

    Typing filters the candidates by prefix and opens a dropdown beneath the
    field; the arrow keys move through it and Enter accepts the highlighted
    value.  With the dropdown closed the field behaves like a plain `Input`, so
    Enter still submits the form and Escape still cancels it.

    The widget is handed its candidates and never queries the kanban service.
    """

    BINDINGS = [
        Binding("down", "next_suggestion", "Next suggestion", show=False),
        Binding("up", "previous_suggestion", "Previous suggestion", show=False),
        Binding("enter", "accept_suggestion", "Accept suggestion", show=False),
        Binding("escape", "close_suggestions", "Close suggestions", show=False),
    ]

    def __init__(
        self,
        candidates: list[str],
        *,
        value: str = "",
        placeholder: str = "",
        id: str | None = None,
    ) -> None:
        """Create a field offering `candidates`, pre-filled with `value`."""
        super().__init__(id=id)
        self.candidates = sorted({candidate for candidate in candidates if candidate})

        self._initial = value
        self._placeholder = placeholder
        self._matches: list[str] = []
        # Set while accepting, so the resulting change does not reopen the dropdown.
        self._accepting = False

    def compose(self) -> ComposeResult:
        """Lay out the text field above its dropdown."""
        yield SuggestionInput(
            value=self._initial, placeholder=self._placeholder, classes="-field"
        )
        yield OptionList(classes="-suggestions")

    def on_mount(self) -> None:
        """Hide the dropdown and keep it out of the focus order."""
        options = self._options
        options.display = False
        options.can_focus = False

    # ── Accessors ─────────────────────────────────────────────────────────────

    @property
    def value(self) -> str:
        """Return the text currently in the field."""
        return self._field.value

    @property
    def is_open(self) -> bool:
        """Return True while the dropdown is showing suggestions."""
        return bool(self._matches)

    @property
    def _field(self) -> SuggestionInput:
        """Return the text field."""
        return self.query_one(SuggestionInput)

    @property
    def _options(self) -> OptionList:
        """Return the dropdown."""
        return self.query_one(OptionList)

    def focus(self, scroll_visible: bool = True) -> AutoCompleteInput:
        """Focus the text field rather than the container."""
        self._field.focus(scroll_visible)
        return self

    # ── Suggestions ───────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        """Re-filter the candidates as the user types."""
        event.stop()

        if self._accepting:
            self._accepting = False
            return

        # Ignore the value being set before the user has reached the field.
        if not self._field.has_focus:
            return

        self._show_matches(event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Accept a suggestion that was clicked."""
        event.stop()
        self._accept(event.option_index)

    def _show_matches(self, text: str) -> None:
        """Open the dropdown on the candidates prefixed by `text`, or close it."""
        matches = matching_candidates(self.candidates, text)

        if not matches:
            self._close()
            return

        self._matches = matches
        options = self._options
        options.set_options(matches)
        options.highlighted = 0
        options.display = True
        self._field.suggesting = True

    def _close(self) -> None:
        """Hide the dropdown and hand the keys back to the field and the form."""
        self._matches = []
        options = self._options
        options.clear_options()
        options.display = False
        self._field.suggesting = False

    def _accept(self, index: int | None) -> None:
        """Put the suggestion at `index` into the field and close the dropdown."""
        if index is None or not (0 <= index < len(self._matches)):
            self._close()
            return

        value = self._matches[index]
        self._close()

        self._accepting = True
        field = self._field
        field.value = value
        field.action_end()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_next_suggestion(self) -> None:
        """Highlight the next suggestion."""
        self._options.action_cursor_down()

    def action_previous_suggestion(self) -> None:
        """Highlight the previous suggestion."""
        self._options.action_cursor_up()

    def action_accept_suggestion(self) -> None:
        """Accept the highlighted suggestion."""
        self._accept(self._options.highlighted)

    def action_close_suggestions(self) -> None:
        """Dismiss the dropdown without changing the field."""
        self._close()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """
        Claim the dropdown keys only while the dropdown is open.

        A disabled binding is not matched, so with the dropdown closed Enter and
        Escape continue up to the form.
        """
        _ = parameters
        if action in _DROPDOWN_ACTIONS:
            return self.is_open
        return True
