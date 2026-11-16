#!/usr/bin/env python3
import unittest

from m30_model import (
    ArtworkSession,
    CardChangePolicy,
    EQ_PRESETS,
    FIRMWARE_EQ_2024_04_PROFILE,
    FIRMWARE_EQ_BAND_HZ,
    FIRMWARE_EQ_CUSTOM_DEFAULT,
    FIRMWARE_EQ_CURRENT_PROFILE,
    FIRMWARE_EQ_MESSAGE_ID,
    FIRMWARE_EQ_PRESETS,
    FIRMWARE_EQ_Q_X10,
    FIRMWARE_EQ_SELECTOR_OFFSET,
    IndexState,
    IndexStatus,
    eq_names,
    find_eq,
    firmware_eq_gains,
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
        status.card_changed()
        self.assertEqual(status.state, IndexState.DIRTY)
        self.assertEqual(status.progress, 0)
        self.assertIn("Manual", status.message)

    def test_observed_automatic_card_change_starts_an_update(self):
        status = IndexStatus(card_change_policy=CardChangePolicy.AUTOMATIC_REBUILD)
        status.card_changed(files_total=4)
        self.assertEqual(status.state, IndexState.UPDATING)
        self.assertEqual(status.files_total, 4)
        self.assertEqual(status.progress, 0)
        self.assertIn("card change", status.message)

    def test_automatic_card_change_requires_a_file_count(self):
        status = IndexStatus(card_change_policy=CardChangePolicy.AUTOMATIC_REBUILD)
        with self.assertRaises(ValueError):
            status.card_changed()

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
        self.assertEqual(FIRMWARE_EQ_Q_X10, (10, 6, 4, 6, 10, 5, 8))
        self.assertEqual(len(FIRMWARE_EQ_PRESETS), 8)

    def test_revision_profile_preserves_verified_2024_frequency_exception(self):
        self.assertEqual(FIRMWARE_EQ_CURRENT_PROFILE.band_hz[0], 80)
        self.assertEqual(FIRMWARE_EQ_2024_04_PROFILE.band_hz[0], 50)
        self.assertEqual(FIRMWARE_EQ_CURRENT_PROFILE.q_x10, FIRMWARE_EQ_2024_04_PROFILE.q_x10)
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

    def test_custom_requires_exactly_seven_signed_int8_values(self):
        custom = FIRMWARE_EQ_CUSTOM_DEFAULT
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
        session.finish_artwork()
        self.assertEqual(session.artwork_state, "ready")
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
