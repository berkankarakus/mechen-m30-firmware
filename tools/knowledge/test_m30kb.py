import unittest
import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
from unittest.mock import patch

import m30kb
from m30kb import validate_rows


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
            {"type": "experiment", "id": "module:probe:1", "module": "module",
             "variant": "v1", "address": "0x10", "status": "executed",
             "summary": "probe summary", "evidence": "finding.md", "reproduce": "probe.sh"},
            {"type": "hypothesis", "id": "module:hypothesis:1", "variant": "v1",
             "status": "unconfirmed", "summary": "hypothesis summary",
             "evidence": "finding.md"},
        ]
        validate_rows(rows)

    def test_indexes_all_fact_types_but_traces_only_known_function_state_edges(self):
        function = {
            "type": "function", "id": "module:0x10", "module": "module",
            "variant": "v1", "sha256": "abc", "address": "0x10",
            "symbol": "FUN_10", "isa": "MIPS16", "status": "static",
            "summary": "function summary", "evidence": "finding.md",
            "reproduce": "probe.sh",
        }
        state = {
            "type": "state", "id": "module:ram:0x20", "module": "module",
            "variant": "v1", "sha256": "abc", "address": "0x20",
            "symbol": "state_20", "width_bits": 8, "summary": "state summary",
            "evidence": "finding.md",
        }
        experiment = {
            "type": "experiment", "id": "module:probe:1", "module": "module",
            "variant": "v1", "address": "0x10", "status": "pcode-complete",
            "summary": "distinctive experiment result", "evidence": "finding.md",
            "reproduce": "probe.sh",
        }
        hypothesis = {
            "type": "hypothesis", "id": "module:hypothesis:1", "variant": "v1",
            "status": "unconfirmed", "summary": "distinctive marquee candidate",
            "evidence": "finding.md",
        }
        valid_edge = {
            "type": "edge", "source": function["id"], "target": state["id"],
            "kind": "writes-state", "evidence": "finding.md",
        }
        unresolved_edge = {
            "type": "edge", "source": function["id"],
            "target": "resident:unresolved", "kind": "calls-resident-boundary",
            "summary": "distinctive unresolved timer boundary", "evidence": "finding.md",
        }
        rows = [function, state, experiment, hypothesis, valid_edge, unresolved_edge]

        with tempfile.TemporaryDirectory(prefix="m30kb-test-") as temp:
            source = Path(temp) / "facts.jsonl"
            database = Path(temp) / "knowledge.sqlite"
            source.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            with patch.object(m30kb, "SOURCE", source), patch.object(m30kb, "DATABASE", database):
                with redirect_stdout(StringIO()):
                    m30kb.build()

                with redirect_stdout(StringIO()) as output:
                    m30kb.search("distinctive marquee candidate")
                self.assertIn(hypothesis["id"], output.getvalue())

                with redirect_stdout(StringIO()) as output:
                    m30kb.search("distinctive experiment result")
                self.assertIn(experiment["id"], output.getvalue())

                with redirect_stdout(StringIO()) as output:
                    m30kb.search("distinctive unresolved timer boundary")
                unresolved_edge_id = m30kb.fact_id(unresolved_edge)
                self.assertIn(unresolved_edge_id, output.getvalue())
                with redirect_stdout(StringIO()) as output:
                    m30kb.show(unresolved_edge_id)
                self.assertIn("distinctive unresolved timer boundary", output.getvalue())

                with redirect_stdout(StringIO()) as output:
                    m30kb.trace(function["id"], state["id"])
                self.assertIn("writes-state", output.getvalue())

                with self.assertRaisesRegex(SystemExit, "unindexed endpoint"):
                    m30kb.trace(function["id"], "resident:unresolved")

                with redirect_stdout(StringIO()) as output:
                    m30kb.show(hypothesis["id"])
                self.assertIn("distinctive marquee candidate", output.getvalue())


if __name__ == "__main__":
    unittest.main()
