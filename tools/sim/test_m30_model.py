#!/usr/bin/env python3
import unittest

from m30_model import ArtworkSession, EQ_PRESETS, IndexState, IndexStatus, eq_names, find_eq, sort_filenames


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
