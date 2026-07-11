import unittest
from yyr4_linux_control.transport.codebook import DEFAULT_CODEBOOK, TransportCode

class TestCodebook(unittest.TestCase):
    def test_exactly_24_mappings(self):
        self.assertEqual(len(DEFAULT_CODEBOOK._mappings), 24)

    def test_all_f13_to_f24_used(self):
        used = set()
        for code in DEFAULT_CODEBOOK._mappings.keys():
            used.add(code.primary_key)
        expected = {f"KEY_F{i}" for i in range(13, 25)}
        self.assertEqual(used, expected)

    def test_unique_vendor_names(self):
        names = set()
        for ctrl in DEFAULT_CODEBOOK._mappings.values():
            self.assertNotIn(ctrl.vendor_name, names)
            names.add(ctrl.vendor_name)
        self.assertEqual(len(names), 24)

    def test_unique_control_ids(self):
        ids = set()
        for ctrl in DEFAULT_CODEBOOK._mappings.values():
            self.assertNotIn(ctrl.control_id, ids)
            ids.add(ctrl.control_id)
        self.assertEqual(len(ids), 24)

    def test_unique_transport_codes(self):
        codes = set()
        for code in DEFAULT_CODEBOOK._mappings.keys():
            self.assertNotIn(code.string_repr, codes)
            codes.add(code.string_repr)
        self.assertEqual(len(codes), 24)

    def test_encoder_mappings_correctness(self):
        # AL (idx 1, CCW) = LSHIFT+F13
        al = DEFAULT_CODEBOOK.get_by_vendor_name("AL")
        self.assertIsNotNone(al)
        self.assertEqual(al.control_id, "encoder.e01.counterclockwise")
        code = DEFAULT_CODEBOOK.get_code_for_control_id(al.control_id)
        self.assertEqual(code.primary_key, "KEY_F13")
        self.assertEqual(code.required_modifiers, ("KEY_LEFTSHIFT",))

        # AP (idx 1, Press) = LSHIFT+F14
        ap = DEFAULT_CODEBOOK.get_by_vendor_name("AP")
        self.assertEqual(ap.control_id, "encoder.e01.press")
        code = DEFAULT_CODEBOOK.get_code_for_control_id(ap.control_id)
        self.assertEqual(code.primary_key, "KEY_F14")

        # AR (idx 1, CW) = LSHIFT+F15
        ar = DEFAULT_CODEBOOK.get_by_vendor_name("AR")
        self.assertEqual(ar.control_id, "encoder.e01.clockwise")
        code = DEFAULT_CODEBOOK.get_code_for_control_id(ar.control_id)
        self.assertEqual(code.primary_key, "KEY_F15")

        # DL (idx 4, CCW) = LSHIFT+F22
        dl = DEFAULT_CODEBOOK.get_by_vendor_name("DL")
        self.assertEqual(dl.control_id, "encoder.e04.counterclockwise")
        code = DEFAULT_CODEBOOK.get_code_for_control_id(dl.control_id)
        self.assertEqual(code.primary_key, "KEY_F22")

    def test_button_mappings(self):
        a1 = DEFAULT_CODEBOOK.get_by_vendor_name("A1")
        self.assertEqual(a1.control_id, "button.k01")
        code = DEFAULT_CODEBOOK.get_code_for_control_id(a1.control_id)
        self.assertEqual(code.primary_key, "KEY_F13")
        self.assertEqual(code.required_modifiers, ())
