import unittest

from status_notifications import (
    STATUS_TWO_NOTIFICATION,
    STATUS_ZERO_NOTIFICATION,
    StatusNotifier,
)


class StatusNotifierTests(unittest.TestCase):
    def test_status_zero_notifies_on_tick_120_then_restarts(self):
        notifier = StatusNotifier()

        for tick in range(1, 120):
            with self.subTest(tick=tick):
                result = notifier.tick(sampled_status=0, sampled_level=0)
                self.assertIsNone(result.event)

        result = notifier.tick(sampled_status=0, sampled_level=0)

        self.assertEqual(result.event, STATUS_ZERO_NOTIFICATION)
        self.assertFalse(result.refresh_key_status)
        self.assertFalse(result.state_changed)
        self.assertIsNone(notifier.tick(sampled_status=0, sampled_level=0).event)

    def test_status_two_level_below_six_refreshes_every_eight_ticks(self):
        notifier = StatusNotifier(status=2, level=5)
        refresh_count = 0

        for _ in range(120):
            result = notifier.tick(sampled_status=2, sampled_level=5)
            refresh_count += result.refresh_key_status

            self.assertIsNone(result.event)

        self.assertEqual(refresh_count, 15)

    def test_status_two_level_six_notifies_on_tick_120_without_refresh(self):
        notifier = StatusNotifier(status=2, level=6)

        for tick in range(1, 120):
            result = notifier.tick(sampled_status=2, sampled_level=6)
            self.assertIsNone(result.event, f"event arrived early at tick {tick}")
            self.assertFalse(result.refresh_key_status)

        result = notifier.tick(sampled_status=2, sampled_level=6)

        self.assertEqual(result.event, STATUS_TWO_NOTIFICATION)
        self.assertFalse(result.refresh_key_status)

    def test_status_zero_level_is_capped_by_its_saved_level(self):
        notifier = StatusNotifier(status=0, level=2, _status_zero_ticks=9)

        result = notifier.tick(sampled_status=0, sampled_level=6)

        self.assertFalse(result.state_changed)
        self.assertEqual((result.status, result.level), (0, 2))
        self.assertIsNone(result.event)
        self.assertEqual(notifier._status_zero_ticks, 0)

    def test_status_four_is_normalized_to_zero_with_level_six(self):
        notifier = StatusNotifier(status=1, level=3, _status_zero_ticks=44)

        result = notifier.tick(sampled_status=4, sampled_level=3)

        self.assertTrue(result.state_changed)
        self.assertEqual((result.status, result.level), (0, 6))
        self.assertEqual(notifier._status_zero_ticks, 44)

        stable_result = notifier.tick(sampled_status=4, sampled_level=3)

        self.assertFalse(stable_result.state_changed)
        self.assertEqual(notifier._status_zero_ticks, 0)

    def test_transition_to_status_zero_level_zero_resets_its_timer(self):
        notifier = StatusNotifier(status=1, level=3, _status_zero_ticks=40)

        transition = notifier.tick(sampled_status=0, sampled_level=0)

        self.assertTrue(transition.state_changed)
        self.assertEqual(notifier._status_zero_ticks, 0)

        for tick in range(1, 120):
            result = notifier.tick(sampled_status=0, sampled_level=0)
            self.assertIsNone(result.event, f"event arrived early at tick {tick}")

        self.assertEqual(
            notifier.tick(sampled_status=0, sampled_level=0).event,
            STATUS_ZERO_NOTIFICATION,
        )

    def test_entering_status_two_resets_its_timer(self):
        notifier = StatusNotifier(status=1, level=3, _status_two_ticks=119)

        result = notifier.tick(sampled_status=2, sampled_level=5)

        self.assertTrue(result.state_changed)
        self.assertEqual((notifier.status, notifier.level), (2, 5))
        self.assertEqual(notifier._status_two_ticks, 0)

    def test_status_two_level_change_carries_its_timer(self):
        notifier = StatusNotifier(status=2, level=5, _status_two_ticks=119)

        transition = notifier.tick(sampled_status=2, sampled_level=6)

        self.assertTrue(transition.state_changed)
        self.assertEqual(notifier._status_two_ticks, 119)

        result = notifier.tick(sampled_status=2, sampled_level=6)

        self.assertEqual(result.event, STATUS_TWO_NOTIFICATION)

    def test_status_two_refresh_threshold_uses_raw_sample_level(self):
        notifier = StatusNotifier(status=2, level=6)

        for _ in range(8):
            result = notifier.tick(sampled_status=2, sampled_level=7)

        self.assertFalse(result.refresh_key_status)
        self.assertIsNone(result.event)
        self.assertEqual((notifier.status, notifier.level), (2, 6))
        self.assertEqual(notifier._status_two_ticks, 8)

    def test_rejects_unmodeled_status_and_levels_outside_one_byte(self):
        notifier = StatusNotifier()

        with self.assertRaises(ValueError):
            notifier.tick(sampled_status=3, sampled_level=6)

        with self.assertRaises(ValueError):
            notifier.tick(sampled_status=2, sampled_level=256)


if __name__ == "__main__":
    unittest.main()
