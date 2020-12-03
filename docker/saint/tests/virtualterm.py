from typing import DefaultDict, Iterable, List
from unittest.mock import patch

import blessed
import pyte
from blessed.terminal import WINSZ
from pyte.screens import Char

from saint.screenbuffer import ScreenBuffer
from saint.style import Style
from saint.tests.pytestreamwrapper import PyteStreamWrapper


class VirtualTerm:
    """
    A virtual "blessed" terminal using pyte.
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.screen = pyte.screens.Screen(width, height)
        self.stream = pyte.streams.Stream(self.screen)
        with patch("os.isatty", return_value=True):
            self.term = blessed.Terminal(stream=PyteStreamWrapper(self.stream), kind="xterm-256color")
        self._screen_buffer = ScreenBuffer(self.term)

        patch.object(
            self.term,
            "_height_and_width",
            return_value=WINSZ(ws_row=height, ws_col=width, ws_ypixel=16 * height, ws_xpixel=8 * width),
        ).__enter__()
        self.style = Style(self.term, self._screen_buffer)
        self._fullscreen_ctx = None

    @property
    def screen_buffer(self):
        return self.screen.buffer

    @property
    def screen_lines(self) -> List[DefaultDict[int, Char]]:
        return list(map(lambda y: self.screen.buffer[y], range(self.height)))

    def columns_of_line(self, line: DefaultDict[int, Char]) -> Iterable[Char]:
        return map(lambda x: line[x], range(self.width))

    @property
    def screen_data(self) -> List[List[Char]]:
        return [list(self.columns_of_line(line)) for line in self.screen_lines]

    def feed(self, *args):
        for arg in args:
            self.stream.feed(str(arg))

    def __enter__(self):
        assert self._fullscreen_ctx is None
        self._fullscreen_ctx = self.term.fullscreen()
        self._fullscreen_ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert self._fullscreen_ctx is not None
        self._fullscreen_ctx.__exit__(exc_type, exc_val, exc_tb)
