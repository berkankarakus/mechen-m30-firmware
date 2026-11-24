#!/usr/bin/env python3
import unittest

from m30_model import (
    ArtworkSession,
    CardChangePolicy,
    DEFAULT_VOLUME_LIMIT,
    EQ_PRESETS,
    FIRMWARE_EQ_2024_04_PROFILE,
    FIRMWARE_EQ_BAND_HZ,
    FIRMWARE_EQ_CURRENT_PROFILE,
    FIRMWARE_EQ_SETTING_CUSTOM_ROW,
    FIRMWARE_EQ_ZEROED_BLOCK_CUSTOM,
    FIRMWARE_EQ_MESSAGE_ID,
    FIRMWARE_EQ_PRESETS,
    FIRMWARE_EQ_Q_VALUES,
    FIRMWARE_EQ_SELECTOR_OFFSET,
    IndexState,
    IndexStatus,
    MAX_VOLUME_LEVEL,
    SleepTimerPersistence,
    SleepTimerState,
    VolumeLimitState,
    adjust_firmware_eq_slider_gain,
    eq_names,
    find_eq,
    firmware_eq_gains,
    firmware_eq_gain_s16,
    build_firmware_eq_structure,
    firmware_eq_command,
    firmware_eq_payload,
    find_firmware_eq_profile,
    sort_filenames,
)


class FilenameOrderTests(unittest.TestCase):
    def test_numeric_runs_are_natural(self):
        names = ["Track 10.flac", "Track 2.flac", "Track 1.flac"]
        self.assertEqual(sort_filenames(names), ["Track 1.flac", "Track 2.flac", "Track 10.flac"])

    def test_extension_is_not_the_primary_sort_field(self):
        names = ["02 - Song.mp3", "01 - Song.flac", "10 - Song.ogg"]
        self.assertEqual(sort_filenames(names), ["01 - Song.flac", "02 - Song.mp3", "10 - Song.ogg"])

    def test_case_and_path_fallback_are_deterministic(self):
        names = ["/Music/zeta.MP3", "/Music/Alpha.mp3", "/Music/alpha.flac"]
        self.assertEqual(sort_filenames(names), ["/Music/alpha.flac", "/Music/Alpha.mp3", "/Music/zeta.MP3"])


class IndexStatusTests(unittest.TestCase):
    def test_manual_policy_never_starts_an_update_implicitly(self):
        status = IndexStatus()
        status.powered_card_reinserted()
        self.assertEqual(status.state, IndexState.DIRTY)
        self.assertEqual(status.progress, 0)
        self.assertIn("Manual", status.message)

    def test_observed_powered_reinsertion_starts_an_update(self):
        status = IndexStatus(card_change_policy=CardChangePolicy.AUTOMATIC_REBUILD)
        status.powered_card_reinserted(files_total=4)
        self.assertEqual(status.state, IndexState.UPDATING)
        self.assertEqual(status.files_total, 4)
        self.assertEqual(status.progress, 0)
        self.assertIn("powered card reinsertion", status.message)

    def test_automatic_powered_reinsertion_requires_a_file_count(self):
        status = IndexStatus(card_change_policy=CardChangePolicy.AUTOMATIC_REBUILD)
        with self.assertRaises(ValueError):
            status.powered_card_reinserted()

    def test_update_progress_and_completion(self):
        status = IndexStatus()
        status.begin(4)
        status.advance(1)
        status.advance(3)
        self.assertEqual(status.progress, 100)
        status.complete()
        self.assertEqual(status.state, IndexState.UP_TO_DATE)

    def test_incomplete_update_cannot_complete(self):
        status = IndexStatus()
        status.begin(2)
        status.advance(1)
        with self.assertRaises(RuntimeError):
            status.complete()


class VolumeLimitTests(unittest.TestCase):
    def test_documented_default_limit_is_full_volume_range(self):
        state = VolumeLimitState()

        self.assertEqual(DEFAULT_VOLUME_LIMIT, MAX_VOLUME_LEVEL)
        self.assertEqual(state.limit, 100)
        self.assertEqual(state.clamp(100), 100)

    def test_configured_limit_clamps_requested_volume(self):
        state = VolumeLimitState()

        state.set_limit(20)

        self.assertEqual(state.clamp(0), 0)
        self.assertEqual(state.clamp(20), 20)
        self.assertEqual(state.clamp(100), 20)

    def test_volume_limit_rejects_levels_outside_the_observed_range(self):
        with self.assertRaises(ValueError):
            VolumeLimitState(-1)
        with self.assertRaises(ValueError):
            VolumeLimitState(MAX_VOLUME_LEVEL + 1)

        state = VolumeLimitState()
        with self.assertRaises(ValueError):
            state.set_limit(MAX_VOLUME_LEVEL + 1)
        with self.assertRaises(ValueError):
            state.clamp(-1)


