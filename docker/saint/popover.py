import textwrap

import blessed.keyboard

from .util import draw_border_double
from .widget import Widget


def _draw_popover(widget: Widget, text: str):
    widget.clear_viewport()
    draw_border_double(widget)

    # '... or [""]' is needed to not swallow single newlines
    lines = [line for text_chunk in text.splitlines() for line in (textwrap.wrap(text_chunk, widget.width - 4) or [""])]
    offset_y = (widget.height - len(lines)) // 2
    for y, line in enumerate(lines):
        offset_x = (widget.width - len(line)) // 2
        widget.out(offset_x, offset_y + y, widget.style.default, line)

    widget.flush()


def popover(widget: Widget, text: str):
    _draw_popover(widget, text)


def popover_confirm(widget: Widget, text: str) -> blessed.keyboard.Keystroke:
    _draw_popover(widget, text)
    with widget.term.raw():
        return widget.term.inkey()
