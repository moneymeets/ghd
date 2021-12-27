import asyncio
from collections import defaultdict
from typing import Callable, Dict, Union
from weakref import WeakMethod, ref

__all__ = ("Signal", "AsyncSignal", "AsyncSignals")


class _SignalBase:
    __slots__ = ("_handlers",)

    def __init__(self):
        self._handlers = set()

    def _cleanup(self, key):
        self._handlers.remove(key)

    @property
    def _unwrapped_handlers(self):
        return [(handler() if isinstance(handler, (WeakMethod, ref)) else handler) for handler in self._handlers]

    def connect(self, f: Callable):
        if hasattr(f, "__self__") and hasattr(f, "__func__"):
            self._handlers.add(WeakMethod(f, self._cleanup))
        elif isinstance(f, object):
            self._handlers.add(ref(f, self._cleanup))
        else:
            self._handlers.add(f)

    def disconnect(self, f: Callable):
        if hasattr(f, "__self__") and hasattr(f, "__func__"):
            self._handlers.remove(WeakMethod(f))
        elif isinstance(f, object):
            self._handlers.remove(ref(f))
        else:
            self._handlers.remove(f)

    def __add__(self, f: Callable):
        if f is self:
            raise RuntimeError("Signal-self assignment detected")

        self.connect(f)
        return self

    def __sub__(self, f: Callable):
        self.disconnect(f)
        return self


class Signal(_SignalBase):
    def emit(self, *args, **kwargs):
        return [handler(*args, **kwargs) for handler in self._unwrapped_handlers]

    def __call__(self, *args, **kwargs):
        return self.emit(*args, **kwargs)


class AsyncSignal(_SignalBase):
    async def emit(self, *args, **kwargs) -> list[bool]:
        fs = [handler(*args, **kwargs) for handler in self._unwrapped_handlers]
        return [await f for f in asyncio.as_completed(fs)]

    async def __call__(self, *args, **kwargs):
        return await self.emit(*args, **kwargs)


class AsyncSignals(Dict[str, AsyncSignal]):
    __slots__ = ("_signals",)

    def __init__(self):
        super().__init__()
        self._signals = defaultdict(AsyncSignal)

    def __getitem__(self, name: Union[str, int]) -> AsyncSignal:
        return self._signals[name]

    def __setitem__(self, name: Union[str, int], signal: AsyncSignal):
        if signal is not self[name]:
            raise ValueError("Signals must not be assigned except themselves")
