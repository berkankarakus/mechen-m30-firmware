import unittest

from ui_calls import classify


class UiCallTests(unittest.TestCase):
    def test_font_switch_and_measurement_share_a19(self):
        switch = classify(0x164C90ED)
        measure = classify(0x164C9001)
        self.assertIsNotNone(switch)
        self.assertIsNotNone(measure)
        self.assertEqual(switch.candidates, ("fix_switch_fontlib",))
        self.assertEqual(measure.candidates, ("fixf_get_string_length",))
        self.assertEqual(switch.bank.bank_type, "A")
        self.assertEqual(switch.bank.bank_index, 19)
        self.assertEqual(measure.bank.bank_index, 19)

    def test_b2_preprocessing_order(self):
        first = classify(0x26089471)
        second = classify(0x260894E9)
        self.assertEqual(first.candidates, ("arabic_uni_join",))
        self.assertEqual(second.candidates, ("arabic_ascii_turn",))
        self.assertEqual(first.bank.bank_index, 2)
        self.assertEqual(second.bank.bank_index, 2)
        self.assertEqual(first.bank.payload_offset, 0x471)
        self.assertEqual(second.bank.payload_offset, 0x4E9)

    def test_b16_sdimage_renderer(self):
        call = classify(0x26409401)
        self.assertEqual(call.candidates, ("put_string_line_sdimage",))
        self.assertEqual(call.bank.bank_type, "B")
        self.assertEqual(call.bank.bank_index, 16)
        self.assertEqual(call.bank.payload_offset, 0x401)
        self.assertEqual(call.confidence, "high")

    def test_unknown_pointer_is_not_guessed(self):
        self.assertIsNone(classify(0x260E4FF4))


if __name__ == "__main__":
    unittest.main()
