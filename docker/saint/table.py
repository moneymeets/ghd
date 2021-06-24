import curses
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Optional,
    Sequence,
    TypeVar,
    Union,
)

import blessed
import blessed.keyboard
import blessed.sequences

from .widget import Widget


class Column:
    def __init__(self, title: str, getter: Callable[[Any, int], str]):
        self._getter = getter
        self.title = title

    def get(self, row: Any, max_length: int):
        return self._getter(row, max_length)

    @staticmethod
    def getter(
        *names: str,
        styler: Optional[Callable[[Any, int], str]] = None,
    ) -> Callable[[dict[str, Any], int], str]:
        def f(row: dict[str, Any], max_length: int):
            cursor = row
            for name in names:
                cursor = cursor[name]
            return str(cursor)[:max_length] if not styler else styler(cursor, max_length)

        return f

    def __repr__(self):
        return f"'{self.title}'"


TableT = TypeVar("TableT")


class Table(Widget, Generic[TableT]):
    on_selection_changed: Widget.Signal

    def __init__(
        self,
        parent_or_term: Union[Optional[Widget], blessed.Terminal],
        *columns: Column,
    ):
        super().__init__(parent_or_term, True)
        self._columns = columns or self.columns
        self._data: Sequence[TableT] = ()
        self._selected_index: int = 0
        self._view_offset: int = 0
        self._widths: Sequence[int] = ()
        self.column_padding: int = 2
        self._left_column = 0

    def _calc_widths(self):
        self._widths = [
            max(
                *([0] + [blessed.sequences.Sequence(c.get(row, 10000), self.term).length() for row in self._data]),
                len(c.title),
            )
            for c in self._columns
        ]

    @property
    def selected_index(self) -> int:
        return self._selected_index

    async def set_selected_index(self, index: int):
        self._selected_index = max(0, min(index, len(self._data) - 1))
        row_on_screen = self._selected_index - self._view_offset
        visible_lines = self.height - 1  # account for header line
        if row_on_screen >= visible_lines:
            self._view_offset = max(0, self._selected_index - (visible_lines - 1))
        elif row_on_screen < 0:
            self._view_offset = self._selected_index

        await self.on_selection_changed(self)

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, rows: Sequence[TableT]):
        self._data = rows
        self._calc_widths()
        if self.focus_index >= len(rows):
            self.focus_index = len(rows) - 1

    @property
    def selected_data(self) -> Optional[TableT]:
        try:
            return self._data[self.selected_index]
        except IndexError:
            return None

    async def on_input(self, key: blessed.keyboard.Keystroke) -> bool:
        if await super(Table, self).on_input(key):
            return True

        if key.code == curses.KEY_DOWN or key == "j":
            await self.set_selected_index(self._selected_index + 1)
            return True
        elif key.code == curses.KEY_UP or key == "k":
            await self.set_selected_index(self._selected_index - 1)
            return True
        elif key.code == curses.KEY_NPAGE or key == "J":
            await self.set_selected_index(self._selected_index + (self.height - 2))
            return True
        elif key.code == curses.KEY_PPAGE or key == "K":
            await self.set_selected_index(self._selected_index - (self.height - 2))
            return True
        elif key.code == curses.KEY_HOME:
            await self.set_selected_index(0)
            return True
        elif key.code == curses.KEY_END:
            await self.set_selected_index(len(self._data) - 1)
            return True
        elif key.code == curses.KEY_LEFT or key == "h":
            if self._left_column > 0:
                self._left_column -= 1
                return True
        elif key.code == curses.KEY_RIGHT or key == "l":
            if self._capped:
                self._left_column += 1
                return True
        return False

    def on_resize(self, width: int, height: int):
        super().on_resize(width, height)
        if self._selected_index - self._view_offset < 0:
            self._view_offset = self._selected_index
        elif self._selected_index - self._view_offset >= self.height:
            self._view_offset = self._selected_index - self.height

    @property
    def _column_dimensions(self) -> Iterable[tuple[int, int]]:
        x = self.column_padding
        for width in self._widths[self._left_column :]:
            padded_width = self.column_padding + width
            next_x = x + padded_width
            if next_x + self.column_padding >= self.width:
                yield x, self.width - (x + self.column_padding)
            else:
                yield x, width
            x = next_x

    @property
    def _capped(self):
        return (
            self.column_padding
            + len(self._widths[self._left_column :]) * self.column_padding
            + sum(self._widths[self._left_column :])
        ) > self.width

    def on_paint(self):
        self.clear_viewport()

        self.out(0, 0, self.style.table_header, " " * self.column_padding)
        for (x, width), column in zip(self._column_dimensions, self._columns[self._left_column :]):
            cell = column.title[:width]
            cell_len = blessed.sequences.Sequence(cell, self.term).length()
            self.out(
                x,
                0,
                self.style.table_header,
                cell,
                " " * (width + self.column_padding - cell_len),
            )

        selected_style = self.style.table_row_selected_focus if self.has_focus else self._style.table_row_selected
        for i, row in enumerate(self._visible_data, start=self._first_visible_row):
            self.style.use_default()
            y = i + 1 - self._first_visible_row
            color = selected_style if i == self._selected_index else self.style.table_row

            self.out(0, y, color, " " * self.column_padding)
            for (x, width), column in zip(self._column_dimensions, self._columns[self._left_column :]):
                cell = column.get(row, width)
                cell_len = blessed.sequences.Sequence(cell, self.term).length()
                self.out(
                    x,
                    y,
                    color,
                    cell,
                    " " * (width - cell_len),
                    color,
                    " " * self.column_padding,
                )

        if self._first_visible_row != 0:
            self.out(0, 1, self.style.default, "↑")
        if self._last_visible_row != len(self._data):
            self.out(0, self.height - 1, self.style.default, "↓")
        if self._left_column != 0:
            self.out(0, 0, self.style.table_header, "←")
        if self._capped:
            self.out(self.width - 1, 0, self.style.table_header, "→")

    @property
    def _first_visible_row(self):
        return self._view_offset

    @property
    def _last_visible_row(self):
        return min(self._first_visible_row + self.height, len(self._data))

    @property
    def _visible_data(self):
        return self._data[self._first_visible_row : self._last_visible_row]

    def __repr__(self):
        columns = ",".join(map(repr, self._columns))
        return f"Table<{columns}>"
