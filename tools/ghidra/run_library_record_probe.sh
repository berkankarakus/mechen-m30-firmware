#!/usr/bin/env bash
# Verify the playlist record/location ABI and fallback track-number parser boundary.
# Static Ghidra analysis only; no firmware or library is modified.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
PLAYLIST=${1:-$ROOT/analysis/community/fw/playlist.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}

if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null 2>&1; then
  JAVA_PREFIX=$(brew --prefix openjdk@25 2>/dev/null || true)
  JAVA_HOME="$JAVA_PREFIX/libexec/openjdk.jdk/Contents/Home"
fi

if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  export JAVA_HOME
fi

[ -f "$PLAYLIST" ] || { echo "missing playlist.ap: $PLAYLIST" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-library-record.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home" "$WORK/project"

JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30libraryrecord \
  -import "$PLAYLIST" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript LoadAP.java "$PLAYLIST" \
  -postScript DumpAt.java 0x40094c8c,0x40094d60,0x40094f2c,0x40094fec "$WORK/fallback.c" containing \
  -postScript DumpWords.java 0x40094fe8 0x40094fec \
  >"$WORK/run.log" 2>&1

grep -q 'DumpAt: 40094c8c -> FUN_40094c8c' "$WORK/run.log"
grep -q 'DumpAt: 40094d60 -> FUN_40094d60' "$WORK/run.log"
grep -q 'DumpAt: 40094f2c -> FUN_40094f2c' "$WORK/run.log"
grep -q 'DumpAt: 40094fec -> FUN_40094fec' "$WORK/run.log"
grep -q 'WORD address=40094fe8 value=0xbfc1640d' "$WORK/run.log"
grep -q "param_1\[bStack_10\] = '.'" "$WORK/fallback.c"
grep -q 'bStack_f = 9' "$WORK/fallback.c"
grep -q 'bStack_10 < 4' "$WORK/fallback.c"
grep -q "_UNK_40094f24\[bStack_10\] != '/'" "$WORK/fallback.c"
grep -q '0x2f < (byte)_UNK_40094f24' "$WORK/fallback.c"
grep -q 'bStack_f = bStack_f \*' "$WORK/fallback.c"
grep -q 'undefined2.*= 0xffff' "$WORK/fallback.c"
grep -q '+ 0xa9' "$WORK/fallback.c"
grep -q '+ 0xf4' "$WORK/fallback.c"

echo 'LIBRARY RECORD GHIDRA PASS location-callback=0xbfc1640d op=3 short-name=FUN_40094c8c track-prefix=4-digits fallback=0xffff'
