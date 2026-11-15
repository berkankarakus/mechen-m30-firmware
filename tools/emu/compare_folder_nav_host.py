#!/usr/bin/env python3
"""Compare host folder navigation against the real p-code boundary matrix.

The p-code probe is the authority for firmware state.  This comparator checks
only fields with an unambiguous shared meaning at the current boundary:
one-based active item and whether a single event wrapped at a list edge.  The
raw handler's start/end/status/update bytes remain in the matrix output until
their firmware-local meanings are resolved independently.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "tools" / "ghidra" / "run_folder_nav_matrix_probe.sh"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "emu"))

from folder_ui import FolderList, FolderRow
from scroll_accel import NEXT, PREVIOUS


PASS_RE = re.compile(
    r"^FOLDER NAV MATRIX PASS app=(?P<app>\w+) mode=(?P<mode>next|previous) "
    r"total=(?P<total>\d+) cursor=(?P<cursor>\d+) .*active=(?P<active>\d+)"
)


def main() -> int:
    completed = subprocess.run(
        ["bash", str(MATRIX)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        print(completed.stdout, end="")
        print(completed.stderr, end="")
        return completed.returncode

    records = [PASS_RE.match(line) for line in completed.stdout.splitlines()]
    records = [record for record in records if record is not None]
    if len(records) != 28:
        raise SystemExit(f"expected 28 matrix records, got {len(records)}")

    active_matches = 0
    wrap_matches = 0
    for record in records:
        assert record is not None
        app = record.group("app")
        mode = record.group("mode")
        total = int(record.group("total"))
        cursor = int(record.group("cursor"))
        expected_active = int(record.group("active"))
        direction = NEXT if mode == "next" else PREVIOUS
        view = FolderList(
            tuple(FolderRow(f"row-{index}") for index in range(total)),
            selected_index=cursor - 1,
        )
        result = view.move_event(direction, 0)
        actual_active = int(result["selected_index"]) + 1
        expected_wrap = (
            mode == "next" and expected_active < cursor
        ) or (
            mode == "previous" and expected_active > cursor
        )
        if actual_active != expected_active:
            raise SystemExit(
                f"active mismatch app={app} mode={mode} total={total} "
                f"cursor={cursor}: host={actual_active} pcode={expected_active}"
            )
        active_matches += 1
        if bool(result["wrapped"]) != expected_wrap:
            raise SystemExit(
                f"wrap mismatch app={app} mode={mode} total={total} "
                f"cursor={cursor}: host={result['wrapped']} pcode={expected_wrap}"
            )
        wrap_matches += 1

    print(
        "FOLDER NAV HOST COMPARE PASS "
        f"cases={len(records)} active={active_matches} wrap={wrap_matches}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
