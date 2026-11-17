import struct
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SIM = ROOT / "tools/sim"
if str(SIM) not in sys.path:
    sys.path.insert(0, str(SIM))

from library_index_sort import INDEX_TEXT_CONVERSION_STOP_ZERO, SECTION_SPECS
from library_tie_refinement_probe import (
    compare_library,
    compare_library_conversion_matrix,
    compare_library_section_modes,
)


SECTOR_SIZE = 512


def make_single_record_library() -> bytes:
    data = bytearray(6 * SECTOR_SIZE)
    struct.pack_into("<H", data, 0x08, 1)

    for section_index, (section_name, _) in enumerate(SECTION_SPECS.items()):
        section_offset = 0x10 + section_index * 0x1C
        data[section_offset : section_offset + 8] = section_name.encode("ascii").ljust(8, b"\0")
        table_sector = 2 + section_index
        struct.pack_into("<H", data, section_offset + 20, table_sector)
        struct.pack_into("<H", data, table_sector * SECTOR_SIZE, 0)

    return bytes(data)


class LibraryTieRefinementProbeTests(unittest.TestCase):
    def test_global_mode_comparison_preserves_existing_summary_shape(self) -> None:
        summary = compare_library(
            make_single_record_library(),
            conversion_mode=INDEX_TEXT_CONVERSION_STOP_ZERO,
        )

        self.assertEqual("stop-zero", summary["conversion_mode"])
        self.assertEqual(1, summary["record_count"])
        self.assertEqual(4, len(summary["sections"]))

    def test_section_modes_require_each_music_library_section(self) -> None:
        with self.assertRaises(ValueError):
            compare_library_section_modes(
                make_single_record_library(),
                {"ALLSONG": INDEX_TEXT_CONVERSION_STOP_ZERO},
            )

    def test_conversion_matrix_covers_all_sixteen_section_mode_combinations(self) -> None:
        results = compare_library_conversion_matrix(make_single_record_library())
        selections = {
            tuple(result["conversion_modes"][section_name] for section_name in SECTION_SPECS)
            for result in results
        }

        self.assertEqual(16, len(results))
        self.assertEqual(16, len(selections))

        for result in results:
            for section in result["sections"].values():
                self.assertEqual(1, section["matching_entries"])
                self.assertIsNone(section["first_mismatch"])

    def test_chained_matrix_uses_candidate_rank_for_later_sections(self) -> None:
        results = compare_library_conversion_matrix(
            make_single_record_library(),
            candidate_rank_chaining=True,
        )

        self.assertEqual(16, len(results))

        for result in results:
            self.assertEqual("candidate-previous-section", result["rank_source"])


if __name__ == "__main__":
    unittest.main()
