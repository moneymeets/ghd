import asyncio
import gc
import unittest
import unittest.mock as mock

from saint.signal import AsyncSignal, AsyncSignals, Signal


class SignalTest(unittest.TestCase):
    @staticmethod
    def _mock_signal(async_: bool):
        return (mock.AsyncMock(), AsyncSignal()) if async_ else (mock.Mock(), Signal())

    def _test_emit_helper(self, async_: bool, connects: int):
        handler, signal = self._mock_signal(async_)
        for _ in range(connects):
            signal.connect(handler)
        r = signal("foo")
        if async_:
            asyncio.run(r)
        handler.assert_called_once_with("foo")

    def test_connect_emit(self):
        self._test_emit_helper(True, 1)
        self._test_emit_helper(False, 1)
        self._test_emit_helper(True, 2)
        self._test_emit_helper(False, 2)

    def _test_disconnect_helper(self, async_: bool):
        handler, signal = self._mock_signal(async_)
        signal.connect(handler)
        signal.disconnect(handler)
        r = signal("foo")
        if async_:
            asyncio.run(r)
        handler.assert_not_called()

    def test_disconnect(self):
        self._test_disconnect_helper(True)
        self._test_disconnect_helper(False)

    def _test_gc_disconnect_helper(self, kls, async_: bool):
        counter = 0

        def incr(*args, **kwargs):
            nonlocal counter
            counter += 1
            self.assertSequenceEqual(args, (123, 456))
            self.assertDictEqual(kwargs, {"foo": "bar"})

        obj = kls(incr)
        signal = AsyncSignal() if async_ else Signal()
        signal.connect(obj.f if hasattr(obj, "f") else obj)
        r = signal(123, 456, foo="bar")
        if async_:
            asyncio.run(r)
        self.assertEqual(counter, 1)

        del obj
        gc.collect()
        counter = 0
        r = signal()
        if async_:
            asyncio.run(r)
        self.assertEqual(counter, 0)

    def test_gc_disconnect(self):
        class Wrapper:
            def __init__(self, f):
                self._f = f

        class SyncFoo(Wrapper):
            def f(self, *args, **kwargs):
                self._f(*args, **kwargs)

        class AsyncFoo(Wrapper):
            async def f(self, *args, **kwargs):
                self._f(*args, **kwargs)

        self._test_gc_disconnect_helper(AsyncFoo, True)
        self._test_gc_disconnect_helper(SyncFoo, False)

    def test_gc_obj_disconnect(self):
        class Wrapper:
            def __init__(self, f):
                self._f = f

        class SyncFoo(Wrapper):
            def __call__(self, *args, **kwargs):
                self._f(*args, **kwargs)

        class AsyncFoo(Wrapper):
            async def __call__(self, *args, **kwargs):
                self._f(*args, **kwargs)

        self._test_gc_disconnect_helper(AsyncFoo, True)
        self._test_gc_disconnect_helper(SyncFoo, False)

    def test_signals_assignment(self):
        signals = AsyncSignals()
        with self.assertRaises(RuntimeError):
            signals["foo"] += signals["foo"]
        signals["foo"] += signals["bar"]
        with self.assertRaises(ValueError):
            signals["foo"] = signals["bar"]
