import textwrap

from .util import draw_border_double
from .widget import Widget


def popover(widget: Widget, text: str):
    widget.clear_viewport()
    draw_border_double(widget)

    lines = textwrap.wrap(text, widget.width - 4)
    offset_y = (widget.height - len(lines)) // 2
    for y, line in enumerate(lines):
        offset_x = (widget.width - len(line)) // 2
        widget.out(offset_x, offset_y + y, widget.style.default, line)

    widget.flush()
