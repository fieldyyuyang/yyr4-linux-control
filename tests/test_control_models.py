import unittest
from yyr4_linux_control.domain.controls import PhysicalControl, ControlKind
from yyr4_linux_control.domain.events import ControlEvent, ControlPhase
from yyr4_linux_control.transport.codebook import TransportCode
from yyr4_linux_control.control.models import OfficialControl, OfficialControlEvent

class TestControlModels(unittest.TestCase):
    def test_official_control_names(self):
        self.assertEqual(len(OfficialControl), 24)
        for i in range(1, 13):
            self.assertEqual(OfficialControl(f"A{i}"), getattr(OfficialControl, f"A{i}"))
        for enc in ["AL", "AP", "AR", "BL", "BP", "BR", "CL", "CP", "CR", "DL", "DP", "DR"]:
            self.assertEqual(OfficialControl(enc), getattr(OfficialControl, enc))

    def test_from_physical_control_success(self):
        pc = PhysicalControl(
            control_id="button.k01",
            vendor_name="A1",
            kind=ControlKind.BUTTON,
            button_index=1
        )
        oc = OfficialControl.from_physical_control(pc)
        self.assertEqual(oc, OfficialControl.A1)

    def test_from_physical_control_unknown(self):
        pc = PhysicalControl(
            control_id="button.unknown",
            vendor_name="UNKNOWN_VENDOR",
            kind=ControlKind.BUTTON,
            button_index=1
        )
        with self.assertRaisesRegex(ValueError, "Unknown physical control vendor_name"):
            OfficialControl.from_physical_control(pc)

    def test_official_control_event(self):
        pc = PhysicalControl(
            control_id="button.k01",
            vendor_name="A1",
            kind=ControlKind.BUTTON,
            button_index=1
        )
        ce = ControlEvent(
            source_id="test",
            timestamp_ns=123,
            control=pc,
            phase=ControlPhase.DOWN,
            transport_code=TransportCode("KEY_F13")
        )
        oce = OfficialControlEvent.from_control_event(ce)
        self.assertEqual(oce.control, OfficialControl.A1)
        self.assertEqual(oce.phase, ControlPhase.DOWN)
        self.assertEqual(oce.timestamp_ns, 123)
        self.assertFalse(hasattr(oce, "source_id"))
        self.assertFalse(hasattr(oce, "transport_code"))