class SleepTimerTests(unittest.TestCase):
    def test_persistent_selection_survives_reboot(self):
        state = SleepTimerState()
        opaque_value = 30
        state.select(opaque_value)

        state.reboot()

        self.assertEqual(state.selected_value, opaque_value)

    def test_one_shot_selection_is_cleared_on_reboot(self):
        state = SleepTimerState(persistence=SleepTimerPersistence.ONE_SHOT)
        state.select(30)

        state.reboot()

        self.assertIsNone(state.selected_value)

    def test_reboot_does_not_claim_to_advance_elapsed_time(self):
        state = SleepTimerState(selected_value=30)

        state.reboot()

        self.assertEqual(state.selected_value, 30)


class EqCatalogTests(unittest.TestCase):
    def test_catalog_has_requested_named_presets(self):
        self.assertIn("Funk", eq_names())
        self.assertIn("Hip-Hop", eq_names())
        self.assertGreaterEqual(len(EQ_PRESETS), 12)

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(find_eq("rOcK").bands_db, (3, 2, -1, 2, 3))


class FirmwareEqContractTests(unittest.TestCase):
    def test_recovered_geometry_is_seven_band(self):
        self.assertEqual(FIRMWARE_EQ_BAND_HZ, (80, 200, 480, 980, 4000, 8000, 16000))
        self.assertEqual(FIRMWARE_EQ_Q_VALUES, (10, 6, 4, 6, 10, 5, 8))
        self.assertEqual(len(FIRMWARE_EQ_PRESETS), 8)

    def test_revision_profile_preserves_verified_2024_frequency_exception(self):
        self.assertEqual(FIRMWARE_EQ_CURRENT_PROFILE.band_hz[0], 80)
        self.assertEqual(FIRMWARE_EQ_2024_04_PROFILE.band_hz[0], 50)
        self.assertEqual(FIRMWARE_EQ_CURRENT_PROFILE.q_values, FIRMWARE_EQ_2024_04_PROFILE.q_values)
        self.assertEqual(FIRMWARE_EQ_CURRENT_PROFILE.presets, FIRMWARE_EQ_2024_04_PROFILE.presets)

    def test_revision_profile_lookup_is_case_insensitive(self):
        self.assertIs(
            find_firmware_eq_profile("2024-04"),
            FIRMWARE_EQ_2024_04_PROFILE,
        )
        with self.assertRaises(KeyError):
            find_firmware_eq_profile("unknown")

    def test_payload_matches_music_ap_selector_protocol(self):
        self.assertEqual(firmware_eq_payload("Off"), (0, 0))
        self.assertEqual(firmware_eq_payload("Rock"), (7, 1))
        self.assertEqual(firmware_eq_payload("Techno"), (7, 6))
        self.assertEqual(firmware_eq_payload("Custom"), (7, 7))

    def test_command_matches_verified_engine_message_boundary(self):
        command = firmware_eq_command("Custom")
        self.assertEqual(command.message_id, FIRMWARE_EQ_MESSAGE_ID)
        self.assertEqual((command.eq_type, command.selector), (7, 7))
        self.assertEqual(command.selector_source_offset, FIRMWARE_EQ_SELECTOR_OFFSET)

    def test_recovered_gain_rows_match_mengine(self):
        self.assertEqual(firmware_eq_gains(0), (0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(firmware_eq_gains(1), (5, 3, 0, -1, 0, 4, 5))
        self.assertEqual(firmware_eq_gains(6), (5, 2, 0, 0, 0, 0, 6))

    def test_custom_slider_steps_follow_the_signed_mips16_boundaries(self):
        expected_steps = (
            (-3, 0x2903, -2),
            (-3, 0x2904, -3),
            (-2, 0x2903, -1),
            (-2, 0x2904, -3),
            (-1, 0x2903, 0),
            (-1, 0x2904, -2),
            (0, 0x2903, 1),
            (0, 0x2904, -1),
            (1, 0x2903, 2),
            (1, 0x2904, 0),
            (2, 0x2903, 3),
            (2, 0x2904, 1),
            (3, 0x2903, 3),
            (3, 0x2904, 2),
        )

        for current_gain, event, expected_gain in expected_steps:
            with self.subTest(current_gain=current_gain, event=event):
                self.assertEqual(
                    adjust_firmware_eq_slider_gain(current_gain, event),
                    expected_gain,
                )

    def test_custom_slider_rejects_unobserved_gain_or_event(self):
        with self.assertRaises(ValueError):
            adjust_firmware_eq_slider_gain(4, 0x2903)

        with self.assertRaises(ValueError):
            adjust_firmware_eq_slider_gain(0, 0x2905)

    def test_builder_scales_signed_gain_bytes_into_signed_halfwords(self):
        custom = (1, 2, 3, -3, -2, 127, -128)

        self.assertEqual(
            firmware_eq_gain_s16(7, custom),
            (10, 20, 30, -30, -20, 1270, -1280),
        )

    def test_builder_matches_verified_structure_writes_and_preserves_unknown_bytes(self):
        initial = bytearray([0xAA] * 0xF0)
        initial[0x0C] = 0

        result = build_firmware_eq_structure(1, 1, bytes(initial))

        self.assertTrue(result.built)
        self.assertEqual(result.selector_copy, 1)
        self.assertEqual(result.structure[0x07], 1)
        self.assertEqual(result.structure[0x0C], 0)
        self.assertEqual(result.structure[0x0D], 1)
        self.assertEqual(result.structure[0x08:0x0C], bytes([0xAA] * 4))
        self.assertEqual(result.structure[0x0E:0x10], bytes([0xAA] * 2))
        self.assertEqual(result.structure[0x47], 0)
        self.assertEqual(result.structure[0x48:0x90], bytes(0x48))
        self.assertEqual(result.structure[0x90:], bytes([0xAA] * 0x60))

        first_band = (
            bytes.fromhex("50000a003200")
            + bytes((1, 0))
        )
        self.assertEqual(result.structure[0x10:0x18], first_band)

    def test_builder_selector_zero_sets_inactive_header_and_zero_gains(self):
        initial = bytearray([0xAA] * 0xF0)
        initial[0x0C] = 0

        result = build_firmware_eq_structure(0, 1, bytes(initial))

        self.assertTrue(result.built)
        self.assertEqual(result.structure[0x0D], 0)
        self.assertEqual(result.structure[0x10 + 4:0x10 + 6], bytes(2))

    def test_builder_gates_leave_structure_unchanged_after_selector_mirror(self):
        busy_structure = bytearray([0xAA] * 0xF0)
        busy_structure[0x0C] = 1
        inactive_structure = bytearray([0xAA] * 0xF0)
        inactive_structure[0x0C] = 0

        busy = build_firmware_eq_structure(3, 1, bytes(busy_structure))
        inactive = build_firmware_eq_structure(3, 0, bytes(inactive_structure))

        self.assertFalse(busy.built)
        self.assertEqual(busy.selector_copy, 3)
        self.assertEqual(busy.structure, bytes(busy_structure))
        self.assertFalse(inactive.built)
        self.assertEqual(inactive.selector_copy, 3)
        self.assertEqual(inactive.structure, bytes(inactive_structure))

    def test_custom_requires_exactly_seven_signed_int8_values(self):
        custom = FIRMWARE_EQ_ZEROED_BLOCK_CUSTOM

        self.assertEqual(custom, (0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(
            FIRMWARE_EQ_CURRENT_PROFILE.setting_custom_row,
            FIRMWARE_EQ_SETTING_CUSTOM_ROW,
        )
        self.assertNotEqual(custom, FIRMWARE_EQ_SETTING_CUSTOM_ROW)
        self.assertIsNone(FIRMWARE_EQ_2024_04_PROFILE.setting_custom_row)
        self.assertEqual(firmware_eq_gains(7, custom), custom)
        self.assertEqual(
            firmware_eq_gains(
                7,
                custom,
                profile=FIRMWARE_EQ_2024_04_PROFILE,
            ),
            custom,
        )
        with self.assertRaises(ValueError):
            firmware_eq_gains(7, (0, 0, 0))
        with self.assertRaises(ValueError):
            firmware_eq_gains(7, (0, 0, 0, 0, 0, 0, 128))
        with self.assertRaises(ValueError):
            firmware_eq_gains(8)


class ArtworkLatencyTests(unittest.TestCase):
    def test_audio_starts_before_artwork_decode(self):
        session = ArtworkSession()
        session.start_track(has_artwork=True)
        self.assertEqual(session.events, ["audio-start", "artwork-placeholder"])
        session.decode_chunk()
        self.assertTrue(session.ui_blocked)
        session.finish_artwork()
        self.assertEqual(session.artwork_state, "ready")
        self.assertFalse(session.ui_blocked)
        self.assertEqual(session.events[0], "audio-start")

    def test_missing_artwork_does_not_block_playback(self):
        session = ArtworkSession()
        session.start_track(has_artwork=False)
        self.assertTrue(session.audio_started)
        self.assertEqual(session.artwork_state, "none")

    def test_decode_cannot_run_before_audio(self):
        session = ArtworkSession(artwork_state="pending")
        with self.assertRaises(RuntimeError):
            session.decode_chunk()


if __name__ == "__main__":
    unittest.main()
