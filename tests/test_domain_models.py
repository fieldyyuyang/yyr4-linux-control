import unittest
from yyr4_linux_control.domain.controls import PhysicalControl, ControlKind, ControlPhase
from yyr4_linux_control.domain.events import RawKeyEvent, ControlEvent

class TestDomainModels(unittest.TestCase):
    def test_physical_control_valid_button(self):
        btn = PhysicalControl(
            control_id="button.k01",
            vendor_name="A1",
            kind=ControlKind.BUTTON,
            button_index=1
        )
        self.assertEqual(btn.control_id, "button.k01")

    def test_physical_control_valid_encoder(self):
        enc = PhysicalControl(
            control_id="encoder.e01.press",
            vendor_name="AP",
            kind=ControlKind.ENCODER_PRESS,
            encoder_index=1
        )
        self.assertEqual(enc.encoder_index, 1)

    def test_physical_control_invalid_button_index(self):
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="x", kind=ControlKind.BUTTON, button_index=13)
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="x", kind=ControlKind.BUTTON, button_index=0)

    def test_physical_control_invalid_encoder_index(self):
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="x", kind=ControlKind.ENCODER_PRESS, encoder_index=5)

    def test_physical_control_button_with_encoder_index(self):
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="x", kind=ControlKind.BUTTON, button_index=1, encoder_index=1)

    def test_physical_control_encoder_with_button_index(self):
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="x", kind=ControlKind.ENCODER_PRESS, encoder_index=1, button_index=1)

    def test_physical_control_empty_strings(self):
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="", vendor_name="x", kind=ControlKind.BUTTON, button_index=1)
        with self.assertRaises(ValueError):
            PhysicalControl(control_id="x", vendor_name="", kind=ControlKind.BUTTON, button_index=1)

    def test_raw_key_event_valid(self):
        evt = RawKeyEvent(source_id="yyr4", timestamp_ns=1000, code="KEY_A", value=1)
        self.assertEqual(evt.source_id, "yyr4")

    def test_raw_key_event_empty_source(self):
        with self.assertRaises(ValueError):
            RawKeyEvent(source_id="", timestamp_ns=1000, code="KEY_A", value=1)

    def test_raw_key_event_negative_timestamp(self):
        with self.assertRaises(ValueError):
            RawKeyEvent(source_id="yyr4", timestamp_ns=-1, code="KEY_A", value=1)

    def test_raw_key_event_empty_code(self):
        with self.assertRaises(ValueError):
            RawKeyEvent(source_id="yyr4", timestamp_ns=1000, code="", value=1)

    def test_raw_key_event_invalid_value(self):
        with self.assertRaises(ValueError):
            RawKeyEvent(source_id="yyr4", timestamp_ns=1000, code="KEY_A", value=3)

    def test_control_event_valid(self):
        from yyr4_linux_control.transport.codebook import TransportCode
        ctrl = PhysicalControl("button.k01", "A1", ControlKind.BUTTON, button_index=1)
        evt = ControlEvent("yyr4", 1000, ctrl, ControlPhase.DOWN, TransportCode("KEY_A"))
        self.assertEqual(evt.source_id, "yyr4")

    def test_control_event_negative_timestamp(self):
        from yyr4_linux_control.transport.codebook import TransportCode
        ctrl = PhysicalControl("button.k01", "A1", ControlKind.BUTTON, button_index=1)
        with self.assertRaises(ValueError):
            ControlEvent("yyr4", -10, ctrl, ControlPhase.DOWN, TransportCode("KEY_A"))

    def test_control_event_synthetic_without_reason(self):
        from yyr4_linux_control.transport.codebook import TransportCode
        ctrl = PhysicalControl("button.k01", "A1", ControlKind.BUTTON, button_index=1)
        with self.assertRaises(ValueError):
            ControlEvent("yyr4", 1000, ctrl, ControlPhase.DOWN, TransportCode("KEY_A"), synthetic=True)

    def test_control_event_non_synthetic_with_reason(self):
        from yyr4_linux_control.transport.codebook import TransportCode
        ctrl = PhysicalControl("button.k01", "A1", ControlKind.BUTTON, button_index=1)
        with self.assertRaises(ValueError):
            ControlEvent("yyr4", 1000, ctrl, ControlPhase.DOWN, TransportCode("KEY_A"), synthetic=False, reason="x")

    def test_control_event_unstructured_transport_code(self):
        ctrl = PhysicalControl("button.k01", "A1", ControlKind.BUTTON, button_index=1)
        with self.assertRaises(ValueError):
            ControlEvent("yyr4", 1000, ctrl, ControlPhase.DOWN, transport_code="KEY_A")
