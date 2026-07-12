import unittest
from unittest.mock import patch
import asyncio
import sys
from yyr4_linux_control.device.identity import YYR4Identity, InputInterface, InterfaceRole
from yyr4_linux_control.input.evdev_adapter import EvdevInputAdapter, LinuxEvdevDeviceFactory
from yyr4_linux_control.input.interfaces import KernelInputEvent
from yyr4_linux_control.input.errors import InputOpenError, InputReadError
from yyr4_linux_control.device.errors import DependencyUnavailableError
from tests.fakes import FakeEventDeviceFactory, FakeClock, FakeEventDeviceHandle

class TestEvdevAdapter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.kb = InputInterface(InterfaceRole.KEYBOARD, "/dev/kb", "KB", "02", "/sys/kb", "/sys/usb")
        self.ms = InputInterface(InterfaceRole.MOUSE, "/dev/ms", "MS", "02", "/sys/ms", "/sys/usb")
        self.idx = YYR4Identity("239a", "80f4", "M", "P", "/sys/usb", self.kb, self.ms, False)
        
        self.factory = FakeEventDeviceFactory()
        self.clock = FakeClock()
        
        # In our fakes, ecodes values: EV_KEY = 1
        # Let's mock evdev in sys.modules to simulate keys if missing
        class FakeEcodes:
            EV_KEY = 1
            EV_SYN = 0
            keys = { 183: "KEY_F13", 42: "KEY_LEFTSHIFT" }
            
        class FakeEvdev:
            ecodes = FakeEcodes()

        self._old_evdev = sys.modules.get("evdev")
        sys.modules["evdev"] = FakeEvdev()

    def tearDown(self):
        if self._old_evdev:
            sys.modules["evdev"] = self._old_evdev
        else:
            sys.modules.pop("evdev", None)

    async def test_start_and_close_idempotent(self):
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        await adapter.start()
        self.assertIn("/dev/kb", self.factory.handles)
        self.assertIn("/dev/ms", self.factory.handles)
        adapter.close()
        adapter.close()
        self.assertTrue(self.factory.handles["/dev/kb"].closed)
        self.assertTrue(self.factory.handles["/dev/ms"].closed)
        self.assertEqual(adapter.snapshot_diagnostics().opened_devices, 2)
        self.assertEqual(adapter.snapshot_diagnostics().close_count, 1)

    async def test_close_without_start(self):
        self.factory.auto_eof = False
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        adapter.close()
        self.assertEqual(adapter.snapshot_diagnostics().close_count, 1)

    async def test_open_fail_keyboard(self):
        self.factory.should_fail_open = True
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        with self.assertRaises(InputOpenError):
            await adapter.start()

    async def test_read_events_valid_key(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [
            KernelInputEvent(1, 183, 1),
            KernelInputEvent(1, 183, 0)
        ])
        
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        events = []
        
        async def consume():
            async for evt in adapter.read_events():
                events.append(evt)
                if len(events) == 2:
                    break
                    
        await asyncio.wait_for(consume(), timeout=1.0)
        
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].source_id, "yyr4:keyboard")
        self.assertEqual(events[0].code, "KEY_F13")
        self.assertEqual(events[0].value, 1)
        self.assertEqual(events[1].value, 0)
        
        diag = adapter.snapshot_diagnostics()
        self.assertEqual(diag.emitted_key_events, 2)
        adapter.close()

    async def test_ignore_syn_events(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [
            KernelInputEvent(0, 0, 0),
            KernelInputEvent(1, 183, 1)
        ])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        events = []
        async def consume():
            async for evt in adapter.read_events():
                events.append(evt)
                break
        await asyncio.wait_for(consume(), timeout=1.0)
        diag = adapter.snapshot_diagnostics()
        self.assertEqual(diag.ignored_non_key_events, 1)
        self.assertEqual(diag.emitted_key_events, 1)
        adapter.close()

    async def test_ignore_unknown_code(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [
            KernelInputEvent(1, 9999, 1), # Unknown code
            KernelInputEvent(1, 183, 1)
        ])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        events = []
        async def consume():
            async for evt in adapter.read_events():
                events.append(evt)
                break
        await asyncio.wait_for(consume(), timeout=1.0)
        diag = adapter.snapshot_diagnostics()
        self.assertEqual(diag.ignored_unknown_codes, 1)
        adapter.close()

    async def test_timestamp_monotonicity(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [
            KernelInputEvent(1, 183, 1),
            KernelInputEvent(1, 183, 0)
        ])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        
        # Mock clock to return same time twice
        self.clock.now_ns = lambda: 5000
        
        events = []
        async def consume():
            async for evt in adapter.read_events():
                events.append(evt)
                if len(events) == 2:
                    break
        await asyncio.wait_for(consume(), timeout=1.0)
        
        self.assertEqual(events[0].timestamp_ns, 5000)
        self.assertEqual(events[1].timestamp_ns, 5001)
        self.assertEqual(adapter.snapshot_diagnostics().timestamp_adjustments, 1)
        adapter.close()

    async def test_read_error_aborts(self):
        self.factory.auto_eof = False
        kb_handle = FakeEventDeviceHandle("/dev/kb", [], auto_eof=False)
        self.factory.handles["/dev/kb"] = kb_handle
        
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        
        async def run_adapter():
            async for evt in adapter.read_events():
                pass
                
        task = asyncio.create_task(run_adapter())
        
        # Inject error
        await asyncio.sleep(0.01)
        kb_handle.inject_error(OSError("Read failed"))
        
        with self.assertRaises(InputReadError):
            await task
            
        self.assertTrue(kb_handle.closed)
        self.assertEqual(adapter.snapshot_diagnostics().read_errors, 1)

    async def test_cancellation_closes(self):
        self.factory.auto_eof = False
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        
        async def run_adapter():
            async for evt in adapter.read_events():
                pass
                
        task = asyncio.create_task(run_adapter())
        await asyncio.sleep(0.01)
        task.cancel()
        
        with self.assertRaises(asyncio.CancelledError):
            await task
            
        self.assertEqual(adapter.snapshot_diagnostics().close_count, 1)

    @patch.dict(sys.modules, {"evdev": None})
    def test_missing_evdev(self):
        with self.assertRaises(DependencyUnavailableError) as ctx:
            LinuxEvdevDeviceFactory()
        self.assertIsInstance(ctx.exception.__cause__, ImportError)

    def test_evdev_restored_after_patch(self):
        # Regression test for sys.modules isolation
        import evdev
        self.assertEqual(evdev.__class__.__name__, "FakeEvdev")

    async def test_mouse_open_fail_rollback(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [])
        self.factory.handles["/dev/ms"] = FakeEventDeviceHandle("/dev/ms", [])
        # Make mouse fail specifically
        class FailingMouseFactory(FakeEventDeviceFactory):
            def open(self, path):
                if path == "/dev/ms":
                    raise OSError("Mouse fail")
                return super().open(path)
                
        adapter = EvdevInputAdapter(self.idx, FailingMouseFactory(), self.clock)
        with self.assertRaises(InputOpenError):
            await adapter.start()
        # KB should be closed!
        self.assertTrue(adapter._handles.get("yyr4:keyboard") is None or adapter._closed)
        
    async def test_include_mouse_false(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock, include_mouse=False)
        await adapter.start()
        self.assertEqual(adapter.snapshot_diagnostics().opened_devices, 1)
        adapter.close()
        
    async def test_double_eof_finishes_iterator(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [])
        self.factory.handles["/dev/ms"] = FakeEventDeviceHandle("/dev/ms", [])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        events = []
        async for evt in adapter.read_events():
            events.append(evt)
        self.assertEqual(len(events), 0)
        
    async def test_task_leak_check(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [])
        self.factory.handles["/dev/ms"] = FakeEventDeviceHandle("/dev/ms", [])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        await adapter.start()
        adapter.close()
        # allow tasks to finish
        await asyncio.sleep(0.01)
        for t in adapter._tasks:
            self.assertTrue(t.done())

    def test_resolve_key_name_dict(self):
        from yyr4_linux_control.input.evdev_adapter import _resolve_key_name
        class Dummy:
            keys = {1: "KEY_ESC"}
        self.assertEqual(_resolve_key_name(1, Dummy()), "KEY_ESC")

    def test_resolve_key_name_list(self):
        from yyr4_linux_control.input.evdev_adapter import _resolve_key_name
        class Dummy:
            keys = {1: ["ESC", "KEY_ESC", "OTHER"]}
        self.assertEqual(_resolve_key_name(1, Dummy()), "KEY_ESC")
        
    def test_resolve_key_name_fallback_KEY(self):
        from yyr4_linux_control.input.evdev_adapter import _resolve_key_name
        class Dummy:
            KEY = {1: "KEY_ESC"}
        self.assertEqual(_resolve_key_name(1, Dummy()), "KEY_ESC")
        
    async def test_interleaved_events(self):
        self.factory.handles["/dev/kb"] = FakeEventDeviceHandle("/dev/kb", [KernelInputEvent(1, 183, 1)])
        self.factory.handles["/dev/ms"] = FakeEventDeviceHandle("/dev/ms", [KernelInputEvent(1, 42, 1)])
        adapter = EvdevInputAdapter(self.idx, self.factory, self.clock)
        events = []
        async for evt in adapter.read_events():
            events.append(evt)
        self.assertEqual(len(events), 2)
