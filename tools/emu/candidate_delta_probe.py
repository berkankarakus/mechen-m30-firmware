#!/usr/bin/env python3
"""Verify an extracted firmware candidate's exact member-level delta."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def member_names(directory: Path) -> tuple[str, ...]:
    if not directory.is_dir():
        raise AssertionError(f"firmware directory does not exist: {directory}")

    return tuple(sorted(path.name for path in directory.iterdir() if path.is_file()))


def verify_exact_delta(
    baseline: Path,
    candidate: Path,
    expected_changed: tuple[str, ...],
    require_same_size: bool = True,
) -> tuple[str, ...]:
    """Verify that only the named extracted members differ."""

    baseline_names = member_names(baseline)
    candidate_names = member_names(candidate)
    if baseline_names != candidate_names:
        missing = sorted(set(baseline_names) - set(candidate_names))
        extra = sorted(set(candidate_names) - set(baseline_names))
        raise AssertionError(f"member set changed: missing={missing!r}, extra={extra!r}")

    actual_changed: list[str] = []
    for name in baseline_names:
        baseline_path = baseline / name
        candidate_path = candidate / name
        if sha256(baseline_path) != sha256(candidate_path):
            actual_changed.append(name)
            if require_same_size and baseline_path.stat().st_size != candidate_path.stat().st_size:
                raise AssertionError(f"member size changed: {name}")

    actual = tuple(actual_changed)
    expected = tuple(sorted(set(expected_changed)))
    if actual != expected:
        raise AssertionError(f"unexpected member delta: expected={expected!r}, actual={actual!r}")

    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="extracted baseline fw directory")
    parser.add_argument("candidate", type=Path, help="extracted candidate fw directory")
    parser.add_argument(
        "--changed",
        action="append",
        required=True,
        dest="expected_changed",
        help="member expected to differ; repeat for each member",
    )
    parser.add_argument(
        "--allow-size-change",
        action="store_true",
        help="allow changed members to have a different size",
    )
    args = parser.parse_args()
    changed = verify_exact_delta(
        args.baseline,
        args.candidate,
        tuple(args.expected_changed),
        require_same_size=not args.allow_size_change,
    )
    print(
        "CANDIDATE DELTA PASS "
        f"baseline={args.baseline} candidate={args.candidate} "
        f"changed={','.join(changed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
