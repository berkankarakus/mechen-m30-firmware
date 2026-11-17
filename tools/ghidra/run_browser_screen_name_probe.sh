#!/usr/bin/env bash
# Reproduce the directory-list screen updater's name-buffer boundary.
# Static analysis only; this does not execute or modify firmware.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP=${1:-$ROOT/analysis/community/fw/browser.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$AP" ] || { echo "missing browser AP: $AP" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-browser-screen.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30browserscreen \
  -import "$AP" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript LoadAP.java "$AP" \
  -postScript DumpWords.java 0x40cd52c8 0x40cd52dc \
  -postScript DumpWords.java 0x48714a70 0x48714a7c \
  -postScript DumpAt.java \
    0x40cd5218,0x48714a20 \
    "$WORK/decomp.c" 2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

for marker in \
  'DumpAt: 40cd5218 -> FUN_40cd5218' \
  'DumpAt: 48714a20 -> FUN_48714a20' \
  'WORD address=40cd52d4 value=0x9fc155a4' \
  'WORD address=40cd52d8 value=0x48714a21' \
  'WORD address=48714a74 value=0x48594511' \
  'WORD address=48714a78 value=0xbfc16a29'; do
  grep -q "$marker" "$WORK/ghidra.log"
done

grep -q 'param_1 + 8' "$WORK/decomp.c"
grep -q '0x1c' "$WORK/decomp.c"

echo 'BROWSER SCREEN NAME PROBE PASS entry-name-destination=+8 provider=0x48594511 converter=0xbfc16a29'
