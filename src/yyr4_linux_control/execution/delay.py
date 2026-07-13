import asyncio
from .interfaces import DelayBackend

class AsyncioDelayBackend(DelayBackend):
    async def delay(self, milliseconds: int) -> None:
        if milliseconds <= 0:
            return
        await asyncio.sleep(milliseconds / 1000.0)
