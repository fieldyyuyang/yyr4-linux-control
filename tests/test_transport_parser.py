import unittest
import json
from yyr4_linux_control.transport.parser import TransportParser
from yyr4_linux_control.domain.events import RawKeyEvent, ControlPhase

class TestTransportParser(unittest.TestCase):
    def setUp(self):
        with open("tests/fixtures/m010_transport_streams.json") as f:
            self.fixtures = json.load(f)["scenarios"]

    def _feed_scenario(self, parser, name):
        events = []
        for e in self.fixtures[name]:
            events.extend(parser.feed(RawKeyEvent(**e)))
        return events

    def test_a1_normal(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "1_A1_normal")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "button.k01")
        self.assertEqual(evts[0].phase, ControlPhase.DOWN)
        self.assertEqual(evts[1].phase, ControlPhase.UP)
        self.assertEqual(p.error_count, 0)

    def test_a2_repeat_ignored(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "2_A2_repeat")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "button.k02")
        self.assertEqual(p.repeat_count, 1)

    def test_a12_normal(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "3_A12_normal")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "button.k12")

    def test_al_special_release(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "4_AL_special_release")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "encoder.e01.counterclockwise")
        self.assertEqual(evts[0].phase, ControlPhase.DOWN)
        self.assertEqual(evts[1].phase, ControlPhase.UP)
        self.assertFalse(p._shift_active)
        self.assertEqual(p.error_count, 0)

    def test_ap_standard_release(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "5_AP_standard_release")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "encoder.e01.press")
        self.assertFalse(p._shift_active)

    def test_continuous_shift(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "8_continuous_shift")
        self.assertEqual(len(evts), 4)
        self.assertEqual(evts[0].control.control_id, "encoder.e01.counterclockwise")
        self.assertEqual(evts[1].phase, ControlPhase.UP)
        self.assertEqual(evts[2].control.control_id, "encoder.e01.counterclockwise")
        self.assertEqual(evts[3].phase, ControlPhase.UP)

    def test_shift_timeout(self):
        p = TransportParser(source_id="yyr4", modifier_timeout_ms=100)
        evts = self._feed_scenario(p, "9_shift_timeout")
        self.assertEqual(len(evts), 2)
        # Shift timed out before F13 arrived, so F13 alone is parsed as A1!
        self.assertEqual(evts[0].control.control_id, "button.k01")
        self.assertEqual(p.modifier_timeouts, 1)

    def test_orphan_release(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "10_orphan_release")
        self.assertEqual(len(evts), 0)
        self.assertEqual(p.orphan_releases, 1)

    def test_duplicate_down(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "11_duplicate_down")
        self.assertEqual(len(evts), 2)
        self.assertEqual(p.duplicate_downs, 1)

    def test_other_source(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "13_other_source")
        self.assertEqual(len(evts), 2)
        # Because main_kbd shift was ignored, it should map to A1 (F13 without shift)
        self.assertEqual(evts[0].control.control_id, "button.k01")

    def test_unrelated_key(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "14_unrelated_key")
        self.assertEqual(len(evts), 0)
        self.assertEqual(p.error_count, 0) # KEY_A is completely ignored

    def test_reset(self):
        p = TransportParser(source_id="yyr4")
        p.feed(RawKeyEvent(source_id="yyr4", timestamp_ns=1000, code="KEY_F13", value=1))
        self.assertEqual(len(p._active_f_keys), 1)
        evts = p.reset(timestamp_ns=2000)
        self.assertEqual(len(evts), 1)
        self.assertTrue(evts[0].synthetic)
        self.assertEqual(evts[0].phase, ControlPhase.UP)
        self.assertEqual(len(p._active_f_keys), 0)

        # idempotent
        evts2 = p.reset(timestamp_ns=3000)
        self.assertEqual(len(evts2), 0)

    def test_active_control_disconnect(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "12_active_control_disconnect")
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0].phase, ControlPhase.DOWN)
        resets = p.reset(timestamp_ns=2000000)
        self.assertEqual(len(resets), 1)
        self.assertEqual(resets[0].phase, ControlPhase.UP)

    def test_f1_to_f12_ignored(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "15_f1_to_f12")
        self.assertEqual(len(evts), 0)
        self.assertEqual(p.error_count, 2)

    def test_unsupported_code(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "16_unsupported_code")
        self.assertEqual(len(evts), 0)

    def test_shift_repeat(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "17_shift_repeat")
        self.assertEqual(len(evts), 2)
        self.assertEqual(evts[0].control.control_id, "encoder.e01.counterclockwise")
        self.assertEqual(p.repeat_count, 1)

    def test_time_regression(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "18_time_regression")
        self.assertEqual(len(evts), 1)
        self.assertEqual(evts[0].phase, ControlPhase.DOWN)
        self.assertEqual(p.timestamp_regressions, 1)

    def test_multiple_active_f_keys(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "19_multiple_active_f_keys")
        self.assertEqual(len(evts), 4)
        self.assertEqual(evts[0].control.control_id, "button.k01")
        self.assertEqual(evts[1].control.control_id, "button.k02")
        self.assertEqual(evts[2].phase, ControlPhase.UP)
        self.assertEqual(evts[2].control.control_id, "button.k01")
        self.assertEqual(evts[3].phase, ControlPhase.UP)
        self.assertEqual(evts[3].control.control_id, "button.k02")

    def test_shift_down_without_up(self):
        p = TransportParser(source_id="yyr4")
        evts = self._feed_scenario(p, "20_shift_down_without_up")
        self.assertEqual(len(evts), 0)
        self.assertTrue(p._shift_active)
        p.reset()
        self.assertFalse(p._shift_active)

    def test_all_button_mappings(self):
        # Programmatically test A1-A12
        p = TransportParser(source_id="yyr4")
        for i in range(13, 25):
            evts = p.feed(RawKeyEvent("yyr4", i*1000, f"KEY_F{i}", 1))
            self.assertEqual(len(evts), 1)
            self.assertEqual(evts[0].control.control_id, f"button.k{i-12:02d}")
            p.feed(RawKeyEvent("yyr4", i*1000 + 100, f"KEY_F{i}", 0))

    def test_all_encoder_mappings(self):
        # Programmatically test 12 encoder actions
        p = TransportParser(source_id="yyr4")
        for i in range(13, 25):
            p.feed(RawKeyEvent("yyr4", i*1000, "KEY_LEFTSHIFT", 1))
            evts = p.feed(RawKeyEvent("yyr4", i*1000 + 10, f"KEY_F{i}", 1))
            self.assertEqual(len(evts), 1)
            self.assertTrue(evts[0].control.control_id.startswith("encoder.e"))
            p.feed(RawKeyEvent("yyr4", i*1000 + 20, f"KEY_F{i}", 0))
            p.feed(RawKeyEvent("yyr4", i*1000 + 30, "KEY_LEFTSHIFT", 0))
