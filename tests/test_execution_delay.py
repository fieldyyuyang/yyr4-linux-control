import asyncio
import unittest
from yyr4_linux_control.execution.delay import AsyncioDelayBackend

class TestExecutionDelay(unittest.IsolatedAsyncioTestCase):
    async def test_delay(self):
        backend = AsyncioDelayBackend()
        # Should complete quickly without blocking
        await asyncio.wait_for(backend.delay(10), timeout=0.1)

    async def test_delay_zero(self):
        backend = AsyncioDelayBackend()
        await backend.delay(0)

    async def test_delay_negative(self):
        backend = AsyncioDelayBackend()
        await backend.delay(-10)

    async def test_delay_cancellation(self):
        backend = AsyncioDelayBackend()
        task = asyncio.create_task(backend.delay(5000))
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
