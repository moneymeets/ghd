import asyncio
from asyncio.events import TimerHandle
from typing import Awaitable, Callable, Optional


class Timer:
    def __init__(self, interval: float, callback: Callable[[], Awaitable[None]]):
        self._interval = interval
        self._callback = callback
        self._stopped = True
        self._handle: Optional[TimerHandle] = None

    def _enqueue(self):
        if not self._stopped:
            self._handle = asyncio.get_event_loop().call_later(self._interval, self._tick)

    def _tick(self):
        self._enqueue()
        asyncio.get_event_loop().create_task(self._callback())

    def start(self):
        if not self._stopped:
            return

        self._stopped = False
        if self._handle is None or self._handle.cancelled():
            self._tick()

    def stop(self):
        self._handle.cancel()
        self._stopped = True

    @property
    def stopped(self):
        return self._stopped
