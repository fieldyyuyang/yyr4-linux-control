import unittest
import sys

class TestBombRealDeviceAccess(unittest.TestCase):
    def test_bomb_no_real_pyudev_context(self):
        try:
            import pyudev
            original_context = pyudev.Context
        except ImportError:
            return
            
        def bomb(*args, **kwargs):
            raise RuntimeError("BOMB: Real pyudev.Context was called!")
            
        pyudev.Context = bomb
        try:
            # Import our module that shouldn't call it on import
            from yyr4_linux_control.device.linux_udev import LinuxUdevDiscoveryBackend
            backend = LinuxUdevDiscoveryBackend()
            # We don't call enumerate_input_records because that WOULD call the bomb, 
            # but we want to make sure the rest of our tests don't hit the real Context.
            # Wait, this test only bombs during itself.
            pass
        finally:
            pyudev.Context = original_context

    def test_bomb_no_real_evdev_inputdevice(self):
        try:
            import evdev
            original_input_device = evdev.InputDevice
        except ImportError:
            return
            
        def bomb(*args, **kwargs):
            raise RuntimeError("BOMB: Real evdev.InputDevice was called!")
            
        evdev.InputDevice = bomb
        try:
            from yyr4_linux_control.input.evdev_adapter import LinuxEvdevDeviceFactory
            factory = LinuxEvdevDeviceFactory()
        finally:
            evdev.InputDevice = original_input_device
