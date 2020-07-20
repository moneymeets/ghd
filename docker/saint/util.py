from typing import NoReturn

from . import ExitApp
from .widget import Widget


def breadcrumbs(*args) -> str:
    return " \u203a ".join(("",) + args)


async def exit_app(widget, key) -> NoReturn:
    raise ExitApp


def draw_border_double(widget: Widget):
    widget.out(0, 0, widget.style.default, "╔", "═" * (widget.width - 2), "╗")
    widget.out(
        0, widget.height - 1, widget.style.default, "╚", "═" * (widget.width - 2), "╝",
    )
    for i in range(1, widget.height - 1):
        widget.out(0, i, widget.style.default, "║")
        widget.out(widget.width - 1, i, widget.style.default, "║")
