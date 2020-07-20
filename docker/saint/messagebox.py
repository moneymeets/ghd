import curses
from typing import Optional, Union, Sequence, Tuple, Any

import blessed
import blessed.keyboard

from .util import draw_border_double
from .widget import Widget


class MessageBox(Widget):
    on_select: Widget.Signal
    on_abort: Widget.Signal

    def __init__(
        self,
        parent_or_term: Union[Optional[Widget], blessed.Terminal],
        message: str,
        choices: Sequence[Tuple[str, Any]],
    ):
        super().__init__(parent_or_term, False)
        self.message = message
        self._choices = choices
        self._current_choice = 0

        self.on[blessed.keyboard.KEY_TAB] += self.next_choice
        self.on[curses.KEY_RIGHT] += self.next_choice
        self.on[curses.KEY_BTAB] += self.prev_choice
        self.on[curses.KEY_LEFT] += self.prev_choice
        self.on[curses.KEY_EXIT] += self.on_abort
        self.on["q"] += self.on_abort
        self.on[curses.KEY_ENTER] += self.on_select

    async def next_choice(self, widget, key):
        self._current_choice = (self._current_choice + 1) % len(self._choices)

    async def prev_choice(self, widget, key):
        self._current_choice = (self._current_choice + len(self._choices) - 1) % len(self._choices)

    @property
    def choice(self):
        return self._choices[self._current_choice]

    @property
    def choice_index(self):
        return self._current_choice

    @choice_index.setter
    def choice_index(self, value: int):
        self._current_choice = min(max(0, value), len(self._choices) - 1)

    def on_paint(self):
        self.clear_viewport()
        draw_border_double(self)

        lines = self.message.splitlines()
        y = 1
        for line in lines:
            self.out(2, y, line[: self.size_x - 4])
            y += 1

        x = 2
        y += 1
        for i, (choice, _) in enumerate(self._choices):
            text = f"[ {choice} ]"
            if i == self._current_choice:
                self.out(x, y, self.style.table_row_selected_focus, text, self.style.default)
            else:
                self.out(x, y, text)
            x += len(text) + 2
