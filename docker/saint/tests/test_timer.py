import asyncio
import unittest
from unittest.mock import AsyncMock, call

from saint.timer import Timer


class SignalTest(unittest.IsolatedAsyncioTestCase):
    def test_initial_tick(self):
        f = AsyncMock()

        timer = Timer(100, f)
        timer.start()
        self.assertFalse(timer.stopped)
        f.assert_called_once_with()
        timer.stop()
        self.assertTrue(timer.stopped)

    def test_start_stop(self):
        f = AsyncMock()

        timer = Timer(100, f)
        self.assertTrue(timer.stopped)
        f.assert_not_called()
        timer.start()
        self.assertFalse(timer.stopped)
        timer.stop()
        self.assertTrue(timer.stopped)

    async def test_ticks(self):
        f = AsyncMock()

        n_calls = 5
        interval = 0.01
        timer = Timer(interval, f)
        timer.start()
        await asyncio.sleep(interval * n_calls)
        timer.stop()
        await asyncio.sleep(interval * n_calls)  # make sure it's really stopped
        self.assertEqual(f.call_count, n_calls)
        f.assert_has_calls([call()] * n_calls)
