from io import StringIO

import blessed


class ScreenBuffer:
    def __init__(self, term: blessed.Terminal):
        self.buffer = StringIO()
        self._term = term

    def print(self, *args):
        self.buffer.write("".join(map(str, args)))

    def clear(self):
        self.buffer = StringIO()

    def output(self):
        self._term.stream.write(self.buffer.getvalue())
