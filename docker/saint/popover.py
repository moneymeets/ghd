import textwrap

from .util import draw_border_double
from .widget import Widget


def popover(widget: Widget, text: str, wait_for_input: bool = False):
    widget.clear_viewport()
    draw_border_double(widget)

    # '... or [""]' is needed to not swallow single newlines
    lines = [line for text_chunk in text.splitlines() for line in (textwrap.wrap(text_chunk, widget.width - 4) or [""])]
    offset_y = (widget.height - len(lines)) // 2
    for y, line in enumerate(lines):
        offset_x = (widget.width - len(line)) // 2
        widget.out(offset_x, offset_y + y, widget.style.default, line)

    widget.flush()

    if wait_for_input:
        with widget.term.raw():
            widget.term.inkey()
