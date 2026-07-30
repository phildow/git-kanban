"""A text field with a prefix-matched dropdown of candidate values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from textual import events
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


@dataclass(frozen=True)
class Segment:
    """
    The part of a field's value that is being completed.

    `start` is the offset in the full value where `text` begins, so an accepted
    suggestion can replace exactly that much of the field.
    """

    text:  str
    start: int


def active_segment(value: str, delimiter: str | None = None) -> Segment:
    """
    Return the portion of `value` the user is currently typing.

    Without a delimiter the whole value is being completed.  With one, only the
    text after the final delimiter counts, minus the whitespace that usually
    follows it.  Whitespace *inside* the segment is kept, because values such
    as tags may legitimately contain spaces.
    """
    if delimiter is None:
        return Segment(value, 0)

    start = value.rfind(delimiter) + 1
    while start < len(value) and value[start] == " ":
        start += 1

    return Segment(value[start:], start)


def entered_values(value: str, delimiter: str | None = None) -> list[str]:
    """
    Return the completed entries of a delimited value, ignoring the last one.

    These are the values the user has already committed to, so they should not
    be offered again.  A value with no delimiter has no completed entries.
    """
    if delimiter is None:
        return []

    parts = value.split(delimiter)[:-1]
    return [part.strip() for part in parts if part.strip()]


def matching_candidates(
    candidates: list[str],
    text: str,
    limit: int = MAX_SUGGESTIONS,
    *,
    exclude: Iterable[str] = (),
) -> list[str]:
    """
    Return the candidates prefixed by `text`, at most `limit` of them.

    Matching ignores case, and a candidate identical to what has already been
    typed is left out so accepting a suggestion does not immediately offer it
    again.  Anything in `exclude` is left out too.  An empty `text` matches
    everything.
    """
    needle = text.lower()
    excluded = set(exclude)

    return [
        candidate
        for candidate in candidates
        if candidate.lower().startswith(needle)
        and candidate != text
        and candidate not in excluded
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

    Given a `delimiter` the field holds a list rather than a single value: only
    the entry after the final delimiter is completed, and entries already in
    the field are not offered again.

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
        delimiter: str | None = None,
        id: str | None = None,
    ) -> None:
        """
        Create a field offering `candidates`, pre-filled with `value`.

        Pass a `delimiter` for fields that hold several values, such as the
        comma-separated tags field.
        """
        super().__init__(id=id)
        self.candidates = sorted({candidate for candidate in candidates if candidate})
        self.delimiter = delimiter

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
        """
        Accept a suggestion that was clicked.

        The value comes from the event rather than from the cached matches,
        because clicking moves focus off the field and the resulting blur has
        already closed the dropdown by the time this arrives.
        """
        event.stop()
        self._accept_value(str(event.option.prompt))

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        """
        Close the dropdown when focus leaves the field.

        Tabbing on to the next field should not leave suggestions hanging over
        it, and the keys the dropdown claims must go back to the form.
        """
        _ = event
        self._close()

    def _show_matches(self, text: str) -> None:
        """Open the dropdown on the candidates matching what is being typed, or close it."""
        segment = active_segment(text, self.delimiter)
        matches = matching_candidates(
            self.candidates,
            segment.text,
            exclude=entered_values(text, self.delimiter),
        )

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
        """Accept the highlighted suggestion, or close the dropdown if there is none."""
        if index is None or not (0 <= index < len(self._matches)):
            self._close()
            return

        self._accept_value(self._matches[index])

    def _accept_value(self, suggestion: str) -> None:
        """
        Put `suggestion` into the field and close the dropdown.

        Only the entry being typed is replaced, so accepting a tag leaves the
        tags already in the field alone.  Focus returns to the field, which a
        click on the dropdown will have taken away.
        """
        self._close()

        field = self._field
        segment = active_segment(field.value, self.delimiter)

        self._accepting = True
        field.value = f"{field.value[:segment.start]}{suggestion}"
        field.focus()

        # Deferred so it lands after the focus event, which selects the field.
        self.call_after_refresh(field.action_end)

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
