from typing import Optional, Union

import blessed

from .widget import Widget


class StatusBar(Widget):
    def __init__(self, parent_or_term: Union[Optional[Widget], blessed.Terminal]):
        super().__init__(parent_or_term, False)
        self.text = ""

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height - 1)
        self.size_y = height

    def on_paint(self):
        for widget in self.widgets:
            widget.on_paint()
        self.out(
            0, self.height - 1, self.style.status_bar, self.text, self.term.clear_eol,
        )
