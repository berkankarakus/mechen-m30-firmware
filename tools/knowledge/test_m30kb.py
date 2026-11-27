import unittest

from m30kb import reference_ids, validate_rows


class KnowledgeFactValidationTests(unittest.TestCase):
    def test_rejects_function_without_reproduce_field(self):
        row = {
            "type": "function", "id": "module:0x10", "module": "module",
            "variant": "v1", "sha256": "abc", "address": "0x10",
            "symbol": "FUN_10", "isa": "MIPS16", "status": "static",
            "summary": "summary", "evidence": "finding.md",
        }
        with self.assertRaisesRegex(ValueError, "module:0x10.*reproduce"):
            validate_rows([row])

    def test_rejects_state_without_source_identity_fields(self):
        row = {
            "type": "state", "id": "module:ram:0x20", "module": "module",
            "variant": "v1", "address": "0x20", "width_bits": 8,
            "summary": "summary", "evidence": "finding.md",
        }
        with self.assertRaisesRegex(ValueError, "module:ram:0x20.*sha256, symbol"):
            validate_rows([row])

    def test_accepts_complete_records_of_each_kind(self):
        rows = [
            {"type": "function", "id": "module:0x10", "module": "module",
             "variant": "v1", "sha256": "abc", "address": "0x10",
             "symbol": "FUN_10", "isa": "MIPS16", "status": "static",
             "summary": "summary", "evidence": "finding.md", "reproduce": "probe.sh"},
            {"type": "state", "id": "module:ram:0x20", "module": "module",
             "variant": "v1", "sha256": "abc", "address": "0x20",
             "symbol": "state_20", "width_bits": 8, "summary": "summary",
             "evidence": "finding.md"},
            {"type": "edge", "source": "module:0x10", "target": "module:ram:0x20",
             "kind": "writes-state", "evidence": "finding.md"},
            {"type": "hypothesis", "id": "candidate:one", "variant": "v1",
             "status": "inference", "summary": "summary", "evidence": "finding.md"},
            {"type": "experiment", "id": "experiment:one", "module": "module",
             "variant": "v1", "address": "0x30", "status": "synthetic-pass",
             "summary": "summary", "evidence": "finding.md", "reproduce": "probe.sh"},
        ]
        validate_rows(rows)

    def test_rejects_hypothesis_without_evidence_status(self):
        row = {
            "type": "hypothesis", "id": "candidate:one", "variant": "v1",
            "summary": "summary", "evidence": "finding.md",
        }

        with self.assertRaisesRegex(ValueError, "candidate:one.*status"):
            validate_rows([row])

    def test_collects_edge_endpoints_without_detailed_facts_as_references(self):
        edges = [
            {
                "source": "module:0x10",
                "target": "resident:0xbfc00000"
            }
        ]

        references = reference_ids(edges, ["module:0x10"])

        self.assertEqual(["resident:0xbfc00000"], references)


if __name__ == "__main__":
    unittest.main()
