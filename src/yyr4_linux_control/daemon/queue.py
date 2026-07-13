import asyncio
import logging

from yyr4_linux_control.control.actions import ActionPlan

logger = logging.getLogger("yyr4_linux_control.daemon")

class DropNewestActionQueue:
    """A bounded FIFO queue that drops the newest plan if full."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self._queue = asyncio.Queue()
        self.dropped_count = 0

    def enqueue(self, plan: ActionPlan) -> bool:
        if self._queue.qsize() >= self.capacity:
            self.dropped_count += 1
            logger.warning(f"Queue full (capacity {self.capacity}). Dropping new action plan for control {plan.control.value}.")
            return False
        
        self._queue.put_nowait(plan)
        return True

    async def dequeue(self) -> ActionPlan:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    def get_all_nowait(self) -> list[ActionPlan]:
        items = []
        while not self._queue.empty():
            try:
                items.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items
