from itertools import accumulate
from typing import Final, Optional, TypeVar, Union

import blessed
import blessed.keyboard
import blessed.sequences

from .screenbuffer import ScreenBuffer
from .signal import AsyncSignal as SaintSignal, AsyncSignals
from .style import Style

Widget_co = TypeVar("Widget_co", bound="Widget", covariant=True)


def init_signals(obj: Widget_co):
    signal_defs = {}
    for klass in type(obj).__mro__[::-1]:
        if not issubclass(klass, Widget) or "__annotations__" not in klass.__dict__:
            continue

        for name, annotation in klass.__annotations__.items():
            if annotation is not Widget.Signal:
                continue

            if name in signal_defs:
                # Annotations of subclasses without __init__ are duplicated up the chain to the first class
                # with an __init__ method.  This leads to the problem that we cannot detect a duplicated
                # signal in a subclass without an __init__ function, because that signal declaration is
                # indistinguishable from one that might have been declared in the first base class which has
                # an explicit __init__ method.
                raise KeyError(
                    f"Signal '{klass.__qualname__}.{name}' already defined in '{signal_defs[name]}'; "
                    f"if this is wrong, make sure you have an __init__ function in your classes",
                )
            signal_defs[name] = klass.__qualname__
            setattr(obj, name, obj.on[name])


class Widget:
    """
    Use the "Signal" in a class as a type annotation, i.e. write "on_something: Widget.Signal" and it will
    automagically be available as an instance variable (i.e. "instance_of_class.on_something(...)") as well as
    available in the "on" signal list (i.e. "on['on_something']" is the same signal).

    NOTE: This only works if the class you're declaring the signal in also has an __init__ function.
    """

    Signal: SaintSignal = SaintSignal

    def __init__(
        self,
        parent_or_term: Union[Optional["Widget"], blessed.Terminal],
        layout_dir_vertical: bool,
    ):
        parent_is_widget = isinstance(parent_or_term, Widget)
        self.parent: Final[Optional[Widget]] = parent_or_term if parent_is_widget else None
        self.term: Final[blessed.Terminal] = self.parent.term if parent_is_widget else parent_or_term
        self.screen: Final[ScreenBuffer] = self.parent.screen if parent_is_widget else ScreenBuffer(self.term)
        self._style: Final[Style] = self.parent._style if parent_is_widget else Style(self.term, self.screen)
        self.layout_dir_vertical = layout_dir_vertical
        self.origin_x: int = 0
        self.origin_y: int = 0
        self.size_x: int = 1
        self.size_y: int = 1
        self.flex: int = 1
        self.widgets: list[Widget] = []
        self.focus_index: int = 0
        self.on: Final[AsyncSignals[[Widget_co, blessed.keyboard.Keystroke], None]] = AsyncSignals()

        init_signals(self)

        if self.parent is not None:
            self.parent.widgets.append(self)

    def clear_viewport(self):
        filler = self.style.default + " " * self.width
        for i in range(self.height):
            self.out(0, i, filler)

    @property
    def width(self) -> int:
        return self.size_x

    @property
    def height(self) -> int:
        return self.size_y

    @property
    def style(self) -> Style:
        return self._style

    @property
    def has_focus(self) -> bool:
        return (self.parent.focused_widget is self and self.parent.has_focus) if self.parent else True

    def out(self, x: int, y: int, *args: str):
        if x >= self.size_x or y >= self.size_y:
            return

        output = blessed.sequences.Sequence("".join(map(str, args)), self.term)
        self.screen.print(self.term.move_xy(x + self.origin_x, y + self.origin_y), output)

    def _set_focus_index(self, index: int):
        if not self.widgets:
            self.focus_index = 0
        else:
            self.focus_index = (index + len(self.widgets)) % len(self.widgets)

    @property
    def focused_widget(self) -> Optional["Widget"]:
        return self.widgets[self.focus_index] if 0 <= self.focus_index < len(self.widgets) else None

    def focus_next(self):
        self._set_focus_index(self.focus_index + 1)

    def focus_prev(self):
        self._set_focus_index(self.focus_index - 1)

    async def focus_next_slot(self, widget, key):
        self.focus_next()

    async def focus_prev_slot(self, widget, key):
        self.focus_prev()

    def _flex_offsets(self, size: int):
        if not self.widgets:
            return []

        flexes = [0] + list(accumulate([widget.flex for widget in self.widgets]))
        return [flex * size // flexes[-1] for flex in flexes]

    def on_resize(self, width: int, height: int):
        self.size_x, self.size_y = width, height
        if self.parent:
            self.size_x = min(self.size_x, self.parent.size_x - self.origin_x)
            self.size_y = min(self.size_y, self.parent.size_y - self.origin_y)
        offsets = self._flex_offsets(height if self.layout_dir_vertical else width)
        for i, widget in enumerate(self.widgets):
            offset = offsets[i]
            size = offsets[i + 1] - offset
            if not self.layout_dir_vertical:
                widget.origin_x, widget.origin_y = offset, self.origin_y
                widget.on_resize(size, height)
            else:
                widget.origin_x, widget.origin_y = self.origin_x, offset
                widget.on_resize(width, size)

    def on_paint(self):
        for widget in self.widgets:
            widget.on_paint()

    async def on_input(self, key: blessed.keyboard.Keystroke) -> bool:
        if any(await self.on[key.code or str(key)](self, key)):
            return True

        focused = self.focused_widget
        if focused:
            return await focused.on_input(key)
        else:
            return False
