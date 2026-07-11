import unittest
from yyr4_linux_control.input.interfaces import KernelInputEvent, SystemMonotonicClock

class TestInputInterfaces(unittest.TestCase):
    def test_kernel_input_event_valid(self):
        evt = KernelInputEvent(1, 2, 3, 1000)
        self.assertEqual(evt.event_type, 1)
        
    def test_kernel_input_event_invalid_type(self):
        with self.assertRaises(ValueError):
            KernelInputEvent(-1, 2, 3)

    def test_kernel_input_event_invalid_code(self):
        with self.assertRaises(ValueError):
            KernelInputEvent(1, -1, 3)

    def test_kernel_input_event_invalid_timestamp(self):
        with self.assertRaises(ValueError):
            KernelInputEvent(1, 2, 3, -1)
            
    def test_system_clock(self):
        clock = SystemMonotonicClock()
        t1 = clock.now_ns()
        t2 = clock.now_ns()
        self.assertGreaterEqual(t2, t1)
