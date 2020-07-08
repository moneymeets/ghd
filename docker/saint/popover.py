import textwrap

from .widget import Widget


def popover(widget: Widget, text: str):
    widget.clear_viewport()

    widget.out(0, 0, widget.style.default, "╔", "═" * (widget.width - 2), "╗")
    widget.out(
        0, widget.height - 1, widget.style.default, "╚", "═" * (widget.width - 2), "╝",
    )
    for i in range(1, widget.height - 1):
        widget.out(0, i, widget.style.default, "║")
        widget.out(widget.width - 1, i, widget.style.default, "║")

    lines = textwrap.wrap(text, widget.width - 4)
    offset_y = (widget.height - len(lines)) // 2
    for y, line in enumerate(lines):
        offset_x = (widget.width - len(line)) // 2
        widget.out(offset_x, offset_y + y, widget.style.default, line)

    widget.flush()
