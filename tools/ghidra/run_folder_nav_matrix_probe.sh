#!/usr/bin/env bash
# Execute real browser/music folder handlers across list and page boundaries.
# This is a read-only Ghidra p-code regression probe; it never writes firmware.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-folder-matrix.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

# mode total page start end cursor expected-state-substring
CASES=(
  "next 1 1 1 1 1 mode=next start=1 end=1 active=1 previous=1 status=0 update=0 redraw=0 reset=0"
  "previous 1 1 1 1 1 mode=previous start=1 end=1 active=1 previous=1 status=0 update=0 redraw=0 reset=0"
  "next 2 7 1 2 2 mode=next start=1 end=2 active=1 previous=2 status=0 update=1 redraw=0 reset=0"
  "previous 2 7 1 2 1 mode=previous start=1 end=2 active=2 previous=1 status=0 update=1 redraw=0 reset=0"
  "next 7 7 1 7 7 mode=next start=1 end=7 active=1 previous=7 status=0 update=1 redraw=0 reset=0"
  "previous 7 7 1 7 1 mode=previous start=1 end=7 active=7 previous=1 status=0 update=1 redraw=0 reset=0"
  "next 8 7 1 7 7 mode=next start=2 end=8 active=8 previous=7 status=1 update=2 redraw=1 reset=0"
  "previous 8 7 1 8 1 mode=previous start=2 end=8 active=8 previous=7 status=5 update=2 redraw=0 reset=0"
  "next 9 7 2 8 8 mode=next start=3 end=9 active=9 previous=7 status=1 update=2 redraw=1 reset=0"
  "next 10 7 4 10 10 mode=next start=1 end=7 active=1 previous=1 status=4 update=2 redraw=0 reset=0"
  "previous 10 7 1 7 1 mode=previous start=4 end=10 active=10 previous=7 status=5 update=2 redraw=0 reset=0"
  "previous 10 7 4 10 4 mode=previous start=4 end=10 active=3 previous=4 status=0 update=1 redraw=0 reset=0"
  "next 10 7 1 7 7 mode=next start=2 end=8 active=8 previous=7 status=1 update=2 redraw=1 reset=0"
  "previous 10 7 1 7 7 mode=previous start=1 end=7 active=6 previous=7 status=0 update=1 redraw=0 reset=0"
)

case_no=0
for app in browser music; do
  for spec in "${CASES[@]}"; do
    read -r mode total page start end cursor expected <<< "$spec"
    case_no=$((case_no + 1))
    log="$WORK/${case_no}-${app}-${mode}.log"
    if ! bash "$ROOT/tools/ghidra/run_folder_nav_pcode_probe.sh" \
      "$app" "$mode" "$total" "$page" "$start" "$end" "$cursor" >"$log" 2>&1; then
      cat "$log" >&2
      exit 1
    fi
    actual=$(sed -n 's/.*FOLDER NAV PASS //p' "$log" | tail -n 1)
    actual=$(printf '%s\n' "$actual" | sed -E 's/^([^ ]+) steps=[0-9]+ /\1 /')
    if [[ "$actual" != *"$expected"* ]]; then
      echo "folder navigation matrix mismatch: app=$app case=$spec" >&2
      cat "$log" >&2
      exit 1
    fi
    printf 'FOLDER NAV MATRIX PASS app=%s mode=%s total=%s cursor=%s %s\n' \
      "$app" "$mode" "$total" "$cursor" "$expected"
  done
done

echo "FOLDER NAV MATRIX PASS cases=$case_no"
