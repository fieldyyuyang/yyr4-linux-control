import asyncio
import unittest
from yyr4_linux_control.daemon.queue import DropNewestEventQueue
from yyr4_linux_control.control.actions import ActionPlan, ResolutionStatus, NoOpAction
from yyr4_linux_control.control.models import OfficialControl

class TestDaemonQueue(unittest.IsolatedAsyncioTestCase):
    def test_queue_preserves_fifo_order(self):
        q = DropNewestEventQueue(capacity=3)
        plan1 = ActionPlan(OfficialControl.A1, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        plan2 = ActionPlan(OfficialControl.A2, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        
        q.enqueue(plan1)
        q.enqueue(plan2)
        
        items = q.get_all_nowait()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].control, OfficialControl.A1)
        self.assertEqual(items[1].control, OfficialControl.A2)

    def test_queue_drops_newest_when_full(self):
        q = DropNewestEventQueue(capacity=2)
        plan1 = ActionPlan(OfficialControl.A1, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        plan2 = ActionPlan(OfficialControl.A2, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        plan3 = ActionPlan(OfficialControl.A3, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        
        self.assertTrue(q.enqueue(plan1))
        self.assertTrue(q.enqueue(plan2))
        self.assertFalse(q.enqueue(plan3))
        
        self.assertEqual(q.size, 2)
        self.assertEqual(q.dropped_count, 1)

    def test_queue_drop_increments_runtime_counter(self):
        # The runtime drops it, the queue counts it, but we test the queue counter here.
        # The runtime counter test will be done in test_daemon_runtime.py
        q = DropNewestEventQueue(capacity=1)
        plan1 = ActionPlan(OfficialControl.A1, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        plan2 = ActionPlan(OfficialControl.A2, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        
        q.enqueue(plan1)
        q.enqueue(plan2)
        self.assertEqual(q.dropped_count, 1)

    def test_queue_accepts_new_items_after_capacity_recovers(self):
        q = DropNewestEventQueue(capacity=1)
        plan1 = ActionPlan(OfficialControl.A1, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        plan2 = ActionPlan(OfficialControl.A2, ResolutionStatus.CONFIGURED, (NoOpAction(),))
        
        q.enqueue(plan1)
        self.assertFalse(q.enqueue(plan2)) # drops plan2
        
        # Recover
        items = q.get_all_nowait()
        for _ in items:
            q.task_done()
            
        self.assertEqual(q.size, 0)
        self.assertTrue(q.enqueue(plan2)) # accepts plan2 now
