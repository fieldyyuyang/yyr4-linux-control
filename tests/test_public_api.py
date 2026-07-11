import unittest

class TestPublicApi(unittest.TestCase):
    def test_imports(self):
        import yyr4_linux_control
        self.assertEqual(yyr4_linux_control.__version__, "0.1.0.dev0")

        # Verify all exported symbols are accessible
        from yyr4_linux_control import (
            PhysicalControl,
            ControlKind,
            ControlPhase,
            RawKeyEvent,
            ControlEvent,
            DEFAULT_CODEBOOK,
            TransportCode,
            Codebook,
            TransportParser,
        )

        # Verify we can construct a minimal parser flow
        parser = TransportParser("test")
        evts = parser.feed(RawKeyEvent("test", 1000, "KEY_F13", 1))
        self.assertEqual(len(evts), 1)
        self.assertTrue(hasattr(evts[0].transport_code, "primary_key"))
