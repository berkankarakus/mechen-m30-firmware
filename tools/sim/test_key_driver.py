import unittest

from key_driver import ADC_THRESHOLDS, classify_adc_sample


class KeyDriverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.normalized_values = (1, 2, 3, 4, 5, 6, 7)

    def test_thresholds_select_the_first_greater_entry(self):
        result = classify_adc_sample(ADC_THRESHOLDS[2] - 1, self.normalized_values)

        self.assertEqual(result.sampled_value, ADC_THRESHOLDS[2] - 1)
        self.assertEqual(result.normalized_value, 3)
        self.assertFalse(result.override_applied)

    def test_sample_is_masked_to_seven_bits_before_classification(self):
        result = classify_adc_sample(0x80 | 0x02, self.normalized_values)

        self.assertEqual(result.sampled_value, 2)
        self.assertEqual(result.normalized_value, 1)

    def test_unmatched_sample_returns_ff(self):
        result = classify_adc_sample(0x7F, self.normalized_values)

        self.assertEqual(result.normalized_value, 0xFF)

    def test_override_uses_an_explicit_external_table_value(self):
        result = classify_adc_sample(
            0x40,
            self.normalized_values,
            override=True,
            override_value=0x22,
        )

        self.assertEqual((result.sampled_value, result.normalized_value), (0, 0x22))
        self.assertTrue(result.override_applied)


if __name__ == "__main__":
    unittest.main()
