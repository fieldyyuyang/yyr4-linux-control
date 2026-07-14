import asyncio
import logging

from yyr4_linux_control.control.models import OfficialControlEvent

logger = logging.getLogger("yyr4_linux_control.daemon")

class DropNewestEventQueue:
    """A bounded FIFO queue that drops the newest event if full."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._queue = asyncio.Queue()
        self.dropped_count = 0

    def enqueue(self, event: OfficialControlEvent) -> bool:
        if self._queue.qsize() >= self.capacity:
            self.dropped_count += 1
            logger.warning(f"Queue full (capacity {self.capacity}). Dropping new event for control {event.control.value}.")
            return False
        
        self._queue.put_nowait(event)
        return True

    async def dequeue(self) -> OfficialControlEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def get_all_nowait(self) -> list[OfficialControlEvent]:
        items = []
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items
