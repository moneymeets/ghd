from types import TracebackType
from typing import IO, AnyStr, Iterable, Iterator, Optional, Type

import pyte


class PyteStreamWrapper(IO):
    """
    A simple wrapper around pyte's stream to be usable from blessed's terminal.
    """

    FILE_NO = 999999

    def __init__(self, stream: pyte.streams.Stream):
        self._stream = stream

    def close(self) -> None:
        raise NotImplementedError

    def fileno(self) -> int:
        return self.FILE_NO

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True

    def read(self, n: int = ...) -> AnyStr:
        raise NotImplementedError

    def readable(self) -> bool:
        raise NotImplementedError

    def readline(self, limit: int = ...) -> AnyStr:
        raise NotImplementedError

    def readlines(self, hint: int = ...) -> list[AnyStr]:
        raise NotImplementedError

    def seek(self, offset: int, whence: int = ...) -> int:
        raise NotImplementedError

    def seekable(self) -> bool:
        raise NotImplementedError

    def tell(self) -> int:
        raise NotImplementedError

    def truncate(self, size: Optional[int] = ...) -> int:
        raise NotImplementedError

    def writable(self) -> bool:
        raise NotImplementedError

    def write(self, s: AnyStr) -> int:
        self._stream.feed(s)
        return len(s)

    def writelines(self, lines: Iterable[AnyStr]) -> None:
        raise NotImplementedError

    def __next__(self) -> AnyStr:
        raise NotImplementedError

    def __iter__(self) -> Iterator[AnyStr]:
        raise NotImplementedError

    def __enter__(self) -> IO[AnyStr]:
        raise NotImplementedError

    def __exit__(
        self,
        t: Optional[Type[BaseException]],
        value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        raise NotImplementedError
